from pathlib import Path

from PIL import Image

from studio.blender_stack import _sequence_qc


def _fixture(tmp_path: Path) -> tuple[Path, dict, dict, Path]:
    artifact = tmp_path / "artifact"
    sequence = artifact / "render" / "P1"
    sequence.mkdir(parents=True)
    for frame in range(1, 11):
        Image.new("RGB", (16, 16), (frame * 10, 30, 60)).save(sequence / f"frame_{frame:04d}.png")
    info = {"frame_start": 1, "frame_end": 10, "screen_direction": "RIGHT", "ground_lock": True}
    profile = {"name": "P1", "width": 16, "height": 16, "alpha": False, "color_mode": "RGB"}
    return artifact, info, profile, sequence


def test_fast_qc_decodes_only_representative_frames(tmp_path: Path) -> None:
    artifact, info, profile, sequence = _fixture(tmp_path)

    report = _sequence_qc(artifact, info, profile, sequence, "render", mode="FAST")

    assert report["decision"] == "PASS"
    assert report["mode"] == "FAST"
    assert report["visual_checks"]["total_frames"] == 10
    assert report["visual_checks"]["decoded_frames"] == 5
    assert report["visual_checks"]["sequence_continuity_checked"] is True


def test_deep_qc_decodes_every_frame(tmp_path: Path) -> None:
    artifact, info, profile, sequence = _fixture(tmp_path)

    report = _sequence_qc(artifact, info, profile, sequence, "render", mode="DEEP")

    assert report["decision"] == "PASS"
    assert report["visual_checks"]["decoded_frames"] == 10


def test_fast_qc_detects_corrupt_representative_frame(tmp_path: Path) -> None:
    artifact, info, profile, sequence = _fixture(tmp_path)
    (sequence / "frame_0006.png").write_bytes(b"not-an-image")

    report = _sequence_qc(artifact, info, profile, sequence, "render", mode="FAST")

    assert report["decision"] == "BLOCKED"
    assert report["visual_checks"]["decode_errors"]


def test_missing_frame_blocks_both_profiles(tmp_path: Path) -> None:
    artifact, info, profile, sequence = _fixture(tmp_path)
    (sequence / "frame_0007.png").unlink()

    report = _sequence_qc(artifact, info, profile, sequence, "render", mode="FAST")

    assert report["decision"] == "BLOCKED"
    assert "frame_0007.png" in report["visual_checks"]["missing_frames"][0]
