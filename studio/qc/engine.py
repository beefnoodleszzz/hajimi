"""Five-tier Fast QC engine.

Tier 0 stays mechanical, Tier 1 creates a proxy, Tier 1.5 detects scenes,
Tier 2 samples only 2–3 frames per scene and computes cheap metrics. Tier 3/4
are represented as explicit handoff fields; this module never sends every
frame to a VLM.
"""

from __future__ import annotations

import json
import re
import shutil
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import load_yaml, write_json
from ..db import StateStore
from ..manifest import assert_valid_manifest, load_manifest, manifest_hash, write_manifest
from ..media.audio import audio_qc, validate_sound_layers
from ..media.contact_sheet import build_contact_sheet
from ..media.hashing import sha256_file
from ..media.metrics import aggregate_metrics
from ..media.probe import duration_seconds, probe_media
from ..media.proxy import build_proxy
from ..media.sampling import extract_frame, extract_scene_samples
from ..media.scenes import detect_scenes
from ..paths import StudioPaths, project_root

QC_PROFILE_VERSION = "fast-qc-v2"
MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".wav", ".mp3", ".m4a", ".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _paths(root: str | Path | None = None) -> StudioPaths:
    return StudioPaths(Path(root).resolve() if root else project_root())


def _media_for_shot(
    shot_dir: Path,
    active_media: str | Path | None = None,
    *,
    base_dir: Path | None = None,
) -> Path | None:
    if active_media:
        configured = Path(active_media).expanduser()
        configured_candidates = [configured]
        if not configured.is_absolute():
            # Manifest paths are episode-relative, while older shot manifests
            # commonly used shot-relative paths. Resolve both conventions and
            # never silently fall back to a different candidate when the
            # manifest explicitly names an active asset.
            if base_dir is not None:
                configured_candidates.append(base_dir / configured)
            configured_candidates.append(shot_dir / configured)
        for candidate in configured_candidates:
            if candidate.is_file() and candidate.suffix.lower() in MEDIA_EXTENSIONS:
                return candidate.resolve()
        # An explicit active_media value is an integrity assertion.  Falling
        # back to an unrelated candidate would make the report describe a
        # different asset than the manifest names and could approve the wrong
        # render.
        return None
    candidates = [path for path in shot_dir.rglob("*") if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS]
    if not candidates:
        return None
    # The manifest's active media is preferred. When an older manifest has no
    # explicit path, production derivatives win over candidates/inputs and
    # storyboard cards remain a last-resort animatic fallback.
    candidates.sort(
        key=lambda path: (
            path.suffix.lower() not in VIDEO_EXTENSIONS,
            "production" not in path.parts,
            any(part in {"candidates", "input", "provenance"} for part in path.parts),
            str(path),
        )
    )
    return candidates[0]


def _config(root: Path) -> dict[str, Any]:
    path = root / "config" / "qc.yaml"
    if not path.exists():
        return {}
    try:
        return load_yaml(path)
    except Exception:
        return {}


def _write_metric_artifacts(work_dir: Path, scope: str, asset_hash: str, metrics: dict[str, Any], suspicious: list[dict[str, Any]]) -> dict[str, str]:
    key = f"{scope.replace('/', '_')}_{asset_hash[:12]}"
    metrics_path = work_dir / "metrics" / f"{key}.json"
    suspicious_path = work_dir / "suspicious" / f"{key}.json"
    write_json(metrics, metrics_path)
    write_json({"scope": scope, "asset_hash": asset_hash, "items": suspicious}, suspicious_path)
    return {"metrics": str(metrics_path), "suspicious": str(suspicious_path)}


