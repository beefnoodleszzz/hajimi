"""Mechanical preview transcode from an accepted animatic.

This is not the full FFmpeg roughcut path and does not create a publishable
master. The normal local master is built from approved shots with
``studio.roughcut``; optional Resolve exports are registered separately.
"""

from __future__ import annotations

import json
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import write_json
from .manifest import assert_valid_manifest, write_manifest
from .media.probe import executable
from .media.hashing import sha256_file
from .media.probe import probe_media
from .voice.manifest import production_voice_check


def _portable_path(root: Path, value: str | Path) -> str:
    path = Path(value).resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _require_production_gate(episode_root: Path) -> None:
    gate_path = episode_root / "animatic" / "gate.json"
    if not gate_path.exists():
        raise RuntimeError("Animatic gate is missing; formal production cannot start")
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Animatic gate is unreadable: {gate_path}") from exc
    if gate.get("production_gate") != "PASS":
        raise RuntimeError("Animatic production_gate is not PASS; director approval is required before formal production")


def build_release_candidate(episode_root: str | Path, manifest: dict[str, Any], source: str | Path | None = None, force: bool = False) -> Path:
    episode_root = Path(episode_root)
    assert_valid_manifest(manifest, episode_root / "episode.yaml")
    gate_path = episode_root / "animatic" / "gate.json"
    if not gate_path.exists():
        raise RuntimeError("Animatic gate is missing; formal production cannot start")
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Animatic gate is unreadable: {gate_path}") from exc
    if gate.get("production_gate") != "PASS":
        raise RuntimeError("Animatic production_gate is not PASS; formal production cannot start")
    source_path = Path(source) if source else episode_root / "animatic" / f"{manifest['episode_id']}_animatic.mp4"
    if not source_path.exists():
        raise FileNotFoundError(f"Accepted animatic not found: {source_path}")
    output = episode_root / "master" / f"{manifest['episode_id']}_master_rc01.mp4"
    if output.exists() and not force:
        return output
    ffmpeg_bin = executable("HAJIMI_FFMPEG", "ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg is required for the local release-candidate transcode")
    master = manifest["master"]
    vf = f"scale={master['width']}:{master['height']}:force_original_aspect_ratio=decrease,pad={master['width']}:{master['height']}:(ow-iw)/2:(oh-ih)/2:color=black"
    command = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-nostdin",
        "-i",
        str(source_path),
        "-vf",
        vf,
        "-r",
        str(master["fps"]),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        str(master["sample_rate"]),
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output),
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-3000:] or "release-candidate transcode failed")
    write_json(
        {
            "schema_version": "master-build-v1",
            "episode_id": manifest["episode_id"],
            "source": _portable_path(episode_root.parent.parent, source_path),
            "output": _portable_path(episode_root.parent.parent, output),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "master_type": "animatic_release_candidate",
            "editor_of_record": "FFmpeg animatic preview",
            "note": "Mechanical animatic preview only; build the approved-shot FFmpeg roughcut before master QC.",
        },
        episode_root / "master" / "build.json",
    )
    return output


def _fps_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            return float(numerator) / float(denominator)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def register_resolve_master(episode_root: str | Path, manifest: dict[str, Any], source: str | Path, force: bool = False) -> dict[str, Any]:
    """Register a Resolve premium-finish export as the active master.

    When the optional Resolve path is used, validate the export, copy it into
    the immutable episode delivery location, and record its hash/probe evidence.
    """

    episode_root = Path(episode_root)
    assert_valid_manifest(manifest, episode_root / "episode.yaml")
    _require_production_gate(episode_root)
    voice_check = production_voice_check(episode_root)
    if not voice_check["pass"]:
        raise RuntimeError(f"Production master requires local VoxCPM2 voice: {voice_check['reason']}")
    source_path = Path(source).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Resolve master not found: {source_path}")
    probe = probe_media(source_path)
    if not probe.get("ok"):
        raise RuntimeError("Resolve master failed deterministic media validation")
    expected = manifest["master"]
    video = probe.get("video", {})
    audio = probe.get("audio", {})
    mismatches: list[str] = []
    if video.get("width") != expected["width"]:
        mismatches.append("width")
    if video.get("height") != expected["height"]:
        mismatches.append("height")
    fps = _fps_value(video.get("fps"))
    if fps is None or abs(fps - float(expected["fps"])) > 0.01:
        mismatches.append("fps")
    try:
        sample_rate = int(audio.get("sample_rate"))
    except (TypeError, ValueError):
        sample_rate = None
    if sample_rate != int(expected["sample_rate"]):
        mismatches.append("sample_rate")
    if mismatches:
        raise ValueError("Resolve master does not match manifest: " + ", ".join(mismatches))

    output = episode_root / "master" / f"{manifest['episode_id']}_master_final.mp4"
    source_hash = sha256_file(source_path)
    if output.resolve() != source_path:
        if output.exists() and not force:
            if sha256_file(output) != source_hash:
                raise FileExistsError(f"Active master exists and differs; pass force to replace: {output}")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, output)
    build = {
        "schema_version": "master-build-v2",
        "episode_id": manifest["episode_id"],
        "source": str(source_path),
        "output": _portable_path(episode_root.parent.parent, output),
        "source_sha256": source_hash,
        "master_sha256": sha256_file(output),
        "probe": probe,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "master_type": "resolve_master",
        "editor_of_record": "DaVinci Resolve 21.1",
        "publishable": False,
    }
    resolve_readback = episode_root / "edit" / "resolve_production_readback.json"
    if resolve_readback.exists():
        from .resolve.sync import validate_resolve_readback

        try:
            readback = json.loads(resolve_readback.read_text(encoding="utf-8"))
            expected_readback = {
                "episode_id": manifest["episode_id"],
                "width": expected["width"],
                "height": expected["height"],
                "fps": expected["fps"],
                "sample_rate": expected["sample_rate"],
                "shot_ids": [shot["id"] for shot in manifest.get("shots", [])],
                "master_path": str(output.resolve()),
            }
            validation = validate_resolve_readback(
                expected_readback,
                readback,
                root=episode_root.parent.parent,
            )
            build["resolve_readback_validation"] = validation
            build["publishable"] = validation.get("decision") == "PASS"
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            build["resolve_readback_validation"] = {"decision": "FAIL", "errors": [f"{type(exc).__name__}: {exc}"]}
        build["resolve_readback"] = _portable_path(episode_root.parent.parent, resolve_readback)
    build["publish_block_reason"] = None if build["publishable"] else "RESOLVE_READBACK_REQUIRED"
    manifest["master"]["path"] = str(output.relative_to(episode_root))
    manifest["master"]["source"] = "resolve"
    write_manifest(manifest, episode_root / "episode.yaml")
    write_json(build, episode_root / "master" / "build.json")
    return build
