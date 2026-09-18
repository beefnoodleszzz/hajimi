"""Resolve handoff planning and official-export readback validation.

This module does not pretend to mutate Resolve. It creates an ingest contract
from the episode manifest and validates the metadata exported by the real
Resolve session. The creative edit remains in Resolve, while the repository
owns deterministic paths, hashes, ordering, and readback evidence.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import write_json
from ..manifest import assert_valid_manifest, load_manifest, manifest_hash, manifest_input_hash
from ..media.hashing import sha256_file
from ..provenance import validate_episode_provenance

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
LEGACY_TIMELINE_RE = re.compile(r"(?:^|[_-])(?:v0?3|v1)(?:[_-]|$)", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _portableize(value: Any, root: Path) -> Any:
    """Keep handoff metadata clone-safe while runtime probes remain local."""

    if isinstance(value, dict):
        return {key: _portableize(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [_portableize(item, root) for item in value]
    if isinstance(value, str):
        path = Path(value).expanduser()
        if path.is_absolute():
            try:
                return str(path.resolve().relative_to(root.resolve()))
            except ValueError:
                return value
    return value


def resolve_capability() -> dict[str, Any]:
    candidates = [
        "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS/Resolve",
        "/Applications/DaVinci Resolve Studio/DaVinci Resolve Studio.app/Contents/MacOS/Resolve",
    ]
    found = next((candidate for candidate in candidates if Path(candidate).exists()), None)
    return {
        "available": bool(found),
        "binary": found,
        "version_target": "DaVinci Resolve 21.1",
        "status": "PARTIAL" if found else "EXTERNAL_RUNTIME_REQUIRED",
        "mutation": False,
        "mode": "HANDOFF_ONLY",
        "checks": {
            "app": "PASS" if found else "BLOCKED",
            "version": "UNKNOWN",
            "scripting_developer_files": "UNKNOWN",
            "mcp": "UNKNOWN",
            "runtime_connection": "UNKNOWN",
            "readback": "CONTRACT_ONLY",
        },
        "reason": "A local app path is not evidence of scripting, MCP, mutation, or readback readiness.",
    }


def resolve_doctor(root: str | Path) -> dict[str, Any]:
    """Return conservative Resolve readiness without mutating Resolve."""

    capability = resolve_capability()
    return {
        "command": "resolve doctor",
        "status": capability["status"],
        "capability": capability,
        "handoff": {
            "mode": "HANDOFF_ONLY",
            "mutation": False,
            "readback_validator": "studio.resolve.sync.validate_resolve_readback",
            "project_root": str(Path(root).resolve()),
        },
        "next_action": "Run the local Resolve runtime probe and record a verified readback before treating Resolve as runtime-ready.",
    }


def _resolve_path(root: Path, episode_root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    if str(path).startswith("episodes/") or str(path).startswith("blender/"):
        return root / path
    return episode_root / path


def _sequence_manifest(root: Path, episode_id: str, shot_id: str) -> dict[str, Any] | None:
    candidates = [
        root / "blender" / "generated" / "artifacts" / f"{episode_id.split('_', 1)[0]}_{shot_id}" / "render_manifest.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        manifest = _load_json(path)
        sequence_dir = _resolve_path(root, path.parent, str(manifest.get("sequence_dir", "")))
        if not sequence_dir.exists():
            sequence_dir = path.parent / str(manifest.get("sequence_dir", ""))
        files = sorted(sequence_dir.glob("*.png")) if sequence_dir.exists() else []
        return {
            "kind": "image_sequence",
            "manifest": str(path.resolve()),
            "manifest_sha256": sha256_file(path),
            "sequence_dir": str(sequence_dir.resolve()),
            "filename_pattern": manifest.get("filename_pattern"),
            "start": manifest.get("start"),
            "end": manifest.get("end"),
            "fps": manifest.get("fps"),
            "alpha": manifest.get("alpha"),
            "files": len(files),
            "qc_decision": manifest.get("qc_decision"),
        }
    return None


def _shot_media(root: Path, episode_root: Path, episode_id: str, shot: dict[str, Any]) -> dict[str, Any]:
    shot_id = str(shot["id"])
    shot_dir = episode_root / "shots" / shot_id
    configured = shot.get("active_media") or shot.get("source")
    explicit_media = bool(configured)
    videos: list[Path] = []
    if configured:
        candidate = _resolve_path(root, episode_root, str(configured))
        if candidate.is_file() and candidate.suffix.lower() in VIDEO_EXTENSIONS:
            videos.append(candidate)
        elif candidate.is_file() and candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            videos.append(candidate)
    if not explicit_media and shot_dir.exists():
        files = [path for path in shot_dir.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS]
        files.sort(key=lambda path: ("production" not in path.parts, "trimmed" not in path.name, str(path)))
        videos.extend(files)
    sequence = _sequence_manifest(root, episode_id, shot_id)
    active = videos[0] if videos else None
    if active is None and sequence and not explicit_media:
        active = Path(sequence["sequence_dir"])
    return {
        "active": str(active.resolve()) if active else None,
        "active_kind": (
            "video"
            if active and active.suffix.lower() in VIDEO_EXTENSIONS
            else "image"
            if active and active.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            else "image_sequence"
            if active and sequence
            else None
        ),
        "videos": [
            {
                "path": str(path.resolve()),
                "sha256": sha256_file(path),
                "kind": "image" if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else "video",
            }
            for path in videos
        ],
        "image_sequence": sequence,
    }


def _shot_qc_approved(episode_root: Path, manifest: dict[str, Any], shot: dict[str, Any], media: dict[str, Any]) -> bool:
    """Bind Resolve ingest approval to the exact active media evidence."""

    if shot.get("method") == "animatic_card" or shot.get("status") != "approved":
        return False
    report_path = episode_root / "qc" / "report.json"
    if not report_path.exists():
        return False
    try:
        report = _load_json(report_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    evidence = next((item for item in report.get("shots", []) if str(item.get("shot_id")) == str(shot.get("id"))), None)
    if not isinstance(evidence, dict):
        return False
    pass_evidence = evidence.get("decision") == "PASS" or (
        evidence.get("decision") == "REVIEW"
        and isinstance(evidence.get("director_review"), dict)
        and evidence["director_review"].get("status") == "PASS"
    )
    target = evidence.get("approval_target")
    if not pass_evidence or not isinstance(target, dict) or target.get("manifest_sha256") != manifest_input_hash(manifest):
        return False
    source = evidence.get("source")
    asset_hash = evidence.get("asset_hash")
    source_path = Path(str(source)).expanduser() if source else None
    if source_path is not None and not source_path.is_absolute():
        source_path = episode_root.parent.parent / source_path
    return bool(
        source_path
        and source_path.is_file()
        and isinstance(asset_hash, str)
        and sha256_file(source_path) == asset_hash
        and target.get("asset_sha256") == asset_hash
        and media.get("active")
    )


def _expected_timeline(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode_id": manifest["episode_id"],
        "width": manifest["master"]["width"],
        "height": manifest["master"]["height"],
        "fps": manifest["master"]["fps"],
        "sample_rate": manifest["master"]["sample_rate"],
        "shot_ids": [shot["id"] for shot in manifest.get("shots", [])],
    }


def _path_matches(expected: str | Path, actual: str | Path, root: Path | None = None) -> bool:
    """Compare Resolve's exported path across absolute/relative conventions."""

    expected_path = Path(expected).expanduser()
    actual_path = Path(actual).expanduser()
    if expected_path.is_absolute():
        expected_resolved = expected_path.resolve(strict=False)
    elif root is not None:
        expected_resolved = (root / expected_path).resolve(strict=False)
    else:
        expected_resolved = expected_path.resolve(strict=False)
    if actual_path.is_absolute():
        return actual_path.resolve(strict=False) == expected_resolved

    candidates: list[Path] = []
    if root is not None:
        candidates.append(root / actual_path)
        # Resolve exports commonly report `episodes/<id>/...`; a hand-entered
        # readback may instead report `master/...` relative to the episode.
        candidates.append(expected_resolved.parent.parent / actual_path)
    candidates.append(expected_resolved.parent / actual_path)
    return any(candidate.resolve(strict=False) == expected_resolved for candidate in candidates)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if "/" in text:
            numerator, denominator = text.split("/", 1)
            try:
                return float(numerator) / float(denominator)
            except (ValueError, ZeroDivisionError):
                return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _number_matches(expected: Any, actual: Any, tolerance: float = 0.0) -> bool:
    expected_value = _number(expected)
    actual_value = _number(actual)
    return expected_value is not None and actual_value is not None and abs(expected_value - actual_value) <= tolerance


