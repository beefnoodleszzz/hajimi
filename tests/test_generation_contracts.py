from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio.generation.image import ROLE_BUDGETS, prepare_image_job, register_image_candidate


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


def test_image_registration_identifies_codex_backend(tmp_path: Path) -> None:
    source = tmp_path / "codex-result.png"
    source.write_bytes(b"image")
    job = prepare_image_job(_shot())
    destination = register_image_candidate(tmp_path, "S001", source, job, candidate_number=1)
    metadata = json.loads(destination.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["backend"] == "codex_image_gen"
    assert destination.exists()


def test_image_generation_defaults_to_one_candidate() -> None:
    assert ROLE_BUDGETS == {"HERO": 1, "STORY": 1, "CONNECTOR": 1}
    shot = _shot()
    shot.pop("image_candidate_plan")
    shot["role"] = "UNLISTED_ROLE"
    assert prepare_image_job(shot)["candidate_count"] == 1


def test_candidate_registration_rejects_path_traversal_and_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "codex-result.png"
    source.write_bytes(b"image")
    job = prepare_image_job(_shot())
    with pytest.raises(ValueError, match="shot_id"):
        register_image_candidate(tmp_path, "../escape", source, job, candidate_number=1)
    first = register_image_candidate(tmp_path, "S001", source, job, candidate_number=1)
    with pytest.raises(FileExistsError):
        register_image_candidate(tmp_path, "S001", source, job, candidate_number=1)
    assert first.read_bytes() == b"image"
