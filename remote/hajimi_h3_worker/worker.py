"""Serial MiniMax H3 renderer. Creative decisions stay in local Hajimi."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL
from .comfy_client import ComfyClient
from .contract import JOB_RE, safe_job_id, sha256_file, validate_job_directory
from .media_probe import summarize, tool_version

RUNTIME = Path(os.environ.get("HAJIMI_H3_RUNTIME", "/root/autodl-tmp/hajimi-h3-runtime")).resolve()
COMFY_ROOT = Path(os.environ.get("HAJIMI_COMFYUI_ROOT", "/root/ComfyUI")).resolve()
MODEL_ROOT = Path(os.environ.get("HAJIMI_H3_MODEL_ROOT", "/root/autodl-tmp/ComfyUI-H3-models")).resolve()
WORKFLOW_ROOT = Path(__file__).resolve().parents[1] / "workflows"
COMFY_URL = os.environ.get("HAJIMI_COMFY_ENDPOINT", "http://127.0.0.1:8188")
PYTHON = os.environ.get("HAJIMI_H3_PYTHON", "/root/miniconda3/bin/python")
FPS = 24
MODELS = {
    "fl2va": "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "ref2va": "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    "text_encoder": "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "video_vae": "vae/minimax_h3_video_vae_fp16.safetensors",
    "audio_vae": "vae/minimax_h3_audio_vae_fp32.safetensors",
}
COMFY_MODELS = {
    "fl2va": "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "ref2va": "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    "text_encoder": "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "video_vae": "vae/minimax_h3_video_vae_fp16.safetensors",
    "audio_vae": "vae/minimax_h3_audio_vae_fp32.safetensors",
}
REQUIRED_NODES = {
    "UNETLoader", "CLIPLoader", "VAELoader", "MiniMaxH3ImageToVideo",
    "MiniMaxH3ReferenceToVideo", "RandomNoise", "CreateVideo", "SaveVideo",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _gpu() -> dict[str, Any]:
    found = shutil.which("nvidia-smi")
    if found:
        try:
            result = subprocess.run(
                [found, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            line = next((x.strip() for x in result.stdout.splitlines() if x.strip()), "")
            if result.returncode == 0 and line:
                fields = [x.strip() for x in line.split(",")]
                if len(fields) >= 3:
                    try:
                        return {"available": True, "name": fields[0], "vram_mb": int(float(fields[1])), "driver": fields[2]}
                    except ValueError:
                        pass
        except (OSError, subprocess.SubprocessError):
            # AutoDL no-card containers may expose an empty nvidia-smi stub.
            pass
    try:
        import torch

        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            props = torch.cuda.get_device_properties(0)
            return {"available": True, "name": props.name, "vram_mb": int(props.total_memory // (1024 * 1024)), "driver": None}
        return {"available": False, "name": None, "vram_mb": None, "driver": None}
    except (ImportError, RuntimeError) as exc:
        return {"available": False, "name": None, "vram_mb": None, "driver": None, "error": str(exc)}


def _torch() -> dict[str, Any]:
    try:
        import torch

        return {"version": torch.__version__, "cuda": torch.version.cuda, "cuda_available": bool(torch.cuda.is_available())}
    except (ImportError, RuntimeError) as exc:
        return {"version": None, "cuda": None, "cuda_available": False, "error": str(exc)}


def _comfy_commit() -> str | None:
    if not (COMFY_ROOT / ".git").exists():
        return None
    result = subprocess.run(["git", "-C", str(COMFY_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=8, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _custom_nodes() -> list[dict[str, Any]]:
    root = COMFY_ROOT / "custom_nodes"
    if not root.is_dir():
        return []
    result = []
    for path in sorted(root.iterdir()):
        if path.name.startswith(".") or path.name == "__pycache__":
            continue
        if path.is_dir() or path.is_symlink():
            commit = None
            if (path / ".git").exists():
                probe = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=8, check=False)
                commit = probe.stdout.strip() if probe.returncode == 0 else None
            result.append({"name": path.name, "commit": commit})
    return result


def _file_identity(relative: str) -> dict[str, Any]:
    path = MODEL_ROOT / relative
    if not path.is_file():
        return {"filename": path.name, "path": str(path), "present": False}
    stat = path.stat()
    return {"filename": path.name, "path": str(path), "present": True, "size_bytes": stat.st_size}


def _workflow_identity(workflow_id: str) -> dict[str, Any]:
    path = WORKFLOW_ROOT / f"{workflow_id}.json"
    if not path.is_file():
        return {"present": False, "path": str(path)}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return {"present": isinstance(value, dict) and isinstance(value.get("prompt"), dict), "workflow_version": value.get("workflow_version"), "node_count": len(value.get("prompt", {}))}
    except (OSError, json.JSONDecodeError):
        return {"present": False, "path": str(path)}


def doctor() -> dict[str, Any]:
    gpu = _gpu()
    torch = _torch()
    models = {name: _file_identity(relative) for name, relative in MODELS.items()}
    comfy_models = {name: (COMFY_ROOT / "models" / relative).is_file() for name, relative in COMFY_MODELS.items()}
    workflows = {name: _workflow_identity(name) for name in ("h3_i2va_api", "h3_fl2va_api", "h3_ref2va_api")}
    checks: dict[str, str] = {
        "gpu": "PASS" if gpu.get("available") and torch.get("cuda_available") else "FAIL",
        "h3_model": "PASS" if all(item.get("present") for item in models.values()) else "FAIL",
        "comfyui_models": "PASS" if all(comfy_models.values()) else "FAIL",
        "h3_workflows": "PASS" if all(item.get("present") for item in workflows.values()) else "FAIL",
        "required_nodes": "FAIL",
        "comfyui_api": "FAIL",
        "native_audio": "PASS" if shutil.which("ffmpeg") and shutil.which("ffprobe") else "FAIL",
        "protocol": "PASS" if PROTOCOL == "hajimi-h3-remote-v1" else "FAIL",
    }
    comfy: dict[str, Any] = {"endpoint": COMFY_URL, "reachable": False}
    try:
        client = ComfyClient(COMFY_URL, timeout=5)
        stats = client.system_stats()
        info = client.object_info()
        comfy.update({"reachable": True, "system_stats": stats})
        missing = sorted(REQUIRED_NODES - set(info))
        comfy["missing_nodes"] = missing
        checks["comfyui_api"] = "PASS"
        checks["required_nodes"] = "PASS" if not missing else "FAIL"
    except Exception as exc:
        comfy["error"] = str(exc)
    status = "READY" if all(value == "PASS" for value in checks.values()) else "BLOCKED"
    return {
        "schema_version": PROTOCOL,
        "backend": "minimax_h3",
        "status": status,
        "checked_at": _now(),
        "checks": checks,
        "gpu": gpu,
        "torch": torch,
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "cuda_runtime": torch.get("cuda"),
        "comfyui": {**comfy, "commit": _comfy_commit()},
        "custom_nodes": _custom_nodes(),
        "models": models,
        "comfyui_model_paths": comfy_models,
        "workflows": workflows,
        "ffmpeg": tool_version("ffmpeg"),
        "ffprobe": tool_version("ffprobe"),
    }


def _shape(aspect_ratio: str) -> tuple[int, int]:
    return {"9:16": (768, 1344), "16:9": (1344, 768), "1:1": (768, 768)}[aspect_ratio]


def _frame_count(duration: float) -> int:
    value = max(5, round(duration * FPS))
    return value + (5 - value % 17) % 17


def _stage_assets(job_dir: Path, job: dict[str, Any], comfy_input: Path) -> dict[str, str]:
    staged: dict[str, str] = {}
    inputs = job["inputs"]
    declared = [inputs.get("first_frame"), inputs.get("last_frame"), *inputs.get("reference_images", [])]
    for relative in filter(None, declared):
        source = job_dir / relative
        name = f"h3_{job['job_id']}_{source.name}"
        destination = comfy_input / name
        if destination.exists() and sha256_file(destination) != job["input_sha256"][relative]:
            raise FileExistsError(f"ComfyUI input staging path collision for {name}")
        if not destination.exists():
            shutil.copy2(source, destination)
        staged[relative] = name
    return staged


def _prepare_workflow(job: dict[str, Any], candidate_index: int, staged: dict[str, str]) -> tuple[dict[str, Any], str, int]:
    mode = job["mode"]
    workflow_id = "h3_ref2va_api" if mode == "ref2va" else f"h3_{mode}_api"
    workflow_path = WORKFLOW_ROOT / f"{workflow_id}.json"
    wrapper = json.loads(workflow_path.read_text(encoding="utf-8"))
    api = json.loads(json.dumps(wrapper["prompt"]))
    workflow_version = int(wrapper.get("workflow_version", 1))
    width, height = _shape(job["aspect_ratio"])
    length = _frame_count(float(job["duration_sec"]))
    seed = secrets.randbelow(2**63 - 1)
    h3_type = "MiniMaxH3ReferenceToVideo" if mode == "ref2va" else "MiniMaxH3ImageToVideo"
    h3_nodes = [(node_id, value) for node_id, value in api.items() if value.get("class_type") == h3_type]
    if len(h3_nodes) != 1:
        raise ValueError(f"{workflow_id} must contain exactly one {h3_type} node")
    _, h3_node = h3_nodes[0]
    inputs = h3_node["inputs"]
    inputs.update({"prompt": job["prompt"], "width": width, "height": height, "length": length})
    if mode == "ref2va":
        references = job["inputs"].get("reference_images", [])
        if len(references) > 9:
            raise ValueError("ref2va supports at most 9 reference images")
        for index, relative in enumerate(references):
            key = f"ref_images.ref_image_{index}"
            inputs[key] = [str(900 + index), 0]
            loader = api.get(str(900 + index))
            if not loader or loader.get("class_type") != "LoadImage":
                raise ValueError(f"fixed workflow is missing reference loader {index}")
            loader["inputs"]["image"] = staged[relative]
        for key in list(inputs):
            if key.startswith("ref_images.ref_image_") and key not in {f"ref_images.ref_image_{i}" for i in range(len(references))}:
                inputs.pop(key)
        diffusion = MODELS["ref2va"]
    else:
        first = job["inputs"]["first_frame"]
        api["900"]["inputs"]["image"] = staged[first]
        inputs["first_frame"] = ["900", 0]
        if mode == "fl2va":
            last = job["inputs"]["last_frame"]
            api["901"]["inputs"]["image"] = staged[last]
            inputs["last_frame"] = ["901", 0]
        else:
            inputs.pop("last_frame", None)
        diffusion = MODELS["fl2va"]
    for _, node in api.items():
        if node.get("class_type") == "UNETLoader":
            node["inputs"]["unet_name"] = Path(diffusion).name
        elif node.get("class_type") == "CLIPLoader":
            node["inputs"]["clip_name"] = Path(MODELS["text_encoder"]).name
        elif node.get("class_type") == "VAELoader":
            field = "vae_name" if "vae_name" in node.get("inputs", {}) else ""
            if field:
                node["inputs"][field] = Path(MODELS["video_vae"]).name
        elif node.get("class_type") == "RandomNoise":
            node["inputs"]["noise_seed"] = seed
            node["inputs"]["noise_mode"] = "fixed"
        elif node.get("class_type") == "SaveVideo":
            node["inputs"]["filename_prefix"] = f"hajimi_h3/{job['job_id']}/candidate_{candidate_index:02d}"
    return api, workflow_id, seed


def _video_outputs(history: dict[str, Any]) -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []
    for node in history.get("outputs", {}).values():
        if not isinstance(node, dict):
            continue
        for key in ("videos", "gifs", "images"):
            value = node.get(key)
            if isinstance(value, list):
                videos.extend(item for item in value if isinstance(item, dict) and item.get("filename"))
    return videos


def _remove_comfy_output(item: dict[str, Any]) -> None:
    if item.get("type", "output") not in {"output", "temp"}:
        return
    filename, subfolder = item.get("filename"), item.get("subfolder", "")
    if not isinstance(filename, str) or not filename or Path(filename).name != filename:
        return
    base = (COMFY_ROOT / ("output" if item.get("type", "output") == "output" else "temp")).resolve()
    path = (base / str(subfolder) / filename)
    if path.is_symlink():
        return
    resolved = path.resolve()
    if not resolved.is_relative_to(base) or not resolved.is_file():
        return
    resolved.unlink()
    parent = resolved.parent
    while parent != base:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def _candidate(job: dict[str, Any], index: int, client: ComfyClient, history: dict[str, Any], result_dir: Path, workflow_id: str, workflow_version: int, seed: int) -> dict[str, Any]:
    outputs = _video_outputs(history)
    if not outputs:
        raise RuntimeError("ComfyUI completed without a video output")
    candidate_id = f"{job['job_id']}_candidate_{index:02d}"
    video_name = f"candidate_{index:02d}.mp4"
    video_path = result_dir / video_name
    try:
        client.download_view(outputs[0], video_path)
        machine = summarize(video_path)
    finally:
        _remove_comfy_output(outputs[0])
    metadata = {
        "schema_version": PROTOCOL,
        "backend": "comfyui_minimax_h3",
        "workflow": workflow_id,
        "workflow_id": workflow_id,
        "workflow_version": workflow_version,
        "candidate_id": candidate_id,
        "filename": video_name,
        "sha256": sha256_file(video_path),
        **machine,
        "generation_parameters": {
            "mode": job["mode"], "seed": seed, "duration_requested_sec": job["duration_sec"],
            "frame_count": _frame_count(float(job["duration_sec"])), "width": machine["width"], "height": machine["height"],
        },
        "h3_model_identity": {
            "diffusion_model": _file_identity(MODELS["ref2va"] if job["mode"] == "ref2va" else MODELS["fl2va"]),
            "text_encoder": _file_identity(MODELS["text_encoder"]),
            "video_vae": _file_identity(MODELS["video_vae"]),
            "audio_vae": _file_identity(MODELS["audio_vae"]),
        },
        "comfy_prompt_id": history.get("prompt_id"),
        "comfy_output": outputs[0],
    }
    _write_json(result_dir / f"candidate_{index:02d}.json", metadata)
    return {"candidate_id": candidate_id, "filename": video_name, "metadata_file": f"candidate_{index:02d}.json", "sha256": metadata["sha256"]}


def _run_job(job_dir: Path) -> dict[str, Any]:
    try:
        job = validate_job_directory(job_dir)
    except Exception as exc:
        if job_dir.parent.name == "running" and job_dir.is_dir():
            failed_dir = RUNTIME / "jobs" / "failed" / job_dir.name
            _write_json(job_dir / "state.json", {"job_id": job_dir.name, "status": "FAILED", "stage": "validation", "error": str(exc), "failed_at": _now()})
            failed_dir.parent.mkdir(parents=True, exist_ok=True)
            if failed_dir.exists():
                raise FileExistsError(f"preserving existing failed job directory: {failed_dir}") from exc
            shutil.move(str(job_dir), str(failed_dir))
        raise
    job_id = safe_job_id(job["job_id"])
    running_dir = RUNTIME / "jobs" / "running" / job_id
    complete_dir = RUNTIME / "jobs" / "complete" / job_id
    failed_dir = RUNTIME / "jobs" / "failed" / job_id
    if job_dir.resolve() != running_dir.resolve():
        raise ValueError("worker can only run jobs from jobs/running/<job_id>")
    if complete_dir.exists() or failed_dir.exists():
        raise FileExistsError(f"preserving existing result for H3 job {job_id}")
    with (RUNTIME / "jobs" / ".gpu.lock").open("w", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state_file = running_dir / "state.json"
        _write_json(state_file, {"job_id": job_id, "status": "RUNNING", "started_at": _now()})
        result_dir = RUNTIME / "jobs" / "work" / job_id
        staged_names: dict[str, str] = {}
        stage = "preparing"
        try:
            if result_dir.exists():
                raise FileExistsError(f"H3 temporary output already exists for {job_id}")
            result_dir.mkdir(parents=True)
            stage = "staging"
            client = ComfyClient(COMFY_URL, timeout=int(os.environ.get("HAJIMI_H3_JOB_TIMEOUT", "7200")))
            comfy_input = COMFY_ROOT / "input"
            comfy_input.mkdir(parents=True, exist_ok=True)
            staged_names = _stage_assets(running_dir, job, comfy_input)
            candidates: list[dict[str, Any]] = []
            for index in range(1, job["candidate_count"] + 1):
                stage = "comfy_submit"
                workflow, workflow_id, seed = _prepare_workflow(job, index, staged_names)
                prompt_id = client.submit(workflow)
                stage = "sampling"
                history = client.wait(prompt_id)
                history["prompt_id"] = prompt_id
                stage = "decode_probe"
                candidates.append(_candidate(job, index, client, history, result_dir, workflow_id, 1, seed))
                stage = "staging"
            result = {
                "schema_version": PROTOCOL,
                "backend": "comfyui_minimax_h3",
                "job_id": job_id,
                "episode_id": job["episode_id"],
                "shot_id": job["shot_id"],
                "status": "COMPLETE",
                "completed_at": _now(),
                "candidates": candidates,
            }
            _write_json(result_dir / "result.json", result)
            _write_json(running_dir / "state.json", {"job_id": job_id, "status": "COMPLETE", "completed_at": _now()})
            complete_dir.parent.mkdir(parents=True, exist_ok=True)
            if complete_dir.exists():
                raise FileExistsError(f"completed job directory already exists: {job_id}")
            shutil.move(str(result_dir), str(complete_dir))
            shutil.rmtree(running_dir)
            return result
        except Exception as exc:
            _write_json(running_dir / "state.json", {"job_id": job_id, "status": "FAILED", "stage": stage, "error": str(exc), "failed_at": _now()})
            if result_dir.exists():
                shutil.rmtree(result_dir)
            failed_dir.parent.mkdir(parents=True, exist_ok=True)
            if failed_dir.exists():
                raise FileExistsError(f"preserving existing failed job directory: {failed_dir}") from exc
            shutil.move(str(running_dir), str(failed_dir))
            raise
        finally:
            for filename in staged_names.values():
                (COMFY_ROOT / "input" / filename).unlink(missing_ok=True)


def _job_dirs() -> list[tuple[str, Path]]:
    base = RUNTIME / "jobs"
    return [(state, base / state) for state in ("inbox", "running", "complete", "failed")]


def _status(job_id: str | None = None, episode_id: str | None = None, shot_id: str | None = None) -> dict[str, Any]:
    result = []
    for directory_state, directory in _job_dirs():
        if not directory.is_dir():
            continue
        for child in sorted(directory.iterdir()):
            if not child.is_dir() or not JOB_RE.fullmatch(child.name) or (job_id and child.name != job_id):
                continue
            job_path = child / "job.json"
            if directory_state == "complete":
                job_path = child / "result.json"
            if not job_path.is_file():
                continue
            try:
                job = json.loads(job_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if episode_id and job.get("episode_id") != episode_id:
                continue
            if shot_id and job.get("shot_id") != shot_id:
                continue
            state_file = child / "state.json"
            state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
            status = state.get("status") or {"inbox": "QUEUED", "running": "QUEUED", "complete": "COMPLETE", "failed": "FAILED"}[directory_state]
            entry = {"job_id": child.name, "episode_id": job.get("episode_id"), "shot_id": job.get("shot_id"), "status": status}
            if state.get("stage"):
                entry["stage"] = state["stage"]
            if state.get("error"):
                entry["error"] = state["error"]
            result.append(entry)
    return {"schema_version": PROTOCOL, "jobs": result}


def _submit(job_dir: Path) -> dict[str, Any]:
    job = validate_job_directory(job_dir)
    job_id = job["job_id"]
    inbox = RUNTIME / "jobs" / "inbox" / job_id
    running = RUNTIME / "jobs" / "running" / job_id
    complete = RUNTIME / "jobs" / "complete" / job_id
    failed = RUNTIME / "jobs" / "failed" / job_id
    if complete.exists():
        return {"schema_version": PROTOCOL, "job_id": job_id, "status": "COMPLETE"}
    if running.exists() or failed.exists():
        state = running / "state.json" if running.exists() else failed / "state.json"
        value = json.loads(state.read_text()) if state.exists() else {}
        return {"schema_version": PROTOCOL, "job_id": job_id, "status": value.get("status", "RUNNING")}
    if job_dir.resolve() != inbox.resolve():
        raise ValueError("submit path must be jobs/inbox/<job_id>")
    running.parent.mkdir(parents=True, exist_ok=True)
    inbox.rename(running)
    _write_json(running / "state.json", {"job_id": job_id, "status": "QUEUED", "submitted_at": _now()})
    (RUNTIME / "logs").mkdir(parents=True, exist_ok=True)
    log_path = RUNTIME / "logs" / f"{job_id}.log"
    with log_path.open("ab") as log:
        subprocess.Popen(
            [PYTHON, "worker.py", "run", "--job-dir", str(running)],
            cwd=RUNTIME / "worker",
            env={**os.environ, "PYTHONPATH": str(RUNTIME / "worker")},
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    return {"schema_version": PROTOCOL, "job_id": job_id, "status": "SUBMITTED"}


def _cleanup(job_id: str, expected_hash: str, local_import_verified: bool) -> dict[str, Any]:
    job_id = safe_job_id(job_id)
    result_dir = RUNTIME / "jobs" / "complete" / job_id
    result_file = result_dir / "result.json"
    if not result_file.is_file():
        raise FileNotFoundError("completed result does not exist")
    if not local_import_verified:
        raise ValueError("cleanup requires confirmation that local import and hash verification succeeded")
    actual = sha256_file(result_file)
    if actual != expected_hash:
        raise ValueError("pull confirmation hash does not match remote result.json")
    shutil.rmtree(result_dir)
    return {"schema_version": PROTOCOL, "job_id": job_id, "status": "CLEANED", "result_sha256": actual}


def _write_environment_report() -> Path:
    report = doctor()
    report["storage"] = {
        "runtime_root": str(RUNTIME),
        "model_root": str(MODEL_ROOT),
        "comfyui_root": str(COMFY_ROOT),
        "autodl_tmp_mounted": os.path.ismount("/root/autodl-tmp"),
        "autodl_fs_exists": Path("/root/autodl-fs").exists(),
        "autodl_fs_mounted": os.path.ismount("/root/autodl-fs"),
    }
    path = RUNTIME / "environment.json"
    _write_json(path, report)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hajimi_h3_worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.add_argument("--write-report", action="store_true")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("job_dir", nargs="?")
    run_parser.add_argument("--job-dir", dest="job_dir_option")
    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("--job-dir", required=True)
    submit_parser.add_argument("--json", action="store_true")
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("job_id", nargs="?")
    status_parser.add_argument("--job-id", dest="job_id_option")
    status_parser.add_argument("--episode-id")
    status_parser.add_argument("--shot-id")
    status_parser.add_argument("--json", action="store_true")
    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("job_id", nargs="?")
    cleanup_parser.add_argument("--job-id", dest="job_id_option")
    cleanup_parser.add_argument("--confirm-result-sha256", required=True)
    cleanup_parser.add_argument("--local-import-verified", action="store_true", required=True)
    cleanup_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
            if args.write_report:
                result["environment_report"] = str(_write_environment_report())
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["status"] == "READY" else 2
        if args.command == "submit":
            result = _submit(Path(args.job_dir).resolve())
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.command == "run":
            job_dir = args.job_dir_option or args.job_dir
            if not job_dir:
                raise ValueError("run requires a job directory")
            result = _run_job(Path(job_dir).resolve())
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.command == "status":
            print(json.dumps(_status(args.job_id_option or args.job_id, args.episode_id, args.shot_id), ensure_ascii=False))
            return 0
        if args.command == "cleanup":
            job_id = args.job_id_option or args.job_id
            if not job_id:
                raise ValueError("cleanup requires a job_id")
            result = _cleanup(job_id, args.confirm_result_sha256, args.local_import_verified)
            print(json.dumps(result, ensure_ascii=False))
            return 0
    except Exception as exc:
        print(json.dumps({"schema_version": PROTOCOL, "status": "FAILED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 2
