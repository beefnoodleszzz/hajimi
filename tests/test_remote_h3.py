from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from studio.config import dump_yaml, load_yaml, write_json
from studio.manifest import load_manifest
from studio.remote.contract import H3_BACKEND, prepare_h3_jobs, sha256_file, validate_h3_job
from studio.remote.result import import_h3_result, select_h3_candidate, validate_h3_result
from studio.remote import ssh_transport
from studio.provenance import validate_shot_provenance


EPISODE_ID = "EP099_remote-contract"


@pytest.mark.parametrize("transfer_tool", ["rsync", "scp"])
def test_upload_uses_configured_ssh_identity_and_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transfer_tool: str) -> None:
    package = tmp_path / "EP099_remote-contract_S001_r01"
    package.mkdir()
    (package / "job.json").write_text("{}", encoding="utf-8")
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(ssh_transport.subprocess, "run", fake_run)
    monkeypatch.setattr(
        ssh_transport.shutil,
        "which",
        lambda name: f"/mock/{name}" if name == transfer_tool else None,
    )
    connection = {
        "port": 2222,
        "target": "worker@example.test",
        "identity_file": "/keys/id with spaces",
        "ssh_config": "/configs/ssh config",
    }

    destination = ssh_transport.transfer_job(
        {"remote": {"root": "/srv/hajimi"}}, connection, package
    )

    assert destination == f"/srv/hajimi/jobs/inbox/{package.name}"
    if transfer_tool == "rsync":
        transport = commands[1][commands[1].index("-e") + 1]
        assert transport == "ssh -p 2222 -o BatchMode=yes -i '/keys/id with spaces' -F '/configs/ssh config'"
    else:
        assert commands[1][1:9] == [
            "-r", "-P", "2222", "-o", "BatchMode=yes", "-i",
            "/keys/id with spaces", "-F",
        ]
        assert commands[1][9] == "/configs/ssh config"


def _project(root: Path, *, include_keyframe: bool = True) -> Path:
    episode = root / "episodes" / EPISODE_ID
    shot_dir = episode / "shots" / "S001"
    shot_dir.mkdir(parents=True)
    shot = {
        "id": "S001",
        "version": 1,
        "role": "HERO",
        "method": "h3_i2v",
        "intent": "A measured cloud settles onto a platform.",
        "camera": {"movement": "small push"},
        "shot_contract": {
            "shot_id": "S001",
            "role": "HERO",
            "visual_goal": "Show contact without deformation.",
            "subject": "a compact cloud",
            "environment": "measurement stage",
            "composition": "centered portrait frame",
            "lighting": "cool edge light",
            "palette": "navy and white",
            "continuity": {"identity": "same cloud"},
            "forbidden": ["generated text"],
        },
        "motion_plan": {
            "source_keyframe": "shots/S001/images/selected_keyframe.png",
            "duration_target": 1.0,
            "subject_motion": "settles by a few centimeters",
            "environmental_motion": "subtle scale vibration",
            "camera_motion": "small push",
            "preserve": ["cloud silhouette", "platform geometry"],
            "avoid": ["morphing", "text"],
        },
        "video_candidate_plan": {"candidates": 1},
        "output": {
            "provenance": "provenance.json",
            "selected_keyframe": "shots/S001/images/selected_keyframe.png",
            "video_dir": "shots/S001/video",
            "download_target": "shots/S001/video",
        },
    }
    dump_yaml(shot, shot_dir / "shot.yaml")
    if include_keyframe:
        keyframe = shot_dir / "images" / "selected_keyframe.png"
        keyframe.parent.mkdir(parents=True)
        keyframe.write_bytes(b"selected keyframe bytes")
    manifest = {
        "episode_id": EPISODE_ID,
        "status": "production",
        "channel": "Test",
        "format": "youtube_short",
        "language": "en-US",
        "aspect_ratio": "9:16",
        "master": {"width": 1080, "height": 1920, "fps": 24, "sample_rate": 48000},
        "creative": {"promise": "Test promise", "hero_shot": "S001", "target_duration_sec": 1.0},
        "script": {"path": "script.md"},
        "audio": {"narrator": "science_female_main", "target_lufs": -14, "true_peak_max_db": -1},
        "shots": [{
            "id": "S001",
            "role": "HERO",
            "method": "h3_i2v",
            "status": "storyboard",
            "active_media": None,
            "duration_target": 1.0,
            "remote_status": "NOT_READY",
        }],
        "publish": {"visibility": "private"},
    }
    dump_yaml(manifest, episode / "episode.yaml")
    write_json({"production_gate": "PASS"}, episode / "animatic" / "gate.json")
    return episode


def _job() -> dict:
    return {
        "schema_version": "hajimi-h3-remote-v1",
        "job_id": f"{EPISODE_ID}_S001_r01",
        "episode_id": EPISODE_ID,
        "shot_id": "S001",
        "mode": "i2va",
        "candidate_count": 1,
        "duration_sec": 1.0,
        "aspect_ratio": "9:16",
        "prompt": "A cloud settles gently.",
        "inputs": {"first_frame": "assets/first.png", "last_frame": None, "reference_images": [], "reference_videos": [], "reference_audio": []},
        "input_sha256": {"assets/first.png": "a" * 64},
        "audio": {"generate_native_audio": True, "intent": "soft wind, no voice, no music"},
        "preserve": [],
        "avoid": [],
        "output": {"video": True, "native_audio": True},
    }


