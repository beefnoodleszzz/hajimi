from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio.generation.image import ROLE_BUDGETS, prepare_image_job, register_image_candidate, select_image_candidate
from studio.generation.image import load_image_prompt_artifact, write_image_prompt_artifact
from studio.config import dump_yaml


def _shot() -> dict:
    return {
        "id": "S001",
        "role": "HERO",
        "method": "ai_image",
        "shot_contract": {
            "subject": "a stable cloud",
            "environment": "deep atmospheric sky",
            "composition": "centered cloud with negative space",
            "lighting": "cool rim light",
            "palette": "navy and white",
            "forbidden": ["generated text"],
        },
        "reference_pack": {"style_ref": "style.png"},
        "image_candidate_plan": {"candidates": 1},
        "output": {"selected_keyframe": "shots/S001/images/selected_keyframe.png"},
    }


def _prompt_artifact(root: Path) -> dict:
    shot_dir = root / "shots" / "S001"
    shot_dir.mkdir(parents=True, exist_ok=True)
    dump_yaml(_shot()["shot_contract"], shot_dir / "shot.yaml")
    return write_image_prompt_artifact(
        root,
        "S001",
        "A final, agent-authored cloud keyframe prompt. Keep the cloud silhouette stable.",
        {"template": "single-subject cinematic keyframe", "style": "grounded miniature macro realism"},
        [],
    )


def test_image_registration_identifies_codex_backend(tmp_path: Path) -> None:
    source = tmp_path / "codex-result.png"
    source.write_bytes(b"image")
    artifact = _prompt_artifact(tmp_path)
    job = prepare_image_job(_shot(), prompt_artifact=artifact)
    destination = register_image_candidate(tmp_path, "S001", source, job, candidate_number=1)
    metadata = json.loads(destination.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["backend"] == "codex_image_gen"
    assert metadata["prompt"] == artifact["prompt"]
    assert metadata["prompt_artifact"]["path"] == "shots/S001/images/prompt.md"
    assert destination.exists()


def test_registered_image_candidate_can_be_selected_with_bound_review(tmp_path: Path) -> None:
    from PIL import Image

    source = tmp_path / "source.jpg"
    Image.new("RGB", (4, 4), "navy").save(source)
    artifact = _prompt_artifact(tmp_path)
    job = prepare_image_job(_shot(), prompt_artifact=artifact)
    register_image_candidate(tmp_path, "S001", source, job, candidate_number=1)
    selected = select_image_candidate(tmp_path, "S001", 1, "director")
    assert selected.name == "selected_keyframe.png"
    assert selected.is_file()
    selection = json.loads(selected.with_suffix(".json").read_text())
    assert selection["reviewer"] == "director"
    assert selection["selected_keyframe_sha256"]


def test_image_generation_defaults_to_one_candidate(tmp_path: Path) -> None:
    assert ROLE_BUDGETS == {"HERO": 1, "STORY": 1, "CONNECTOR": 1}
    shot = _shot()
    shot.pop("image_candidate_plan")
    shot["role"] = "UNLISTED_ROLE"
    assert prepare_image_job(shot, prompt_artifact=_prompt_artifact(tmp_path))["candidate_count"] == 1


def test_image_prompt_is_agent_artifact_and_required_for_packaging(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="agent-authored image prompt artifact is required"):
        prepare_image_job(_shot())
    artifact = _prompt_artifact(tmp_path)
    loaded = load_image_prompt_artifact(tmp_path, "S001")
    job = prepare_image_job(_shot(), prompt_artifact=loaded)
    assert job["prompt"] == artifact["prompt"]
    assert job["prompt_artifact"]["source_skill"]["commit"] == "0dc09c46c8a30b1fdd89c18cc78a894dac2104e3"


def test_candidate_registration_rejects_path_traversal_and_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "codex-result.png"
    source.write_bytes(b"image")
    job = prepare_image_job(_shot(), prompt_artifact=_prompt_artifact(tmp_path))
    with pytest.raises(ValueError, match="shot_id"):
        register_image_candidate(tmp_path, "../escape", source, job, candidate_number=1)
    first = register_image_candidate(tmp_path, "S001", source, job, candidate_number=1)
    with pytest.raises(FileExistsError):
        register_image_candidate(tmp_path, "S001", source, job, candidate_number=1)
    assert first.read_bytes() == b"image"
