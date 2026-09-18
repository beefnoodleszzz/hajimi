"""Adapter for the user's existing local VoxCPM2 project.

The adapter invokes the project's real scripts instead of reimplementing a TTS
engine.  It never falls back to cloud TTS, macOS `say`, Qwen, or another local
provider when the configured narrator is unavailable.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from ..config import load_yaml, write_json
from ..manifest import load_manifest
from ..media.hashing import sha256_file
from ..paths import StudioPaths, project_root
from .manifest import DEFAULT_MODE, DEFAULT_NARRATOR, MODEL_REPO, VOICE_PROVIDER, load_voice_manifest, script_hash, write_voice_manifest


def _project_path() -> Path:
    return Path(os.environ.get("VOXCPM_PROJECT", str(Path.home() / "AI" / "voxcpm2-local"))).expanduser().resolve()


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


def _run_system_check(project: Path) -> tuple[dict[str, Any] | None, str | None]:
    python = project / ".venv" / "bin" / "python"
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
    selected = narrator or DEFAULT_NARRATOR
    voice_json = project / "voices" / selected / "voice.json"
    output_root = paths.episode(episode_id) / "audio" if episode_id else paths.root / "episodes"
    checks: dict[str, Any] = {
        "project_exists": project.is_dir(),
        "runtime_exists": (project / ".venv" / "bin" / "python").is_file(),
        "system_check": "NOT_RUN",
        "bf16_model": "NOT_RUN",
        "reference_voice": "NOT_RUN",
        "output_path_writable": bool(output_root.exists() and os.access(output_root, os.W_OK)),
        "cli_reachable": all((project / "scripts" / name).is_file() for name in ("prepare_episode.py", "batch_dub.py", "audit_outputs.py")),
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
    reference_details: dict[str, Any] = {"id": selected, "path": str(voice_json), "exists": voice_json.is_file()}
    if voice_json.is_file():
        try:
            voice = json.loads(voice_json.read_text(encoding="utf-8"))
            style = voice.get("styles", {}).get("neutral", {})
            reference = project / "voices" / selected / str(style.get("reference", ""))
            reference_details.update({
                "language": voice.get("language"),
                "reference": str(reference),
                "reference_exists": reference.is_file(),
                "authorization_status": voice.get("authorization_status"),
                "commercial_use": voice.get("commercial_use"),
                "reference_sha256": style.get("reference_sha256"),
            })
            reference_ok = bool(reference.is_file() and voice.get("authorization_status") == "authorized" and voice.get("commercial_use") is True and voice.get("language") == "en")
        except (OSError, json.JSONDecodeError, TypeError):
            reference_ok = False
    else:
        reference_ok = False
    checks["reference_voice"] = "PASS" if reference_ok else "BLOCKED_NARRATOR_REFERENCE"
    core_ok = bool(report and report.get("ok") and checks["bf16_model"] == "PASS" and checks["cli_reachable"])
    if not core_ok:
        status = "BLOCKED"
        reason = "BLOCKED_VOXCPM2"
    elif not reference_ok:
        status = "BLOCKED"
        reason = "BLOCKED_NARRATOR_REFERENCE"
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
        "narrator": selected,
        "mode": DEFAULT_MODE,
        "project": str(project),
        "checks": checks,
        "system_report": report,
        "system_error": error,
        "reference": reference_details,
        "fallback": None,
        "episode_id": episode_id,
    }


def _source_payload(root: Path, episode_id: str) -> dict[str, Any]:
    episode_root = root / "episodes" / episode_id
    manifest = load_manifest(episode_root / "episode.yaml")
    beats = load_yaml(episode_root / "creative" / "beat_script.yaml").get("beats", [])
    audio = manifest.get("audio", {}) if isinstance(manifest.get("audio"), dict) else {}
    narrator = audio.get("narrator") or DEFAULT_NARRATOR
    return {
        "project": f"hajimi_{episode_id}_voxcpm2",
        "candidates": 3,
        "inference_timesteps": 30,
        "cfg_value": 2.0,
        "profile": "production",
        "lines": [
            {"id": str(beat["id"]), "character_id": narrator, "style": "neutral", "mode": "ultimate", "text": str(beat.get("narration", ""))}
            for beat in beats if isinstance(beat, dict) and beat.get("id") and beat.get("narration")
        ],
    }


def render_voice(root: str | Path, episode_id: str) -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    episode_root = paths.episode(episode_id)
    readiness = doctor(paths.root, episode_id)
    if readiness["status"] != "READY":
        return {"status": readiness.get("reason", "BLOCKED_VOXCPM2"), "provider": VOICE_PROVIDER, "generated": False, "doctor": readiness}
    project = _project_path()
    python = project / ".venv" / "bin" / "python"
    audio_root = episode_root / "audio" / "voxcpm2"
    audio_root.mkdir(parents=True, exist_ok=True)
    source = _source_payload(paths.root, episode_id)
    input_path = audio_root / "voice_source.json"
    prepared_path = audio_root / "voice_prepared.json"
    write_json(source, input_path)
    prepared_cmd = [str(python), str(project / "scripts" / "prepare_episode.py"), str(input_path), str(prepared_path), "--exact-performance"]
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
    value = load_voice_manifest(episode_root) or {}
    selected = str(value.get("selection_policy", {}).get("selected_candidate", "candidate_02"))
    lines = response.get("lines", [])
    selected_paths = []
    for line in lines:
        candidates = line.get("candidates", []) if isinstance(line, dict) else []
        chosen = next((item for item in candidates if Path(str(item.get("output", ""))).name == f"{selected}.wav"), None)
        if chosen:
            selected_paths.append(chosen)
    if not selected_paths or len(selected_paths) != len(lines):
        return {"status": "BLOCKED_VOXCPM2", "provider": VOICE_PROVIDER, "generated": False, "stage": "candidate_selection", "reason": "selected candidate is missing for one or more beat lines"}
    value["takes"] = {str(line.get("id")): {"selected": selected, "candidates": line.get("candidates", []), "status": "SELECTED"} for line in lines}
    value["production_voice"] = {"provider": VOICE_PROVIDER, "status": "READY", "temporary": False, "path": str(manifest_path.parent), "sha256": sha256_file(manifest_path)}
    write_voice_manifest(episode_root, value)
    return {"status": "READY", "provider": VOICE_PROVIDER, "generated": True, "manifest": str(manifest_path), "audit": audit_response, "selected_candidate": selected, "line_count": len(lines)}


def voice_status(root: str | Path, episode_id: str) -> dict[str, Any]:
    paths = StudioPaths(Path(root).resolve() if root else project_root())
    value = load_voice_manifest(paths.episode(episode_id))
    if value is None:
        return {"status": "NOT_INITIALIZED", "provider": VOICE_PROVIDER, "episode_id": episode_id}
    return {"status": value.get("production_voice", {}).get("status", "PLANNED"), "provider": value.get("provider"), "narrator": value.get("narrator"), "manifest": str(paths.episode(episode_id) / "audio" / "voice_manifest.yaml"), "production_voice": value.get("production_voice"), "script_hash": value.get("script_hash"), "current_script_hash": script_hash(paths.episode(episode_id))}