def _is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def _tier0_summary(probe: dict[str, Any], qc_settings: dict[str, Any]) -> dict[str, Any]:
    """Expose the mechanical checks and threshold findings as data."""

    filters = probe.get("filters", {}) if isinstance(probe.get("filters"), dict) else {}
    video_events = filters.get("video_events", []) if isinstance(filters.get("video_events"), list) else []
    audio_events = filters.get("audio_events", []) if isinstance(filters.get("audio_events"), list) else []
    thresholds = qc_settings.get("thresholds", {}) if isinstance(qc_settings.get("thresholds"), dict) else {}
    freeze_seconds = float(thresholds.get("freeze_sec", 0.8) or 0.8)
    anomalies: list[dict[str, Any]] = []
    black_events = [line for line in video_events if "black_" in str(line)]
    freeze_events = [line for line in video_events if "freeze_" in str(line)]
    silence_events = [line for line in audio_events if "silence_" in str(line)]
    if black_events:
        anomalies.append({"type": "black_frames", "events": black_events})
    if freeze_events:
        anomalies.append({"type": "freeze", "minimum_seconds": freeze_seconds, "events": freeze_events})
    if silence_events:
        anomalies.append({"type": "silence", "threshold_db": thresholds.get("silence_db", -50), "events": silence_events})
    true_peak = filters.get("true_peak_dbfs")
    if isinstance(true_peak, (int, float)) and float(true_peak) > 0.0:
        anomalies.append({"type": "clipping", "true_peak_dbfs": true_peak})
    return {
        "decode": bool(probe.get("decode", {}).get("ok")),
        "blackdetect": {"ran": bool(video_events or probe.get("video")), "events": black_events},
        "freezedetect": {"ran": bool(video_events or probe.get("video")), "events": freeze_events, "minimum_seconds": freeze_seconds},
        "silencedetect": {"ran": bool(audio_events or probe.get("audio", {}).get("codec")), "events": silence_events},
        "ebur128_astats": {"ran": bool(audio_events or probe.get("audio", {}).get("codec")), "integrated_lufs": filters.get("integrated_lufs"), "true_peak_dbfs": true_peak},
        "anomalies": anomalies,
    }


def _locked_transcript(manifest: dict[str, Any], episode_root: Path) -> str | None:
    script_config = manifest.get("script", {})
    if not script_config.get("locked"):
        return None
    script_value = script_config.get("path")
    if not script_value:
        return None
    script_path = episode_root / str(script_value)
    if not script_path.exists():
        return None
    text = script_path.read_text(encoding="utf-8")
    marker = "## Full temporary voiceover"
    if marker not in text:
        return None
    section = text.split(marker, 1)[1]
    section = section.split("\n## ", 1)[0]
    lines = [re.sub(r"^>\s*", "", line).strip().strip("`") for line in section.splitlines()]
    transcript = " ".join(line for line in lines if line)
    return transcript or None


