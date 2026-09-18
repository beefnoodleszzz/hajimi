"""Audio diagnostics and optional ASR comparison."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .probe import probe_media

NUMBER_TOKENS = {"465", "1000", "one", "second", "meters", "meter"}
NUMBER_PHRASE = ("four", "hundred", "sixty", "five")


def normalize_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _canonical_words(text: str) -> list[str]:
    words = normalize_words(text)
    canonical: list[str] = []
    index = 0
    while index < len(words):
        if tuple(words[index : index + len(NUMBER_PHRASE)]) == NUMBER_PHRASE:
            canonical.append("465")
            index += len(NUMBER_PHRASE)
        else:
            canonical.append(words[index])
            index += 1
    return canonical


def transcript_diff(expected: str, actual: str) -> dict[str, Any]:
    expected_words = _canonical_words(expected)
    actual_words = _canonical_words(actual)
    expected_counts = Counter(expected_words)
    actual_counts = Counter(actual_words)
    missing = [word for word, count in expected_counts.items() for _ in range(max(0, count - actual_counts[word]))]
    extra = [word for word, count in actual_counts.items() for _ in range(max(0, count - expected_counts[word]))]
    key_numbers = [word for word in expected_words if word in NUMBER_TOKENS]
    missing_key_numbers = [word for word in key_numbers if actual_counts[word] == 0]
    matched_word_count = len(expected_words) - len(missing)
    return {
        "expected_word_count": len(expected_words),
        "actual_word_count": len(actual_words),
        "missing_words": missing,
        "extra_words": extra,
        "matched_word_count": matched_word_count,
        "coverage": round(matched_word_count / max(1, len(expected_words)), 3),
        "missing_key_tokens": missing_key_numbers,
        "decision": "PASS" if not missing else "REVIEW",
    }


def audio_qc(path: str | Path, expected_transcript: str | None = None) -> dict[str, Any]:
    probe = probe_media(path)
    audio_metadata = probe.get("audio") if isinstance(probe.get("audio"), dict) else {}
    has_audio = any(stream.get("codec_type") == "audio" for stream in probe.get("streams", [])) or bool(
        audio_metadata.get("codec") or audio_metadata.get("sample_rate")
    )
    if not has_audio:
        return {"status": "NO_AUDIO", "asr": {"status": "not_run"}}
    result: dict[str, Any] = {"status": "PASS" if probe.get("ok") else "REVIEW", "asr": {"status": "not_run"}}
    try:
        from faster_whisper import WhisperModel  # type: ignore

        model = WhisperModel("small", compute_type="int8")
        segments, info = model.transcribe(str(path), vad_filter=True)
        actual = " ".join(segment.text.strip() for segment in segments)
        result["asr"] = {"status": "PASS", "language": info.language, "text": actual}
        if expected_transcript:
            result["asr"]["diff"] = transcript_diff(expected_transcript, actual)
    except ImportError:
        result["asr"] = {"status": "unavailable", "reason": "faster-whisper is optional"}
    except Exception as exc:
        result["asr"] = {"status": "error", "reason": exc.__class__.__name__}
    return result


def _resolve_audio_path(root: Path, episode_root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve(strict=False)
    if str(path).startswith("episodes/"):
        return (root / path).resolve(strict=False)
    return (episode_root / path).resolve(strict=False)


def validate_sound_layers(
    root: str | Path,
    episode_root: str | Path,
    manifest: dict[str, Any],
    *,
    stems: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the Fairlight handoff's layered-audio evidence.

    The master file's loudness is checked separately by ``audio_qc``.  This
    contract checks that the editorial handoff actually names and hashes the
    required VO/music/ambience/SFX outputs, and that an available Resolve
    readback exposes corresponding Fairlight tracks.  It never invents a
    stem when an output is missing.
    """

    root_path = Path(root).resolve()
    episode_path = Path(episode_root).resolve()
    audio_config = manifest.get("audio", {}) if isinstance(manifest.get("audio"), dict) else {}
    required = [str(item) for item in audio_config.get("required_layers", []) if str(item).strip()]
    if not required:
        return {
            "decision": "NOT_CONFIGURED",
            "required_layers": [],
            "layers": [],
            "errors": [],
            "fairlight": {"status": "NOT_CONFIGURED"},
        }

    if stems is None:
        stems_path = episode_path / "audio" / "final" / "stems.json"
        if not stems_path.exists():
            return {
                "decision": "FAIL",
                "required_layers": required,
                "layers": [],
                "errors": [f"missing final stems manifest: {stems_path}"],
                "fairlight": {"status": "NOT_CHECKED"},
            }
        try:
            stems = json.loads(stems_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "decision": "FAIL",
                "required_layers": required,
                "layers": [],
                "errors": [f"unreadable final stems manifest: {type(exc).__name__}"],
                "fairlight": {"status": "NOT_CHECKED"},
            }
    if not isinstance(stems, dict):
        return {
            "decision": "FAIL",
            "required_layers": required,
            "layers": [],
            "errors": ["final stems manifest must be a mapping"],
            "fairlight": {"status": "NOT_CHECKED"},
        }

    records = {
        str(item.get("role")): item
        for item in stems.get("stems", [])
        if isinstance(item, dict) and item.get("role")
    }
    errors: list[str] = []
    layers: list[dict[str, Any]] = []
    for role in required:
        record = records.get(role)
        if not record:
            errors.append(f"missing stem record: {role}")
            continue
        output = record.get("output")
        path = _resolve_audio_path(root_path, episode_path, output) if isinstance(output, str) else None
        item: dict[str, Any] = {"role": role, "path": str(path) if path else None, "exists": bool(path and path.is_file())}
        if path is None or not path.is_file():
            errors.append(f"missing stem output: {role}")
        else:
            actual_hash = sha256_file(path)
            item["sha256"] = actual_hash
            expected_hash = record.get("output_sha256")
            item["hash_matches"] = isinstance(expected_hash, str) and actual_hash == expected_hash
            if not item["hash_matches"]:
                errors.append(f"stem hash mismatch: {role}")
        sample_rate = record.get("sample_rate")
        if sample_rate is not None:
            try:
                item["sample_rate"] = int(sample_rate)
                if int(audio_config.get("sample_rate", manifest.get("master", {}).get("sample_rate", 0))) != item["sample_rate"]:
                    errors.append(f"stem sample rate mismatch: {role}")
            except (TypeError, ValueError):
                errors.append(f"invalid stem sample rate: {role}")
        layers.append(item)

    fairlight: dict[str, Any] = {"status": "NOT_FOUND", "track_count": 0, "tracks": []}
    readback_path = episode_path / "edit" / "resolve_production_readback.json"
    if readback_path.exists():
        try:
            readback = json.loads(readback_path.read_text(encoding="utf-8"))
            fairlight_value = readback.get("fairlight", {}) if isinstance(readback, dict) else {}
            tracks = fairlight_value.get("tracks", []) if isinstance(fairlight_value, dict) else []
            track_roles = {str(track.get("stem")) for track in tracks if isinstance(track, dict) and track.get("stem")}
            missing_tracks = [role for role in required if role not in track_roles]
            fairlight = {
                "status": "PASS" if not missing_tracks else "FAIL",
                "track_count": len(tracks),
                "tracks": tracks,
                "missing_tracks": missing_tracks,
            }
            errors.extend(f"missing Fairlight track: {role}" for role in missing_tracks)
        except (OSError, json.JSONDecodeError) as exc:
            fairlight = {"status": "FAIL", "track_count": 0, "tracks": [], "error": type(exc).__name__}
            errors.append("unreadable Resolve Fairlight readback")

    return {
        "decision": "PASS" if not errors else "FAIL",
        "required_layers": required,
        "layers": layers,
        "errors": errors,
        "fairlight": fairlight,
    }