def _sample_mp4(path: Path) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("ffmpeg and ffprobe are required for the H3 result import contract")
    completed = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=navy:s=288x512:r=24:d=1", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", "1", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        pytest.skip("local ffmpeg lacks the codecs required for a tiny H3 result fixture")
    probe = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(probe.stdout)


def test_job_contract_rejects_unsafe_assets_and_hash_mismatches() -> None:
    job = _job()
    assert validate_h3_job(job) == []
    unsafe = {**job, "inputs": {**job["inputs"], "first_frame": "assets/../escape.png"}}
    assert any("stay inside" in error for error in validate_h3_job(unsafe))
    missing_hash = {**job, "input_sha256": {}}
    assert any("exactly match" in error for error in validate_h3_job(missing_hash))


def test_prepare_packages_only_selected_keyframe_and_records_hash(tmp_path: Path) -> None:
    episode = _project(tmp_path)
    packages = prepare_h3_jobs(tmp_path, EPISODE_ID, ["S001"])
    assert len(packages) == 1
    job = json.loads((packages[0] / "job.json").read_text(encoding="utf-8"))
    assert validate_h3_job(job) == []
    assert job["input_sha256"]["assets/first_frame.png"] == sha256_file(packages[0] / "assets" / "first_frame.png")
    assert sorted(path.name for path in (packages[0] / "assets").iterdir()) == ["first_frame.png"]
    manifest = load_manifest(episode / "episode.yaml")
    assert manifest["shots"][0]["remote_status"] == "REMOTE_READY"
    assert manifest["shots"][0]["remote_job"] == f"remote_jobs/{packages[0].name}/job.json"


def test_prepare_rejects_missing_keyframe(tmp_path: Path) -> None:
    _project(tmp_path, include_keyframe=False)
    with pytest.raises(FileNotFoundError, match="inputs.first_frame"):
        prepare_h3_jobs(tmp_path, EPISODE_ID, ["S001"])


def test_result_import_checks_native_audio_metadata_and_hash(tmp_path: Path) -> None:
    episode = _project(tmp_path)
    package = prepare_h3_jobs(tmp_path, EPISODE_ID, ["S001"])[0]
    job = json.loads((package / "job.json").read_text(encoding="utf-8"))
    result_directory = tmp_path / "remote-result"
    result_directory.mkdir()
    candidate_path = result_directory / "candidate_01.mp4"
    probe = _sample_mp4(candidate_path)
    video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
    audio = next(stream for stream in probe["streams"] if stream["codec_type"] == "audio")
    metadata = {
        "candidate_id": "candidate_01",
        "filename": candidate_path.name,
        "sha256": sha256_file(candidate_path),
        "duration": float(probe["format"]["duration"]),
        "width": video["width"],
        "height": video["height"],
        "fps": video["avg_frame_rate"],
        "has_audio": True,
        "audio_codec": audio["codec_name"],
        "sample_rate": int(audio["sample_rate"]),
        "channels": audio["channels"],
        "workflow_id": None,
        "workflow_version": None,
        "h3_model_identity": {
            "diffusion_model": {"filename": "minimax_h3_fl2va.safetensors", "present": True, "size_bytes": 1234},
            "text_encoder": {"filename": "qwen3vl_h3.safetensors", "present": True, "size_bytes": 5678},
        },
        "generation_parameters": {"mode": "i2va", "seed": 123},
    }
    write_json(metadata, result_directory / "candidate_01.json")
    write_json({
        "schema_version": "hajimi-h3-remote-v1",
        "job_id": job["job_id"],
        "status": "COMPLETE",
        "backend": H3_BACKEND,
        "candidates": [{"candidate_id": "candidate_01", "filename": candidate_path.name, "metadata_file": "candidate_01.json"}],
    }, result_directory / "result.json")

    imported = import_h3_result(tmp_path, EPISODE_ID, "S001", result_directory)

    assert imported.is_dir()
    assert (imported / candidate_path.name).read_bytes() == candidate_path.read_bytes()
    manifest = load_manifest(episode / "episode.yaml")
    assert manifest["shots"][0]["remote_status"] == "CANDIDATES_IMPORTED"
    invalid = json.loads((imported / "result.json").read_text(encoding="utf-8"))
    invalid["candidates"][0]["filename"] = "../candidate.mp4"
    assert any("without path components" in error for error in validate_h3_result(invalid, job))

    selected = select_h3_candidate(tmp_path, EPISODE_ID, "S001", 1, reviewer="local-director")
    assert selected.is_file()
    manifest = load_manifest(episode / "episode.yaml")
    assert manifest["shots"][0]["status"] == "qc_pending"
    assert manifest["shots"][0]["remote_status"] == "SELECTED"
    shot = load_yaml(episode / "shots" / "S001" / "shot.yaml")
    provenance = validate_shot_provenance(tmp_path, EPISODE_ID, shot)
    assert provenance["valid"] is True, provenance
    provenance_data = json.loads((episode / "shots" / "S001" / "provenance.json").read_text(encoding="utf-8"))
    assert provenance_data["qc"]["fast_qc"] == "pending"