def run_media_qc(
    source: str | Path,
    *,
    scope: str,
    store: StateStore,
    work_dir: str | Path,
    profile_version: str | None = None,
    expected_transcript: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    source = Path(source).resolve()
    if not source.exists():
        return {"decision": "FAIL", "source": str(source), "error": "missing media", "cache_hit": False}
    asset_hash = sha256_file(source)
    project_root = store.path.parents[1]
    settings = _config(project_root)
    qc_settings = settings.get("qc", {})
    profile_version = profile_version or str(qc_settings.get("profile_version", QC_PROFILE_VERSION))
    if not force:
        cached = store.get_cached_qc(asset_hash, scope, profile_version)
        if cached:
            return cached

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    probe = probe_media(source)
    errors: list[str] = []
    warnings: list[str] = []
    tier0 = _tier0_summary(probe, qc_settings)
    if not probe.get("ok"):
        errors.append("Tier 0 technical/decode check failed")

    proxy_path: Path | None = None
    analysis_source = source
    if _is_video(source) and not errors:
        proxy_path = work_dir / "proxy" / f"{asset_hash[:16]}_540p.mp4"
        if not proxy_path.exists():
            try:
                proxy_cfg = qc_settings.get("proxy", {})
                build_proxy(
                    source,
                    proxy_path,
                    height=int(proxy_cfg.get("height", 540)),
                    bitrate=str(proxy_cfg.get("video_bitrate", "3M")),
                )
            except Exception as exc:
                warnings.append(f"proxy generation failed: {exc.__class__.__name__}; using source")
        if proxy_path.exists():
            analysis_source = proxy_path

    # Tier 0 is a hard gate. A corrupt media file must not proceed to visual
    # sampling or any future VLM stage.
    if errors:
        contact_path = work_dir / "contact_sheets" / f"{scope.replace('/', '_')}_{asset_hash[:12]}.jpg"
        build_contact_sheet([], contact_path)
        audio = audio_qc(source, expected_transcript=expected_transcript)
        result = {
            "schema_version": "qc-result-v1",
            "source": str(source),
            "asset_hash": asset_hash,
            "scope": scope,
            "profile_version": profile_version,
            "decision": "FAIL",
            "created_at": utc_now(),
            "tier0": {"probe": probe, "checks": tier0, "errors": errors},
            "tier1": {"proxy": None, "analysis_source": None},
            "tier1_5": {"scenes": [], "warnings": ["Tier 0 failed; visual analysis was not run"]},
            "tier2": {"samples": [], "metrics": {"frames": [], "frame_count": 0, "near_duplicate_pairs": []}, "suspicious": []},
            "tier3": {"status": "not_run", "reason": "Tier 0 failure"},
            "tier4": {"status": "blocked_by_tier0"},
            "audio": audio,
            "contact_sheet": str(contact_path),
            "cache_hit": False,
        }
        store.upsert_asset(asset_hash, source, "media", {"suffix": source.suffix.lower(), "scope": scope})
        store.put_qc(asset_hash, scope, profile_version, "FAIL", result)
        return result

    scenes, scene_warnings = detect_scenes(analysis_source)
    warnings.extend(scene_warnings)
    samples_dir = work_dir / "samples" / asset_hash[:16]
    frame_samples = []
    try:
        sampling = qc_settings.get("sampling", {})
        frame_samples = extract_scene_samples(
            analysis_source,
            scenes,
            samples_dir,
            short_threshold=float(sampling.get("short_threshold_sec", 1.2)),
            max_samples=int(sampling.get("max_samples_per_shot", 3)),
        )
    except Exception as exc:
        errors.append(f"frame sampling failed: {exc.__class__.__name__}")

    frame_paths = [sample.path for sample in frame_samples if sample.path.exists()]
    metrics = (
        aggregate_metrics(frame_paths, compute_optical_flow=_is_video(source))
        if frame_paths
        else {
            "frames": [],
            "frame_count": 0,
            "near_duplicate_pairs": [],
            "optical_flow": {"status": "not_run", "reason": "no sampled frames"},
        }
    )
    suspicious: list[dict[str, Any]] = []
    suspicious.extend(
        {"type": "tier0_anomaly", **anomaly}
        for anomaly in tier0.get("anomalies", [])
    )
    if _is_video(source) and len(metrics["near_duplicate_pairs"]) > 0:
        suspicious.append({"type": "near_duplicate_frames", "count": len(metrics["near_duplicate_pairs"])})
    if any(frame.get("laplacian_variance_approx", 0) < 2 for frame in metrics["frames"]):
        suspicious.append({"type": "possible_blur", "detail": "low edge variance in sampled frame"})

    audio = audio_qc(source, expected_transcript=expected_transcript)
    contact_path = work_dir / "contact_sheets" / f"{scope.replace('/', '_')}_{asset_hash[:12]}.jpg"
    contact_items = [(f"{scope} / {index + 1}", sample.path) for index, sample in enumerate(frame_samples)]
    build_contact_sheet(contact_items, contact_path)
    metric_artifacts = _write_metric_artifacts(work_dir, scope, asset_hash, metrics, suspicious)

    decision = "FAIL" if errors else ("REVIEW" if suspicious else "PASS")
    result: dict[str, Any] = {
        "schema_version": "qc-result-v1",
        "source": str(source),
        "asset_hash": asset_hash,
        "scope": scope,
        "profile_version": profile_version,
        "decision": decision,
        "created_at": utc_now(),
        "tier0": {"probe": probe, "checks": tier0, "errors": errors},
        "tier1": {"proxy": str(proxy_path) if proxy_path else None, "analysis_source": str(analysis_source)},
        "tier1_5": {"scenes": scenes, "warnings": warnings},
        "tier2": {"samples": [{"scene": s.scene_index, "position": s.position, "timestamp": s.timestamp, "path": str(s.path)} for s in frame_samples], "metrics": metrics, "suspicious": suspicious},
        "tier3": {"status": "not_run", "reason": "No VLM call is made by default; inspect contact sheet or suspicious frames."},
        "tier4": {"status": "pending_director_review"},
        "audio": audio,
        "contact_sheet": str(contact_path),
        "artifacts": metric_artifacts,
        "cache_hit": False,
    }
    store.upsert_asset(asset_hash, source, "media", {"suffix": source.suffix.lower(), "scope": scope})
    store.put_qc(asset_hash, scope, profile_version, decision, result)
    return result


def _sync_episode(paths: StudioPaths, episode_id: str, store: StateStore) -> tuple[dict[str, Any], Path]:
    manifest_path = paths.manifest(episode_id)
    manifest = load_manifest(manifest_path)
    assert_valid_manifest(manifest, manifest_path)
    store.sync_manifest(manifest, manifest_path, manifest_hash(manifest_path))
    return manifest, paths.episode(episode_id)


def run_shot_qc(episode_id: str, shot_id: str, *, root: str | Path | None = None, force: bool = False) -> dict[str, Any]:
    paths = _paths(root)
    store = StateStore(paths.state_db)
    manifest_path = paths.manifest(episode_id)
    manifest, episode_root = _sync_episode(paths, episode_id, store)
    shot = next((item for item in manifest.get("shots", []) if item.get("id") == shot_id), None)
    if shot is None:
        raise ValueError(f"Unknown shot {shot_id} in {episode_id}")
    source = _media_for_shot(
        episode_root / "shots" / shot_id,
        shot.get("active_media"),
        base_dir=episode_root,
    )
    if source is None:
        result = {"shot_id": shot_id, "decision": "FAIL", "scope": f"shot/{episode_id}/{shot_id}", "error": "no active media in shot directory", "cache_hit": False}
    else:
        result = run_media_qc(
            source,
            scope=f"shot/{episode_id}/{shot_id}",
            store=store,
            work_dir=episode_root / "qc",
            expected_transcript=None,
            force=force,
        )
    shot_status = "approved" if result.get("decision") == "PASS" else "qc_pending"
    if shot.get("status") == "rejected":
        shot_status = "rejected"
    shot["status"] = shot_status
    write_manifest(manifest, manifest_path)
    store.sync_manifest(manifest, manifest_path, manifest_hash(manifest_path))
    store.update_shot_status(episode_id, shot_id, shot_status)
    return result


def record_shot_review(
    root: str | Path,
    episode_id: str,
    shot_id: str,
    *,
    decision: str = "PASS",
    reviewer: str = "human",
    notes: str | None = None,
) -> dict[str, Any]:
    """Record an explicit director/human decision for a sampled shot.

    Automated ``REVIEW`` results are not silently promoted. This is the
    auditable gate for the human/director step. A Tier-0 ``FAIL`` can never be
    overridden here; it must be repaired and rechecked first.
    """

    normalized_decision = str(decision).upper()
    if normalized_decision not in {"PASS", "REJECT"}:
        raise ValueError("shot review decision must be PASS or REJECT")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("shot review requires a reviewer")
    paths = _paths(root)
    store = StateStore(paths.state_db)
    manifest, episode_root = _sync_episode(paths, episode_id, store)
    shot = next((item for item in manifest.get("shots", []) if str(item.get("id")) == shot_id), None)
    if shot is None:
        raise ValueError(f"Unknown shot {shot_id} in {episode_id}")
    report_path = episode_root / "qc" / "report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"shot QC report not found: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    evidence = next((item for item in report.get("shots", []) if str(item.get("shot_id")) == shot_id), None)
    if not isinstance(evidence, dict):
        raise RuntimeError(f"No automated QC evidence for {episode_id}/{shot_id}")
    if evidence.get("decision") == "FAIL":
        raise RuntimeError("Tier-0/automated FAIL cannot be human-overridden; repair and rerun QC")
    source = evidence.get("source")
    asset_hash = evidence.get("asset_hash")
    if not source or not asset_hash:
        raise RuntimeError("Shot QC evidence has no source/hash")
    source_path = Path(str(source)).expanduser()
    if not source_path.is_absolute():
        source_path = paths.root / source_path
    if not source_path.is_file() or sha256_file(source_path) != asset_hash:
        raise RuntimeError("Shot media changed after automated QC; rerun QC before review")
    review = {
        "status": normalized_decision,
        "reviewer": reviewer.strip(),
        "notes": notes,
        "recorded_at": utc_now(),
        "automated_decision": evidence.get("decision"),
        "asset_hash": asset_hash,
    }
    evidence["director_review"] = review
    evidence["reviewed_decision"] = normalized_decision
    shot["status"] = "approved" if normalized_decision == "PASS" else "rejected"
    report["shots"] = [evidence if str(item.get("shot_id")) == shot_id else item for item in report.get("shots", [])]
    report["reviewed_at"] = utc_now()
    write_json(report, report_path)
    write_manifest(manifest, paths.manifest(episode_id))
    store.sync_manifest(manifest, paths.manifest(episode_id), manifest_hash(paths.manifest(episode_id)))
    store.update_shot_status(episode_id, shot_id, shot["status"])
    return {
        "episode_id": episode_id,
        "shot_id": shot_id,
        "decision": normalized_decision,
        "review": review,
        "report": str(report_path),
    }


def _write_episode_report(episode_root: Path, report: dict[str, Any]) -> None:
    qc_root = episode_root / "qc"
    write_json(report, qc_root / "report.json")
    lines = [
        f"# Fast QC Report — {report['episode_id']}",
        "",
        f"Decision: **{report['decision']}**",
        f"Profile: `{report['profile_version']}`",
        "",
        "## Shot results",
        "",
    ]
    for item in report["shots"]:
        lines.append(f"- `{item['shot_id']}` — **{item['decision']}** — {item.get('source', 'no media')}")
    lines += ["", "## Policy", "", "The report samples proxy scenes and does not send a full video frame stream to a VLM."]
    (qc_root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _episode_qc_job(args: tuple[str, str, str, str, bool]) -> dict[str, Any]:
    source, scope, store_path, work_dir, force = args
    store = StateStore(store_path)
    return run_media_qc(source, scope=scope, store=store, work_dir=work_dir, force=force)


def run_episode_qc(episode_id: str, *, root: str | Path | None = None, force: bool = False) -> dict[str, Any]:
    paths = _paths(root)
    store = StateStore(paths.state_db)
    manifest, episode_root = _sync_episode(paths, episode_id, store)
    previous_report: dict[str, Any] = {}
    previous_report_path = episode_root / "qc" / "report.json"
    if previous_report_path.exists():
        try:
            loaded_report = json.loads(previous_report_path.read_text(encoding="utf-8"))
            if isinstance(loaded_report, dict):
                previous_report = loaded_report
        except (OSError, json.JSONDecodeError):
            previous_report = {}
    previous_evidence = {
        str(item.get("shot_id")): item
        for item in previous_report.get("shots", [])
        if isinstance(item, dict) and item.get("shot_id")
    }
    profile_version = str(_config(paths.root).get("qc", {}).get("profile_version", QC_PROFILE_VERSION))
    jobs: list[tuple[str, str, str, str, bool, str]] = []
    results_by_shot: dict[str, dict[str, Any]] = {}
    for shot in manifest.get("shots", []):
        shot_id = str(shot["id"])
        source = _media_for_shot(
            episode_root / "shots" / shot_id,
            shot.get("active_media"),
            base_dir=episode_root,
        )
        if source is None:
            results_by_shot[shot_id] = {"shot_id": shot_id, "decision": "FAIL", "source": None, "error": "no active media"}
        else:
            jobs.append((str(source), f"shot/{episode_id}/{shot_id}", str(paths.state_db), str(episode_root / "qc"), force, shot_id))
    worker_count = int(_config(paths.root).get("qc", {}).get("workers", {}).get("ffmpeg", 1) or 1)
    if jobs and worker_count > 1:
        with ProcessPoolExecutor(max_workers=min(worker_count, len(jobs))) as executor:
            computed = executor.map(_episode_qc_job, [job[:5] for job in jobs])
            for job, result in zip(jobs, computed):
                results_by_shot[job[5]] = {"shot_id": job[5], **result}
    else:
        for job in jobs:
            result = _episode_qc_job(job[:5])
            results_by_shot[job[5]] = {"shot_id": job[5], **result}
    results = [results_by_shot[str(shot["id"])] for shot in manifest.get("shots", [])]
    for result in results:
        shot_id = str(result["shot_id"])
        status = "approved" if result.get("decision") == "PASS" else "qc_pending"
        old_evidence = previous_evidence.get(shot_id, {})
        old_review = old_evidence.get("director_review")
        if (
            result.get("decision") == "REVIEW"
            and isinstance(old_review, dict)
            and old_review.get("status") == "PASS"
            and old_evidence.get("asset_hash") == result.get("asset_hash")
        ):
            result["director_review"] = old_review
            result["reviewed_decision"] = "PASS"
            status = "approved"
        for shot in manifest.get("shots", []):
            if str(shot.get("id")) == shot_id:
                if shot.get("status") == "rejected":
                    status = "rejected"
                shot["status"] = status
                break
    write_manifest(manifest, paths.manifest(episode_id))
    store.sync_manifest(manifest, paths.manifest(episode_id), manifest_hash(paths.manifest(episode_id)))
    contact_items: list[tuple[str, str | Path]] = []
    for result in results:
        contact = result.get("tier2", {}).get("samples", [])
        if contact:
            contact_items.append((result["shot_id"], contact[len(contact) // 2]["path"]))
    decision = "PASS" if results and all(item["decision"] in {"PASS", "REVIEW"} for item in results) else "FAIL"
    report = {
        "schema_version": "episode-qc-v1",
        "episode_id": episode_id,
        "profile_version": profile_version,
        "decision": decision,
        "created_at": utc_now(),
        "shots": results,
        "policy": {"proxy_first": True, "base_samples_per_scene": "2 for <1.2s, otherwise 3", "max_samples_per_shot": 3, "vlm_default": False, "workers": worker_count},
    }
    build_contact_sheet(contact_items, episode_root / "qc" / "contact_sheet.jpg")
    _write_episode_report(episode_root, report)
    return report


def _find_master(episode_root: Path, manifest: dict[str, Any] | None = None) -> Path | None:
    master_root = episode_root / "master"
    candidates: list[Path] = []
    configured = manifest.get("master", {}).get("path") if isinstance(manifest, dict) else None
    if configured:
        configured_path = Path(str(configured)).expanduser()
        if not configured_path.is_absolute():
            configured_path = episode_root / configured_path
        if configured_path.is_file() and configured_path.suffix.lower() in VIDEO_EXTENSIONS:
            return configured_path.resolve()
    for metadata_name in ("build.json", "resolve_render.json"):
        metadata_path = master_root / metadata_name
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                output = metadata.get("output")
                if output:
                    path = Path(output)
                    if not path.is_absolute():
                        path = episode_root.parent.parent / path if str(path).startswith("episodes/") else master_root / path
                    if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                        if metadata_name == "build.json" and metadata.get("master_type") == "resolve_master":
                            return path.resolve()
                        candidates.append(path)
            except (OSError, json.JSONDecodeError):
                pass
    candidates.extend(
        path
        for path in master_root.glob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS and "_rc" not in path.stem
    )
    candidates.sort(key=lambda path: ("_final" not in path.stem, "_v2" not in path.stem, str(path)))
    return candidates[0] if candidates else None


def _master_visual_samples(analysis_source: Path, duration: float, work_dir: Path, asset_hash: str, key_times: list[float]) -> dict[str, Any]:
    sample_root = work_dir / "master_samples" / asset_hash[:16]
    sample_root.mkdir(parents=True, exist_ok=True)
    # Some decoders reject a timestamp very close to EOF even when ffprobe
    # reports it as within the nominal duration. Keep every requested sample
    # inside a conservative decodable range.
    safe_end = max(0.0, float(duration) - 0.2)
    one_fps: list[dict[str, Any]] = []
    for index in range(max(1, int(duration) + 1)):
        timestamp = min(float(index), safe_end)
        destination = sample_root / f"fps1_{index:04d}.jpg"
        try:
            extract_frame(analysis_source, timestamp, destination)
            one_fps.append({"timestamp": timestamp, "path": str(destination)})
        except Exception as exc:
            one_fps.append({"timestamp": timestamp, "path": str(destination), "error": type(exc).__name__})
    keyframes: list[dict[str, Any]] = []
    for index, timestamp in enumerate(sorted({round(max(0.0, min(float(value), safe_end)), 3) for value in key_times})):
        destination = sample_root / f"key_{index:02d}.jpg"
        try:
            extract_frame(analysis_source, timestamp, destination)
            keyframes.append({"timestamp": timestamp, "path": str(destination)})
        except Exception as exc:
            keyframes.append({"timestamp": timestamp, "path": str(destination), "error": type(exc).__name__})
    build_contact_sheet(
        [(f"{timestamp['timestamp']:.2f}s", timestamp["path"]) for timestamp in one_fps if "error" not in timestamp],
        work_dir / "master_contact_sheet_1fps.jpg",
        columns=5,
        cell_width=220,
    )
    return {
        "source": str(analysis_source),
        "one_fps_count": len(one_fps),
        "one_fps": one_fps,
        "keyframes": keyframes,
        "contact_sheet": str(work_dir / "master_contact_sheet_1fps.jpg"),
    }


def run_master_qc(episode_id: str, *, root: str | Path | None = None, force: bool = False) -> dict[str, Any]:
    paths = _paths(root)
    store = StateStore(paths.state_db)
    manifest, episode_root = _sync_episode(paths, episode_id, store)
    master = _find_master(episode_root, manifest)
    if master is None:
        report = {"schema_version": "master-qc-v1", "episode_id": episode_id, "decision": "FAIL", "error": "master file not found", "created_at": utc_now()}
        write_json(report, episode_root / "qc" / "master_report.json")
        return report
    result = run_media_qc(
        master,
        scope=f"master/{episode_id}",
        store=store,
        work_dir=episode_root / "qc",
        expected_transcript=_locked_transcript(manifest, episode_root),
        force=force,
    )
    expected = manifest.get("master", {})
    video = result.get("tier0", {}).get("probe", {}).get("video", {})
    audio_stream = result.get("tier0", {}).get("probe", {}).get("audio", {})
    actual_fps = _fps_value(video.get("fps"))
    geometry = {
        "expected_width": expected.get("width"),
        "expected_height": expected.get("height"),
        "actual_width": video.get("width"),
        "actual_height": video.get("height"),
        "expected_fps": expected.get("fps"),
        "actual_fps": actual_fps,
        "expected_sample_rate": expected.get("sample_rate"),
        "actual_sample_rate": audio_stream.get("sample_rate"),
        "pass": (
            video.get("width") == expected.get("width")
            and video.get("height") == expected.get("height")
            and actual_fps is not None
            and abs(actual_fps - float(expected.get("fps", 0))) <= 0.01
            and str(audio_stream.get("sample_rate")) == str(expected.get("sample_rate"))
        ),
    }
    audio_target = manifest.get("audio", {})
    filters = result.get("tier0", {}).get("probe", {}).get("filters", {})
    integrated_lufs = filters.get("integrated_lufs")
    true_peak_dbfs = filters.get("true_peak_dbfs")
    target_lufs = float(audio_target.get("target_lufs", -14))
    peak_limit = float(audio_target.get("true_peak_max_db", -1.0))
    loudness = {
        "target_lufs": target_lufs,
        "actual_lufs": integrated_lufs,
        "true_peak_max_dbfs": peak_limit,
        "actual_true_peak_dbfs": true_peak_dbfs,
        "pass": integrated_lufs is not None and abs(integrated_lufs - target_lufs) <= 1.5 and true_peak_dbfs is not None and true_peak_dbfs <= peak_limit + 0.2,
    }
    duration = duration_seconds(result.get("tier0", {}).get("probe", {}))
    hero = next((shot for shot in manifest.get("shots", []) if shot.get("id") == manifest.get("creative", {}).get("hero_shot")), {})
    visual_samples = _master_visual_samples(
        Path(result.get("tier1", {}).get("analysis_source", master)),
        duration,
        episode_root / "qc",
        result.get("asset_hash", sha256_file(master)),
        [0.0, float(manifest.get("creative", {}).get("time_to_anomaly_sec", 0.0)), float(hero.get("time_start", 0.0)), float(hero.get("time_end", 0.0)), max(0.0, duration - 0.2)],
    )
    width = int(expected.get("width", 0) or 0)
    height = int(expected.get("height", 0) or 0)
    safe_zone = {
        "status": "PASS" if width > 0 and height > 0 else "FAIL",
        "ocr_free": True,
        "subtitle_rect": {"x": round(width * 0.12), "y": round(height * 0.72), "width": round(width * 0.76), "height": round(height * 0.12)},
        "story_typography_rect": {"x": round(width * 0.10), "y": round(height * 0.10), "width": round(width * 0.72), "height": round(height * 0.70)},
    }
    asr = result.get("audio", {}).get("asr", {})
    sound_layers = validate_sound_layers(paths.root, episode_root, manifest)
    sound_layers_pass = sound_layers.get("decision") in {"PASS", "NOT_CONFIGURED"}
    asr_diff = asr.get("diff") if isinstance(asr, dict) else None
    asr_review = bool(
        isinstance(asr_diff, dict)
        and asr_diff.get("decision") != "PASS"
        and (
            float(asr_diff.get("coverage", 0.0) or 0.0) < 0.98
            or bool(asr_diff.get("missing_key_tokens"))
        )
    )
    if (
        result.get("decision") not in {"PASS", "REVIEW"}
        or not geometry["pass"]
        or not loudness["pass"]
        or not sound_layers_pass
    ):
        decision = "FAIL"
    elif asr_review:
        decision = "REVIEW"
    else:
        decision = "PASS"
    report = {
        "schema_version": "master-qc-v1",
        "episode_id": episode_id,
        "decision": decision,
        "created_at": utc_now(),
        "master": str(master),
        "master_sha256": sha256_file(master),
        "technical": result,
        "geometry": geometry,
        "loudness": loudness,
        "audio_layers": sound_layers,
        "visual_samples": visual_samples,
        "subtitle_safe_zone": safe_zone,
        "asr": result.get("audio", {}).get("asr", {"status": "not_run"}),
        "human_review": {"status": "PENDING", "required": True, "instruction": "Complete playback once and record explicit human approval."},
        "human_review_recorded": False,
    }
    write_json(report, episode_root / "qc" / "master_report.json")
    master_lines = [
        f"# Master QC — {episode_id}",
        "",
        f"Decision: **{decision}**",
        f"Master: `{master}`",
        "",
        "Automated checks are complete. A complete human playback must be recorded before private upload.",
    ]
    (episode_root / "qc" / "master_report.md").write_text("\n".join(master_lines) + "\n", encoding="utf-8")
    return report


def record_human_playback(root: str | Path, episode_id: str, *, reviewer: str = "human", notes: str | None = None) -> dict[str, Any]:
    """Record an explicit human playback approval after the real review."""

    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("human playback requires a reviewer")
    paths = _paths(root)
    report_path = paths.episode(episode_id) / "qc" / "master_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"master QC report not found: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("decision") != "PASS":
        raise RuntimeError("Cannot record human playback until automated master QC is PASS")
    master_path = Path(report.get("master", ""))
    if not master_path.exists() or report.get("master_sha256") != sha256_file(master_path):
        raise RuntimeError("Master changed after automated QC; rerun master QC before human playback")
    report["human_review"] = {"status": "PASS", "reviewer": reviewer.strip(), "notes": notes, "confirmed_at": utc_now()}
    report["human_review_recorded"] = True
    write_json(report, report_path)
    return report
