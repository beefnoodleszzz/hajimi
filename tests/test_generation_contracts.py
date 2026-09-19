from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio.generation.image import ROLE_BUDGETS, prepare_image_job, register_image_candidate
from studio.generation.video import approve_video_candidate, prepare_video_job, register_video_candidate


def _shot(method: str = "ai_i2v") -> dict:
    contract = {
        "subject": "a stable cloud",
        "environment": "deep atmospheric sky",
        "composition": "centered cloud with negative space",
        "lighting": "cool rim light",
        "palette": "navy and white",
        "forbidden": ["generated text"],
        "first_frame": "cloud still",
        "end_frame": "cloud drifting",
        "continuity": {"identity": "same cloud"},
    }
    return {
        "id": "S001",
        "role": "HERO",
        "method": method,
        "shot_contract": contract,
        "reference_pack": {"style_ref": "style.png"},
        "image_candidate_plan": {"candidates": 1},
        "motion_plan": {
            "source_keyframe": "shots/S001/images/selected_keyframe.png",
            "generation_mode": "image_to_video",
            "subject_motion": "settle",
            "environmental_motion": "haze",
            "camera_motion": "push",
            "preserve": "identity",
            "avoid": "morphing",
        },
        "video_candidate_plan": {"candidates": 2},
        "output": {"download_target": "shots/S001/video", "video_dir": "shots/S001/video"},
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


def test_video_candidate_requires_local_download_before_approval(tmp_path: Path) -> None:
    job = prepare_video_job(_shot())
    with pytest.raises(FileNotFoundError):
        approve_video_candidate(tmp_path, "shots/S001/video/missing.mp4", reviewer="director")

    source = tmp_path / "flow-download.mp4"
    source.write_bytes(b"video")
    destination = register_video_candidate(tmp_path, "S001", source, job, candidate_number=1)
    approved = approve_video_candidate(tmp_path, destination, reviewer="director")
    metadata = json.loads(approved.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["backend"] == "google_flow_browser"
    assert metadata["status"] == "approved"


def test_video_approval_rejects_tampered_file_and_duplicate_candidate(tmp_path: Path) -> None:
    source = tmp_path / "flow-download.mp4"
    source.write_bytes(b"original video")
    job = prepare_video_job(_shot())
    candidate = register_video_candidate(tmp_path, "S001", source, job, candidate_number=1)
    with pytest.raises(FileExistsError):
        register_video_candidate(tmp_path, "S001", source, job, candidate_number=1)
    candidate.write_bytes(b"tampered video")
    with pytest.raises(ValueError, match="SHA-256"):
        approve_video_candidate(tmp_path, candidate, reviewer="director")


def test_i2v_requires_source_keyframe_and_multiframe_job_carries_local_segments(tmp_path: Path) -> None:
    shot = _shot("ai_i2v")
    shot["motion_plan"].pop("source_keyframe")
    with pytest.raises(ValueError, match="source keyframe"):
        prepare_video_job(shot)

    multi = _shot("ai_multiframe")
    multi["motion_plan"].update({
        "generation_mode": "multi_keyframe_video",
        "keyframes": [
            {"id": "KF1", "image": "shots/S001/images/KF1.png"},
            {"id": "KF2", "image": "shots/S001/images/KF2.png"},
            {"id": "KF3", "image": "shots/S001/images/KF3.png"},
        ],
        "segments": [
            {"id": "segment_A", "from": "KF1", "to": "KF2", "prompt": "Lift slightly."},
            {"id": "segment_B", "from": "KF2", "to": "KF3", "prompt": "Then fall."},
        ],
    })
    job = prepare_video_job(multi)
    assert [(segment["source_keyframe"], segment["target_keyframe"]) for segment in job["segment_jobs"]] == [
        ("shots/S001/images/KF1.png", "shots/S001/images/KF2.png"),
        ("shots/S001/images/KF2.png", "shots/S001/images/KF3.png"),
    ]
    source = tmp_path / "flow-segment.mp4"
    source.write_bytes(b"segment video")
    with pytest.raises(ValueError, match="segment_id"):
        register_video_candidate(tmp_path, "S001", source, job, candidate_number=1)
    registered = register_video_candidate(tmp_path, "S001", source, job, candidate_number=1, segment_id="segment_A")
    provenance = json.loads(registered.with_suffix(".json").read_text(encoding="utf-8"))
    assert provenance["source_image"] == "shots/S001/images/KF1.png"
    assert provenance["target_keyframe"] == "shots/S001/images/KF2.png"
    assert provenance["segment_id"] == "segment_A"