def validate_resolve_readback(
    expected: dict[str, Any],
    readback: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate a Resolve export without relying on a private Resolve API."""

    if not isinstance(expected, dict) or not isinstance(readback, dict):
        raise ValueError("Resolve expected/readback values must be mappings")

    timeline = readback.get("timeline", {}) if isinstance(readback.get("timeline"), dict) else {}
    render = readback.get("render", {}) if isinstance(readback.get("render"), dict) else {}
    resolution = timeline.get("resolution") or render.get("resolution")
    parsed_width = parsed_height = None
    if isinstance(resolution, str) and "x" in resolution.lower():
        raw_width, raw_height = resolution.lower().split("x", 1)
        try:
            parsed_width, parsed_height = int(raw_width), int(raw_height)
        except ValueError:
            parsed_width = parsed_height = None
    video_shots = readback.get("video_shots", [])
    normalized = {
        "width": readback.get("width", parsed_width if parsed_width is not None else render.get("width")),
        "height": readback.get("height", parsed_height if parsed_height is not None else render.get("height")),
        "fps": readback.get("fps", timeline.get("fps", render.get("fps"))),
        "sample_rate": readback.get("sample_rate", timeline.get("sample_rate", render.get("audio_sample_rate"))),
        "shot_ids": readback.get("shot_ids") or [item.get("id") for item in video_shots if isinstance(item, dict)],
        "timeline_name": readback.get("timeline_name", timeline.get("name")),
        "master_path": readback.get("master_path", render.get("output")),
        "render_status": render.get("status"),
    }
    errors: list[str] = []
    for field in ("width", "height", "sample_rate"):
        if not _number_matches(expected.get(field), normalized.get(field)):
            errors.append(field)
    if not _number_matches(expected.get("fps"), normalized.get("fps"), tolerance=0.01):
        errors.append("fps")
    if normalized.get("shot_ids") != expected.get("shot_ids"):
        errors.append("shot_order")
    timeline_name = str(normalized.get("timeline_name", ""))
    if not timeline_name:
        errors.append("timeline_name")
    elif LEGACY_TIMELINE_RE.search(timeline_name):
        errors.append("legacy_timeline")
    if not normalized.get("master_path"):
        errors.append("master_path")
    elif expected.get("master_path") and not _path_matches(
        str(expected["master_path"]),
        str(normalized["master_path"]),
        Path(root).resolve() if root is not None else None,
    ):
        errors.append("master_path_mismatch")
    if normalized.get("render_status") and str(normalized["render_status"]).lower() not in {"complete", "completed", "success", "pass"}:
        errors.append("render_status")
    return {
        "schema_version": "resolve-readback-v1",
        "decision": "PASS" if not errors else "FAIL",
        "errors": errors,
        "expected": expected,
        "readback": readback,
        "normalized": normalized,
    }


def sync_episode(root: str | Path, episode_id: str) -> Path:
    root = Path(root).resolve()
    manifest_path = root / "episodes" / episode_id / "episode.yaml"
    manifest = load_manifest(manifest_path)
    assert_valid_manifest(manifest, manifest_path)
    episode_root = manifest_path.parent
    provenance_report = validate_episode_provenance(root, episode_id)
    provenance_by_shot = {str(item.get("shot_id")): item for item in provenance_report.get("shots", [])}
    shots = []
    for shot in manifest.get("shots", []):
        media = _shot_media(root, episode_root, manifest["episode_id"], shot)
        provenance = provenance_by_shot.get(str(shot["id"]), {"valid": False, "errors": ["missing provenance result"]})
        shots.append(
            {
                "id": shot["id"],
                "role": shot["role"],
                "method": shot["method"],
                "duration_target": shot.get("duration_target"),
                "time_start": shot.get("time_start"),
                "time_end": shot.get("time_end"),
                "status": shot.get("status"),
                "approved_for_ingest": bool(
                    media.get("active")
                    and provenance.get("valid")
                    and _shot_qc_approved(episode_root, manifest, shot, media)
                ),
                "media": _portableize(media, root),
                "provenance": _portableize(provenance, root),
            }
        )
    payload = {
        "schema_version": "resolve-handoff-v2",
        "episode_id": episode_id,
        "created_at": _utc_now(),
        "editor_of_record": "DaVinci Resolve 21.1",
        "pages": {"edit": True, "fusion": True, "fairlight": True},
        "capability": resolve_capability(),
        "timeline": {**_expected_timeline(manifest), "timebase": f"{manifest['master']['fps']} fps"},
        "manifest_sha256": manifest_hash(manifest_path),
        "provenance": _portableize(provenance_report, root),
        "shots": shots,
        "readback_contract": {"path": "edit/resolve_production_readback.json", "validator": "studio.resolve.sync.validate_resolve_readback"},
        "mode": "handoff_plan",
        "mutation": False,
        "note": "Plan only. Resolve remains the editor of record; import active video/image-sequence media in manifest order and record its export readback.",
    }
    destination = episode_root / "edit" / "resolve_sync_manifest.json"
    write_json(payload, destination)
    return destination


def record_resolve_readback(root: str | Path, episode_id: str, readback: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    if not isinstance(readback, dict):
        raise ValueError("Resolve readback must be a mapping")
    manifest_path = root / "episodes" / episode_id / "episode.yaml"
    manifest = load_manifest(manifest_path)
    assert_valid_manifest(manifest, manifest_path)
    raw_destination = manifest_path.parent / "edit" / "resolve_production_readback.json"
    # Persist the visible Resolve export separately from its validation result;
    # the raw export remains the source evidence used by master registration.
    write_json(readback, raw_destination)
    expected = _expected_timeline(manifest)
    configured_master = manifest.get("master", {}).get("path")
    if configured_master:
        expected["master_path"] = str(_resolve_path(root, manifest_path.parent, configured_master).resolve())
    result = validate_resolve_readback(expected, readback, root=root)
    result = _portableize(result, root)
    result["episode_id"] = episode_id
    result["recorded_at"] = _utc_now()
    result["source_readback"] = str(raw_destination.resolve().relative_to(root))
    destination = manifest_path.parent / "edit" / "resolve_readback_validation.json"
    write_json(result, destination)
    return result
