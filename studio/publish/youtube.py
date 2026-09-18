"""Safe YouTube Studio publish planning and readback persistence.

The repository owns the deterministic contract around a publish. The actual
logged-in browser interaction remains owned by the ``youtube-publisher`` skill
and ego-browser: this module never logs in, reads cookies, or calls a private
YouTube endpoint.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import load_yaml, write_json
from ..db import StateStore
from ..manifest import assert_valid_manifest, load_manifest, manifest_hash, manifest_input_hash, write_manifest
from ..media.hashing import sha256_file
from ..provenance import validate_episode_provenance
from ..resolve.sync import validate_resolve_readback

YOUTUBE_SCHEMA_VERSION = "youtube-publish-v2"
PRIVATE_VISIBILITY = "private"
REQUIRED_READBACK_FIELDS = ["video_url", "visibility", "metadata", "checks", "processing", "schedule"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _master_report(episode_root: Path) -> dict[str, Any] | None:
    path = episode_root / "qc" / "master_report.json"
    return _load_json(path) if path.exists() else None


def _animatic_gate(episode_root: Path) -> dict[str, Any] | None:
    path = episode_root / "animatic" / "gate.json"
    return _load_json(path) if path.exists() else None


def _resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def _portable_path(root: Path, value: str | Path) -> str:
    path = Path(value).resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _active_master(root: Path, episode_root: Path, manifest: dict[str, Any]) -> Path | None:
    """Resolve the one publishable master without relying on directory order."""

    configured = manifest.get("master", {}).get("path")
    candidates: list[Path] = []
    if configured:
        candidates.append(_resolve_path(episode_root, str(configured)))
    build_path = episode_root / "master" / "build.json"
    if build_path.exists():
        build = _load_json(build_path)
        if str(build.get("master_type", "")).startswith("resolve_") and build.get("output"):
            candidates.append(_resolve_path(root, str(build["output"])))
    resolve_render = episode_root / "master" / "resolve_render.json"
    if resolve_render.exists():
        render = _load_json(resolve_render)
        if render.get("output"):
            candidates.append(_resolve_path(root, str(render["output"])))
    candidates.extend(
        [
            episode_root / "master" / f"{manifest['episode_id']}_master_final.mp4",
            episode_root / "master" / f"{manifest['episode_id']}_master_final_v2.mp4",
        ]
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in {".mp4", ".mov", ".mkv"}:
            return candidate.resolve()
    return None


def _youtube_config(episode_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    publish_path = episode_root / "publish" / "publish.yaml"
    publish = load_yaml(publish_path) if publish_path.exists() else {}
    youtube = publish.get("youtube", {})
    if not isinstance(youtube, dict):
        raise ValueError("publish.yaml youtube must be a mapping")
    manifest_publish = manifest.get("publish", {})
    if not isinstance(manifest_publish, dict):
        raise ValueError("episode.yaml publish must be a mapping")
    return {"yaml": youtube, "manifest": manifest_publish}


def _resolve_readback_passes(
    root: Path,
    episode_root: Path,
    manifest: dict[str, Any],
    master_path: Path | None,
) -> bool:
    path = episode_root / "edit" / "resolve_production_readback.json"
    if not path.exists():
        return False
    try:
        readback = _load_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    expected = {
        "episode_id": manifest["episode_id"],
        "width": manifest["master"]["width"],
        "height": manifest["master"]["height"],
        "fps": manifest["master"]["fps"],
        "sample_rate": manifest["master"]["sample_rate"],
        "shot_ids": [shot["id"] for shot in manifest.get("shots", [])],
    }
    if master_path is not None:
        expected["master_path"] = str(master_path.resolve())
    return validate_resolve_readback(expected, readback, root=root).get("decision") == "PASS"


def _human_review_passed(report: dict[str, Any] | None) -> bool:
    if not report:
        return False
    review = report.get("human_review")
    return bool(
        report.get("human_review_recorded") is True
        and isinstance(review, dict)
        and review.get("status") == "PASS"
    )


def _master_qc_passes(report: dict[str, Any] | None, manifest: dict[str, Any], master_sha256: str | None) -> bool:
    return bool(
        report
        and report.get("decision") == "PASS"
        and master_sha256
        and report.get("master_sha256") == master_sha256
        and report.get("manifest_sha256") == manifest_input_hash(manifest)
    )


def _master_approval_passes(report: dict[str, Any] | None, manifest: dict[str, Any], master_sha256: str | None) -> bool:
    if not report or not master_sha256:
        return False
    if report.get("manifest_sha256") != manifest_input_hash(manifest):
        return False
    target = report.get("approval_target")
    review = report.get("human_review")
    review_target = review.get("approval_target") if isinstance(review, dict) else None
    return bool(
        isinstance(target, dict)
        and target.get("asset_sha256") == master_sha256
        and isinstance(review_target, dict)
        and review_target.get("asset_sha256") == master_sha256
        and review_target.get("manifest_sha256") == manifest_input_hash(manifest)
    )


def _shot_qc_evidence_passes(episode_root: Path, manifest: dict[str, Any]) -> bool:
    """Require PASS evidence for every approved shot, not only editable flags."""

    report_path = episode_root / "qc" / "report.json"
    if not report_path.exists():
        return False
    try:
        report = _load_json(report_path)
    except (OSError, json.JSONDecodeError):
        return False
    results = {str(item.get("shot_id")): item for item in report.get("shots", []) if isinstance(item, dict)}
    shots = manifest.get("shots", [])
    if not shots:
        return False
    for shot in shots:
        shot_id = str(shot.get("id"))
        if shot.get("method") == "animatic_card":
            return False
        evidence = results.get(shot_id)
        automated_pass = evidence.get("decision") == "PASS" if evidence else False
        director_override = bool(
            evidence
            and evidence.get("decision") == "REVIEW"
            and isinstance(evidence.get("director_review"), dict)
            and evidence["director_review"].get("status") == "PASS"
        )
        if shot.get("status") != "approved" or not evidence or not (automated_pass or director_override):
            return False
        source = evidence.get("source")
        asset_hash = evidence.get("asset_hash")
        if not source or not asset_hash:
            return False
        source_path = Path(str(source)).expanduser()
        if not source_path.is_absolute():
            source_path = episode_root.parent.parent / source_path
        if not source_path.is_file() or sha256_file(source_path) != asset_hash:
            return False
        approval_target = evidence.get("approval_target")
        if not isinstance(approval_target, dict):
            return False
        if approval_target.get("asset_sha256") != asset_hash or approval_target.get("manifest_sha256") != manifest_input_hash(manifest):
            return False
    return True


def _shot_provenance_passes(root: Path, episode_id: str, manifest: dict[str, Any]) -> bool:
    if not manifest.get("shots"):
        return False
    return validate_episode_provenance(root, episode_id).get("decision") == "PASS"


def build_publish_plan(root: str | Path, episode_id: str, requested_visibility: str = PRIVATE_VISIBILITY) -> dict[str, Any]:
    """Build a machine-readable ego-browser upload contract.

    A plan is not an upload. It is explicit about the human browser action,
    expected metadata, master hash, and readback fields required before the
    repository can record an upload as complete.
    """

    root = Path(root).resolve()
    episode_root = root / "episodes" / episode_id
    manifest_path = episode_root / "episode.yaml"
    manifest = load_manifest(manifest_path)
    assert_valid_manifest(manifest, manifest_path)
    visibility = requested_visibility.lower()
    if visibility not in {"private", "public", "scheduled"}:
        raise ValueError("visibility must be private, public, or scheduled")
    if visibility != PRIVATE_VISIBILITY:
        raise PermissionError("The default adapter only prepares private uploads; public/scheduled requires an explicitly authorized browser task")

    publish = _youtube_config(episode_root, manifest)
    youtube = publish["yaml"]
    manifest_publish = publish["manifest"]
    master_path = _active_master(root, episode_root, manifest)
    master_report = _master_report(episode_root)
    animatic_gate = _animatic_gate(episode_root)
    resolve_readback_pass = _resolve_readback_passes(root, episode_root, manifest, master_path)
    master_sha256 = sha256_file(master_path) if master_path else None
    title = youtube.get("title") or manifest_publish.get("title")
    description = youtube.get("description") or manifest_publish.get("description")
    audience = youtube.get("audience") or manifest_publish.get("audience")
    ai_use = youtube.get("ai_use")
    if ai_use is None and "ai_disclosure" in manifest_publish:
        ai_use = {
            "disclose": manifest_publish.get("ai_disclosure"),
            "reason": manifest_publish.get("ai_disclosure_reason"),
        }
    schedule = youtube.get("schedule", {"enabled": False, "timezone": None, "datetime": None})
    shots = manifest.get("shots", [])

    checks = {
        "animatic_gate": bool(animatic_gate and animatic_gate.get("production_gate") == "PASS"),
        "all_shots_approved": bool(shots) and all(shot.get("status") == "approved" for shot in shots),
        "shot_qc_evidence": _shot_qc_evidence_passes(episode_root, manifest),
        "shot_provenance": _shot_provenance_passes(root, episode_id, manifest),
        "resolve_readback": resolve_readback_pass,
        "master_qc": _master_qc_passes(master_report, manifest, master_sha256),
        "human_playback_recorded": _human_review_passed(master_report),
        "master_approval_hash_bound": _master_approval_passes(master_report, manifest, master_sha256),
        "master_exists": bool(master_path),
        "master_hash_recorded": bool(master_sha256),
        "master_hash_matches_qc": bool(master_report and master_sha256 and master_report.get("master_sha256") == master_sha256),
        "title_exists": isinstance(title, str) and bool(title.strip()),
        "description_exists": isinstance(description, str) and bool(description.strip()),
        "ai_disclosure_resolved": isinstance(ai_use, dict) and isinstance(ai_use.get("disclose"), bool),
        "audience_resolved": isinstance(audience, dict) and isinstance(audience.get("made_for_kids"), bool),
        "visibility_private": visibility == PRIVATE_VISIBILITY,
    }
    return {
        "schema_version": YOUTUBE_SCHEMA_VERSION,
        "episode_id": episode_id,
        "created_at": _utc_now(),
        "status": "READY" if all(checks.values()) else "BLOCKED",
        "lifecycle_status": "PREFLIGHT_READY" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "stage_policy": {
            "required_sequence": ["animatic_gate", "shot_approval", "master_qc", "human_playback", "private_upload", "checks_readback"],
            "animatic_gate": animatic_gate.get("decision") if animatic_gate else "NOT_RUN",
        },
        "master": {"path": _portable_path(root, master_path) if master_path else None, "sha256": master_sha256},
        "metadata": {
            "title": title,
            "description": description,
            "language": youtube.get("language", manifest.get("language")),
            "category": youtube.get("category"),
            "audience": audience,
            "ai_use": ai_use,
            "schedule": schedule,
        },
        "upload": {
            "method": "ego-browser",
            "operation": "uploadFile",
            "visibility": PRIVATE_VISIBILITY,
            "discovery": ["snapshotText", "discover current file input/control", "uploadFile", "snapshotText readback"],
        },
        "readback_contract": {
            "required": REQUIRED_READBACK_FIELDS,
            "must_match": ["master_sha256", "visibility", "metadata.title", "metadata.description", "metadata.audience", "metadata.ai_disclosure"],
        },
        "publisher": "ego-browser",
        "youtube_checks": {"copyright": "not_started", "likeness": "not_started", "upload": "not_started"},
        "note": "Plan only. Use the youtube-publisher skill and ego-browser for the visible logged-in upload; do not save credentials or cookies.",
    }


def preflight(root: str | Path, episode_id: str, requested_visibility: str = PRIVATE_VISIBILITY) -> dict[str, Any]:
    plan = build_publish_plan(root, episode_id, requested_visibility=requested_visibility)
    destination = Path(root) / "episodes" / episode_id / "publish" / "youtube.json"
    write_json(plan, destination)
    return plan


def publish_doctor(root: str | Path, episode_id: str | None = None) -> dict[str, Any]:
    """Report browser-publisher readiness without logging in or uploading."""

    project = Path(root).resolve()
    skill_present = (project / ".agents" / "skills" / "youtube-publisher" / "SKILL.md").exists()
    checks = {
        "ego_browser": "EXTERNAL_RUNTIME_REQUIRED",
        "youtube_studio_session": "NOT_PROBED",
        "upload_capability": "EXTERNAL_RUNTIME_REQUIRED",
        "publisher_skill": "PASS" if skill_present else "BLOCKED",
        "credentials_touched": False,
        "upload_attempted": False,
    }
    return {
        "command": "publish doctor",
        "episode_id": episode_id,
        "status": "EXTERNAL_RUNTIME_REQUIRED" if skill_present else "BLOCKED",
        "checks": checks,
        "next_action": "Use the youtube-publisher skill with ego-browser for a visible private upload; do not infer readiness from this doctor.",
    }


def _metadata_matches(plan: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    expected = plan.get("metadata", {})
    expected_ai = expected.get("ai_use")
    actual_ai = actual.get("ai_disclosure", actual.get("ai_use"))
    if isinstance(expected_ai, dict) and isinstance(actual_ai, bool):
        actual_ai = {"disclose": actual_ai}
    comparisons = {
        "metadata.title": (expected.get("title"), actual.get("title")),
        "metadata.description": (expected.get("description"), actual.get("description")),
        "metadata.audience": (expected.get("audience"), actual.get("audience")),
        "metadata.ai_disclosure": (expected_ai, actual_ai),
    }
    return [field for field, (expected_value, actual_value) in comparisons.items() if expected_value != actual_value]


def record_upload_readback(root: str | Path, episode_id: str, readback: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist the result returned by a visible ego-browser task."""

    if not isinstance(readback, dict):
        raise ValueError("YouTube readback must be a mapping")
    root = Path(root).resolve()
    path = root / "episodes" / episode_id / "publish" / "youtube.json"
    # Recompute the gate at recording time. A previously written READY plan
    # must not survive a changed master, shot status, QC report, or readback.
    plan = build_publish_plan(root, episode_id)
    write_json(plan, path)
    if plan.get("status") != "READY":
        raise RuntimeError("publish preflight is not READY; resolve checks before recording browser readback")
    missing = [field for field in REQUIRED_READBACK_FIELDS if field not in readback]
    if missing:
        raise ValueError(f"YouTube readback missing required fields: {', '.join(missing)}")
    url = readback.get("video_url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError("readback.video_url must be an http(s) URL")
    if readback.get("visibility") != PRIVATE_VISIBILITY:
        raise PermissionError("Only private upload readback can be recorded by the default adapter")
    if readback.get("master_sha256") != plan.get("master", {}).get("sha256"):
        raise ValueError("YouTube readback master_sha256 does not match the planned master")
    metadata = readback.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("readback.metadata must be a mapping")
    metadata_errors = _metadata_matches(plan, metadata)
    if metadata_errors:
        raise ValueError("YouTube metadata readback mismatch: " + ", ".join(metadata_errors))
    checks = readback.get("checks")
    if not isinstance(checks, dict) or checks.get("upload") != "complete":
        raise ValueError("YouTube readback must include checks.upload=complete")

    result = {
        **plan,
        "status": "UPLOADED_PRIVATE",
        "upload_attempted": True,
        "uploaded_at": _utc_now(),
        "video_url": url,
        "visibility": PRIVATE_VISIBILITY,
        "metadata_readback": metadata,
        "processing_readback": readback.get("processing"),
        "schedule_readback": readback.get("schedule"),
        "youtube_checks": checks,
        "task_space": readback.get("task_space"),
        "note": "Uploaded through the visible ego-browser YouTube Studio session; credentials remain outside the repository.",
    }
    write_json(result, path)
    manifest_path = root / "episodes" / episode_id / "episode.yaml"
    manifest = load_manifest(manifest_path)
    manifest_publish = manifest.setdefault("publish", {})
    manifest_publish["video_url"] = url
    manifest_publish["visibility"] = PRIVATE_VISIBILITY
    manifest_publish["processing"] = readback.get("processing")
    manifest_publish["schedule_readback"] = readback.get("schedule")
    manifest["status"] = "uploaded_private"
    write_manifest(manifest, manifest_path)
    store = StateStore(root / "studio" / "studio.sqlite3")
    store.sync_manifest(manifest, manifest_path, manifest_hash(manifest_path))
    store.record_publish(episode_id, "upload_complete", result)
    return result


def record_checks(root: str | Path, episode_id: str, checks: dict[str, Any]) -> dict[str, Any]:
    """Persist a later non-blocking Checks readback without changing visibility."""

    root = Path(root).resolve()
    path = root / "episodes" / episode_id / "publish" / "youtube.json"
    result = _load_json(path)
    if result.get("status") not in {"UPLOADED_PRIVATE", "CHECKS_RECORDED"}:
        raise RuntimeError("An uploaded private video is required before recording YouTube Checks")
    if not isinstance(checks, dict):
        raise ValueError("checks must be a mapping")
    missing = [field for field in ("copyright", "likeness", "upload") if field not in checks]
    if missing:
        raise ValueError("YouTube checks readback missing required fields: " + ", ".join(missing))
    if checks.get("upload") != "complete":
        raise ValueError("YouTube checks readback must preserve checks.upload=complete")
    result["youtube_checks"] = checks
    result["status"] = "CHECKS_RECORDED"
    result["checks_recorded_at"] = _utc_now()
    write_json(result, path)
    manifest_path = root / "episodes" / episode_id / "episode.yaml"
    manifest = load_manifest(manifest_path)
    manifest.setdefault("publish", {})["youtube_checks"] = checks
    manifest["status"] = "checks_pending"
    write_manifest(manifest, manifest_path)
    store = StateStore(root / "studio" / "studio.sqlite3")
    store.sync_manifest(manifest, manifest_path, manifest_hash(manifest_path))
    store.record_publish(episode_id, "checks_readback", result)
    return result


def publish_status(root: str | Path, episode_id: str) -> dict[str, Any]:
    path = Path(root) / "episodes" / episode_id / "publish" / "youtube.json"
    if not path.exists():
        return {"episode_id": episode_id, "status": "NOT_INITIALIZED", "path": str(path)}
    return _load_json(path)
