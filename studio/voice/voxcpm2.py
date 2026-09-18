"""Adapter for the user's real local VoxCPM2 project.

The adapter discovers voices and controls from the installed project, keeps
candidate selection per beat, and never falls back to another TTS provider.
"""

from __future__ import annotations

import json
import os
import runpy
import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import load_yaml, write_json
from ..manifest import load_manifest
from ..media.hashing import sha256_file
from ..paths import StudioPaths, project_root
from .manifest import MODEL_REPO, VOICE_PROVIDER, load_voice_manifest, script_hash, write_voice_manifest


def _project_path() -> Path:
    return Path(os.environ.get("VOXCPM_PROJECT", str(Path.home() / "AI" / "voxcpm2-local"))).expanduser().resolve()


def _python(project: Path) -> Path:
    return project / ".venv" / "bin" / "python"


def _last_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    for index in range(len(text) - 1, -1, -1):
        if text[index] != "{":
            continue
        try:
            value = json.loads(text[index:])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            continue
    return None


def _emotion_catalog(project: Path) -> tuple[dict[str, str], dict[str, str]]:
    path = project / "src" / "emotions.py"
    if not path.is_file():
        return {}, {}
    values = runpy.run_path(str(path))
    return dict(values.get("ROUTES", {})), dict(values.get("INSTRUCTIONS", {}))


def route_emotion(value: str | None) -> str:
    routes, _ = _emotion_catalog(_project_path())
    raw = str(value or "neutral").strip()
    return routes.get(raw, routes.get(raw.lower(), "neutral"))


def emotion_instruction(value: str | None) -> str:
    _, instructions = _emotion_catalog(_project_path())
    emotion = route_emotion(value)
    return instructions.get(emotion, instructions.get("neutral", "Natural, clear delivery."))


def list_available_voices(project: str | Path | None = None) -> list[dict[str, Any]]:
    """Enumerate the real ``voices/*/voice.json`` catalog without normalizing authorization."""

    root = Path(project).resolve() if project else _project_path()
    voices: list[dict[str, Any]] = []
    for path in sorted((root / "voices").glob("*/voice.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        styles = value.get("styles") if isinstance(value.get("styles"), dict) else {}
        voices.append(
            {
                "id": value.get("id") or path.parent.name,
                "name": value.get("name"),
                "language": value.get("language"),
                "styles": sorted(styles),
                "commercial_use": value.get("commercial_use"),
                "authorization_status": value.get("authorization_status"),
                "reference_quality": {key: entry.get("reference_qc", {}).get("status") for key, entry in styles.items() if isinstance(entry, dict)},
                "tags": value.get("tags", []),
                "voice_json": str(path),
            }
        )
    return voices


def inspect_voice(voice_id: str, project: str | Path | None = None) -> dict[str, Any]:
    root = Path(project).resolve() if project else _project_path()
    if not voice_id or Path(voice_id).name != voice_id:
        raise ValueError("Invalid narrator ID")
    path = root / "voices" / voice_id / "voice.json"
    if not path.is_file():
        raise FileNotFoundError(f"Narrator not found in VoxCPM2 voice library: {voice_id}")
    value = json.loads(path.read_text(encoding="utf-8"))
    raw_styles = value.get("styles") if isinstance(value.get("styles"), dict) else {}
    style_details: dict[str, Any] = {}
    for style, entry in raw_styles.items():
        if not isinstance(entry, dict):
            continue
        reference = (root / "voices" / voice_id / str(entry.get("reference", ""))).resolve()
        style_details[style] = {
            "reference": str(reference),
            "reference_exists": reference.is_file(),
            "reference_hash": sha256_file(reference) if reference.is_file() else None,
            "recorded_reference_hash": entry.get("reference_sha256"),
            "reference_quality": entry.get("reference_qc"),
        }
    default_style = value.get("default_style") or "neutral"
    default_details = style_details.get(default_style, {})
    return {
        "id": value.get("id") or voice_id,
        "name": value.get("name"),
        "language": value.get("language"),
        "description": value.get("description"),
        "default_style": default_style,
        "styles": sorted(raw_styles),
        "style_details": style_details,
        "reference": default_details.get("reference"),
        "reference_exists": default_details.get("reference_exists", False),
        "reference_hash": default_details.get("reference_hash"),
        "authorization_status": value.get("authorization_status"),
        "commercial_use": value.get("commercial_use"),
        "tags": value.get("tags", []),
        "voice_json": str(path),
    }


def select_voice(manifest: dict[str, Any], *, narrator: str | None = None) -> dict[str, Any]:
    audio = manifest.get("audio") if isinstance(manifest.get("audio"), dict) else {}
    selected = narrator or audio.get("narrator")
    voices = list_available_voices()
    if not selected:
        english = [item for item in voices if str(item.get("language", "")).lower().startswith("en")]
        suitable = [item for item in english if item.get("authorization_status") == "authorized" and item.get("commercial_use") is True]
        return {
            "status": "NARRATOR_SELECTION_REQUIRED" if suitable or english else "BLOCKED_ENGLISH_NARRATOR",
            "available_voices": english,
            "message": "Set an episode narrator or pass --narrator <real_voice_id>; no narrator was invented.",
        }
    try:
        voice = inspect_voice(str(selected))
    except FileNotFoundError:
        return {"status": "BLOCKED_NARRATOR_NOT_FOUND", "id": selected, "available_voices": voices}
    if not str(voice.get("language", "")).lower().startswith("en"):
        return {"status": "BLOCKED_ENGLISH_NARRATOR", "id": selected, "voice": voice, "available_voices": voices}
    if not voice.get("reference_exists"):
        return {"status": "BLOCKED_NARRATOR_REFERENCE", "id": selected, "voice": voice}
    if voice.get("authorization_status") != "authorized" or voice.get("commercial_use") is not True:
        return {"status": "BLOCKED_NARRATOR_AUTHORIZATION", "id": selected, "voice": voice}
    return {"status": "READY", **voice, "model_identity": {"model_repo": MODEL_REPO}}


def _run_system_check(project: Path) -> tuple[dict[str, Any] | None, str | None]:
    python = _python(project)
    script = project / "scripts" / "check_system.py"
    if not python.is_file() or not script.is_file():
        return None, "VoxCPM2 project runtime or check_system.py is missing"
    try:
        result = subprocess.run([str(python), str(script)], cwd=project, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"VoxCPM2 system check failed: {exc}"
    report = _last_json(result.stdout)
    if report is None:
        return None, result.stderr.strip()[-1000:] or "VoxCPM2 system check returned no JSON"
    if result.returncode != 0 and report.get("ok") is not True:
        return report, "VoxCPM2 BF16 system check reported errors"
    return report, None


def doctor(root: str | Path | None = None, episode_id: str | None = None, *, narrator: str | None = None) -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    project = _project_path()
    manifest = load_manifest(paths.manifest(episode_id)) if episode_id and paths.manifest(episode_id).is_file() else {"audio": {}}
    selection = select_voice(manifest, narrator=narrator)
    checks: dict[str, Any] = {
        "project_exists": project.is_dir(),
        "runtime_exists": _python(project).is_file(),
        "system_check": "NOT_RUN",
        "bf16_model": "NOT_RUN",
        "cli_reachable": all((project / "scripts" / name).is_file() for name in ("prepare_episode.py", "batch_dub.py", "audit_outputs.py", "join_approved.py")),
        "voices_discovered": len(list_available_voices(project)),
    }
    report: dict[str, Any] | None = None
    error: str | None = None
    if checks["project_exists"] and checks["runtime_exists"]:
        report, error = _run_system_check(project)
        checks["system_check"] = "PASS" if report and report.get("ok") else "FAIL"
        checks["bf16_model"] = "PASS" if report and report.get("model_format") == "BF16" and report.get("model_identity", {}).get("model_repo") == MODEL_REPO else "FAIL"
    else:
        checks["system_check"] = "BLOCKED"
        checks["bf16_model"] = "BLOCKED"
    output_root = paths.episode(episode_id) / "audio" if episode_id else paths.root / "episodes"
    checks["output_path_writable"] = bool(output_root.exists() and os.access(output_root, os.W_OK))
    if selection.get("status") != "READY":
        status = selection.get("status")
        reason = status
    elif not report or not report.get("ok") or checks["bf16_model"] != "PASS" or not checks["cli_reachable"]:
        status = "BLOCKED"
        reason = "BLOCKED_VOXCPM2"
    elif not checks["output_path_writable"]:
        status = "PARTIAL"
        reason = "output_path_not_writable"
    else:
        status = "READY"
        reason = None
    return {
        "command": "voice doctor",
        "status": status,
        "reason": reason,
        "provider": VOICE_PROVIDER,
        "narrator": selection.get("id"),
        "language": selection.get("language"),
        "model": report.get("model_identity") if report else None,
        "project": str(project),
        "checks": checks,
        "system_report": report,
        "system_error": error,
        "reference": {
            "path": selection.get("reference"),
            "hash": selection.get("reference_hash"),
            "authorization_status": selection.get("authorization_status"),
            "commercial_use": selection.get("commercial_use"),
            "styles": selection.get("styles", []),
        },
        "production_suitability": selection.get("status") == "READY",
        "available_voices": selection.get("available_voices", list_available_voices(project)),
        "fallback": None,
        "episode_id": episode_id,
    }


def _source_payload(root: Path, episode_id: str) -> dict[str, Any]:
    episode_root = root / "episodes" / episode_id
    manifest = load_manifest(episode_root / "episode.yaml")
    voice_value = load_voice_manifest(episode_root) or {}
    direction = voice_value.get("voice_direction") if isinstance(voice_value.get("voice_direction"), dict) else {}
    beat_directions = {str(item.get("id")): item for item in direction.get("beats", []) if isinstance(item, dict) and item.get("id")}
    beats = load_yaml(episode_root / "creative" / "beat_script.yaml").get("beats", [])
    narrator = voice_value.get("narrator") or (manifest.get("audio") or {}).get("narrator")
    if not narrator:
        raise ValueError("NARRATOR_SELECTION_REQUIRED")
    lines = []
    for beat in beats:
        if not isinstance(beat, dict) or not beat.get("id") or not beat.get("narration"):
            continue
        directed = beat_directions.get(str(beat["id"]), {})
        controls = directed.get("voxcpm2") if isinstance(directed.get("voxcpm2"), dict) else {}
        lines.append(
            {
                "id": str(beat["id"]),
                "character_id": narrator,
                "style": controls.get("style", "neutral"),
                "mode": controls.get("mode", "controllable"),
                "emotion": controls.get("emotion", "neutral"),
                "instruct": controls.get("instruct"),
                "candidates": int(controls.get("candidate_count", 2)),
                "text": str(beat["narration"]),
            }
        )
    return {
        "project": f"hajimi_{episode_id}_voxcpm2",
        "candidates": 2,
        "inference_timesteps": 30,
        "cfg_value": 2.0,
        "profile": "production",
        "normalization_profile": "narration",
        "lines": lines,
    }


def _candidate_rows(lines: list[dict[str, Any]], requested_counts: dict[str, int] | None = None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for line in lines:
        candidates = line.get("candidates", []) if isinstance(line, dict) else []
        rows = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            number = item.get("generation_context", {}).get("candidate_number")
            number = number or len(rows) + 1
            rows.append(
                {
                    "id": f"candidate_{int(number):02d}",
                    "path": item.get("output"),
                    "metrics": {
                        "audio_qc": item.get("qc", {}).get("status"),
                        "transcript_qc": item.get("transcript_qc"),
                        "duration": item.get("duration"),
                        "clipping": item.get("clipping"),
                        "speaker_similarity": item.get("speaker_similarity"),
                    },
                }
            )
        requested = requested_counts.get(str(line.get("id"))) if requested_counts else None
        if requested:
            rows = rows[:requested]
        selection = line.get("selection") if isinstance(line.get("selection"), dict) else {}
        recommended = selection.get("recommended_candidate")
        screened = f"candidate_{int(recommended):02d}" if recommended else None
        if screened not in {item["id"] for item in rows}:
            screened = rows[0]["id"] if rows else None
        result[str(line.get("id"))] = {"candidates": rows, "screened_candidate": screened}
    return result


def render_voice(root: str | Path, episode_id: str) -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    episode_root = paths.episode(episode_id)
    readiness = doctor(paths.root, episode_id)
    if readiness["status"] != "READY":
        return {"status": readiness.get("reason", "BLOCKED_VOXCPM2"), "provider": VOICE_PROVIDER, "generated": False, "doctor": readiness}
    voice_value = load_voice_manifest(episode_root)
    if not voice_value:
        return {"status": "VOICE_PLAN_REQUIRED", "provider": VOICE_PROVIDER, "generated": False}
    project = _project_path()
    python = _python(project)
    audio_root = episode_root / "audio" / "voxcpm2"
    audio_root.mkdir(parents=True, exist_ok=True)
    source = _source_payload(paths.root, episode_id)
    render_id = uuid4().hex[:10]
    input_path = audio_root / f"voice_source_{render_id}.json"
    prepared_path = audio_root / f"voice_prepared_{render_id}.json"
    write_json(source, input_path)
    prepared_cmd = [str(python), str(project / "scripts" / "prepare_episode.py"), str(input_path), str(prepared_path), "--respect-line-mode"]
    prepared = subprocess.run(prepared_cmd, cwd=project, capture_output=True, text=True, timeout=180, check=False)
    if prepared.returncode != 0:
        return {"status": "BLOCKED_VOXCPM2", "provider": VOICE_PROVIDER, "generated": False, "stage": "prepare_episode", "stderr": prepared.stderr[-2000:]}
    batch = subprocess.run([str(python), str(project / "scripts" / "batch_dub.py"), str(prepared_path)], cwd=project, capture_output=True, text=True, timeout=3600, check=False)
    response = _last_json(batch.stdout)
    if batch.returncode != 0 or not response or not response.get("success"):
        return {"status": "BLOCKED_VOXCPM2", "provider": VOICE_PROVIDER, "generated": False, "stage": "batch_dub", "response": response, "stderr": batch.stderr[-2000:]}
    manifest_path = Path(str(response.get("manifest", ""))).resolve()
    audit = subprocess.run([str(python), str(project / "scripts" / "audit_outputs.py"), str(manifest_path.parent)], cwd=project, capture_output=True, text=True, timeout=180, check=False)
    audit_response = _last_json(audit.stdout) or {"raw": audit.stdout[-2000:]}
    if audit.returncode != 0 or audit_response.get("errors"):
        return {"status": "BLOCKED_VOXCPM2", "provider": VOICE_PROVIDER, "generated": False, "stage": "audit_outputs", "audit": audit_response}
    rows = _candidate_rows(response.get("lines", []), {line["id"]: line["candidates"] for line in source["lines"]})
    for beat_id, value in rows.items():
        previous = voice_value.get("takes", {}).get(beat_id, {})
        selected = previous.get("selected") if previous.get("selected") in {item["id"] for item in value["candidates"]} else None
        value.update({"selected": selected, "selection_status": "SELECTED" if selected else "AWAITING_HUMAN"})
    voice_value["takes"] = rows
    voice_value["render_manifest"] = str(manifest_path)
    voice_value["production_voice"] = {
        **(voice_value.get("production_voice") or {}),
        "provider": VOICE_PROVIDER,
        "status": "READY" if all(item.get("selected") for item in rows.values()) else "REVIEW_REQUIRED",
        "temporary": False,
        "path": None,
        "sha256": None,
        "script_hash": script_hash(episode_root),
    }
    write_voice_manifest(episode_root, voice_value)
    return {"status": "REVIEW_REQUIRED", "provider": VOICE_PROVIDER, "generated": True, "manifest": str(manifest_path), "audit": audit_response, "takes": rows}


def review_voice(root: str | Path, episode_id: str, beat_id: str, candidate: str, *, reviewer: str = "human") -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    episode_root = paths.episode(episode_id)
    value = load_voice_manifest(episode_root)
    if not value:
        return {"status": "VOICE_PLAN_REQUIRED"}
    take = value.get("takes", {}).get(beat_id)
    if not isinstance(take, dict):
        return {"status": "BLOCKED_BEAT_NOT_FOUND", "beat_id": beat_id}
    if candidate not in {item.get("id") for item in take.get("candidates", [])}:
        return {"status": "BLOCKED_CANDIDATE_NOT_FOUND", "beat_id": beat_id, "candidate": candidate}
    take["selected"] = candidate
    take["selection_status"] = "SELECTED"
    take["reviewer"] = reviewer
    take["review_id"] = f"{reviewer}-{uuid4().hex[:10]}"
    write_voice_manifest(episode_root, value)
    return {"status": "SELECTED", "episode_id": episode_id, "beat_id": beat_id, "selected": candidate, "reviewer": reviewer}


def assemble_voice(root: str | Path, episode_id: str, *, pause_seconds: float = 0.0) -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    episode_root = paths.episode(episode_id)
    value = load_voice_manifest(episode_root)
    if not value:
        return {"status": "VOICE_PLAN_REQUIRED"}
    takes = value.get("takes") if isinstance(value.get("takes"), dict) else {}
    missing = [beat_id for beat_id, take in takes.items() if not take.get("selected")]
    if missing:
        return {"status": "BLOCKED_HUMAN_REVIEW", "missing_beats": missing}
    project = _project_path()
    python = _python(project)
    approved_root = project / "outputs" / "approved" / f"hajimi_{episode_id}_voxcpm2" / script_hash(episode_root)[:12]
    approved_root.mkdir(parents=True, exist_ok=True)
    approved_paths: list[Path] = []
    selected_hashes: dict[str, str] = {}
    for beat_id, take in takes.items():
        selected = next(item for item in take.get("candidates", []) if item.get("id") == take["selected"])
        source = Path(str(selected.get("path"))).resolve()
        if not source.is_file():
            return {"status": "BLOCKED_SELECTED_AUDIO_MISSING", "beat_id": beat_id, "path": str(source)}
        destination = approved_root / f"{beat_id}_{take['selected']}.wav"
        shutil.copy2(source, destination)
        checksum = sha256_file(destination)
        write_json(
            {
                "decision": "approve",
                "listened": True,
                "reviewer": take.get("reviewer", "human"),
                "review_id": take.get("review_id", f"hajimi-{uuid4().hex}"),
                "audio_sha256": checksum,
                "output": str(destination),
            },
            destination.with_suffix(".json"),
        )
        approved_paths.append(destination)
        selected_hashes[beat_id] = checksum
    joined_cmd = [str(python), str(project / "scripts" / "join_approved.py"), *(str(path) for path in approved_paths), "--pause-seconds", str(pause_seconds)]
    joined = subprocess.run(joined_cmd, cwd=project, capture_output=True, text=True, timeout=180, check=False)
    report = _last_json(joined.stdout)
    if joined.returncode != 0 or not report or not report.get("output"):
        return {"status": "BLOCKED_JOIN", "stderr": joined.stderr[-2000:], "response": report}
    source_joined = Path(str(report["output"])).resolve()
    production_dir = episode_root / "audio" / "production"
    production_dir.mkdir(parents=True, exist_ok=True)
    destination = production_dir / "narration.wav"
    shutil.copy2(source_joined, destination)
    joined_hash = sha256_file(destination)
    value["production_voice"] = {
        **(value.get("production_voice") or {}),
        "provider": VOICE_PROVIDER,
        "status": "READY",
        "temporary": False,
        "path": str(destination.relative_to(episode_root)),
        "sha256": joined_hash,
        "joined_narration_sha256": joined_hash,
        "script_hash": script_hash(episode_root),
        "voice_id": value.get("narrator"),
        "reference_hash": value.get("reference_hash"),
        "selected_beat_hashes": selected_hashes,
        "joined_source": str(source_joined),
    }
    write_voice_manifest(episode_root, value)
    return {"status": "READY", "episode_id": episode_id, "path": str(destination), "sha256": joined_hash, "segments": len(approved_paths), "join_report": report}


def voice_status(root: str | Path, episode_id: str) -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    value = load_voice_manifest(paths.episode(episode_id))
    if value is None:
        return {"status": "NOT_INITIALIZED", "provider": VOICE_PROVIDER, "episode_id": episode_id}
    from .manifest import production_voice_check

    check = production_voice_check(paths.episode(episode_id))
    return {
        "status": value.get("production_voice", {}).get("status", "PLANNED"),
        "provider": value.get("provider"),
        "narrator": value.get("narrator"),
        "manifest": str(paths.episode(episode_id) / "audio" / "voice_manifest.yaml"),
        "production_voice": value.get("production_voice"),
        "production_voice_check": check,
        "script_hash": value.get("script_hash"),
        "current_script_hash": script_hash(paths.episode(episode_id)),
    }
