"""Local CLI-facing operations for the ComfyUI MiniMax H3 remote worker."""

from __future__ import annotations

import json
import shutil
import shlex
import subprocess
from pathlib import Path
from typing import Any

from ..config import dump_yaml
from ..manifest import EPISODE_RE, SHOT_RE, assert_valid_manifest, load_manifest
from .contract import H3_JOB_SCHEMA_VERSION, JOB_ID_RE, assert_valid_h3_job, prepare_h3_jobs, sha256_file
from .result import import_h3_result, select_h3_candidate
from .ssh_transport import (
    load_remote_h3_config,
    pull_job_result,
    resolve_connection,
    run_remote,
    ssh_command,
    transfer_job,
)


def _episode_directory(root: Path, episode_id: str) -> Path:
    if not isinstance(episode_id, str) or not EPISODE_RE.fullmatch(episode_id):
        raise ValueError("episode_id is invalid")
    directory = (root / "episodes" / episode_id).resolve()
    if not directory.is_relative_to(root):
        raise ValueError("episode path escapes the project root")
    return directory


def _has_symlink_component(base: Path, target: Path) -> bool:
    try:
        relative = target.relative_to(base)
    except ValueError:
        return True
    cursor = base
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return True
    return False


def _remote_json(config: dict[str, Any], connection: dict[str, Any], arguments: list[str]) -> dict[str, Any]:
    completed = run_remote(config, connection, arguments, timeout=180)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip()[-2000:] or "remote H3 worker command failed")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Remote H3 worker returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Remote H3 worker response must be a JSON object")
    return value


def h3_doctor(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    checks: list[dict[str, Any]] = []
    try:
        config = load_remote_h3_config(root)
    except (OSError, ValueError, RuntimeError) as exc:
        return {"status": "FAIL", "checks": [{"name": "configuration", "status": "FAIL", "detail": str(exc)}]}
    checks.append({"name": "configuration", "status": "PASS", "detail": "non-secret settings valid; ComfyUI binds to remote localhost"})
    try:
        connection = resolve_connection(config, root)
    except (ValueError, RuntimeError) as exc:
        checks.append({"name": "SSH configuration", "status": "FAIL", "detail": str(exc)})
        return {"status": "FAIL", "checks": checks}
    remote_root = config["remote"]["root"]
    endpoint = config["comfyui"]["endpoint"]
    root_check = f"test -d {shlex.quote(remote_root)}"
    try:
        ssh_result = subprocess.run(ssh_command(connection, "true"), capture_output=True, text=True, timeout=15, check=False)
        checks.append({"name": "SSH reachable", "status": "PASS" if ssh_result.returncode == 0 else "FAIL", "detail": "" if ssh_result.returncode == 0 else ssh_result.stderr.strip()[-500:]})
        if ssh_result.returncode != 0:
            return {"status": "FAIL", "checks": checks}
        runtime_result = subprocess.run(ssh_command(connection, root_check), capture_output=True, text=True, timeout=15, check=False)
        checks.append({"name": "remote runtime path", "status": "PASS" if runtime_result.returncode == 0 else "FAIL", "detail": remote_root})
        worker_python = str(config.get("worker_python", "/root/miniconda3/bin/python"))
        python = (
            "import json,urllib.request; "
            f"r=urllib.request.urlopen({endpoint + '/system_stats'!r},timeout=5); "
            "print(json.dumps({'http_status':r.status}))"
        )
        comfy_result = subprocess.run(ssh_command(connection, shlex.join([worker_python, "-c", python])), capture_output=True, text=True, timeout=12, check=False)
        comfy_ok = comfy_result.returncode == 0
        checks.append({"name": "ComfyUI localhost", "status": "PASS" if comfy_ok else "FAIL", "detail": "" if comfy_ok else comfy_result.stderr.strip()[-500:]})
        if runtime_result.returncode == 0:
            worker_result = run_remote(config, connection, ["doctor", "--json"], timeout=30)
            worker_ok = False
            detail = worker_result.stderr.strip()[-500:]
            try:
                worker = json.loads(worker_result.stdout)
                required_checks = worker.get("checks") if isinstance(worker.get("checks"), dict) else {}
                worker_ok = (
                    worker_result.returncode == 0
                    and worker.get("schema_version") == H3_JOB_SCHEMA_VERSION
                    and worker.get("status") == "READY"
                    and worker.get("backend") == "minimax_h3"
                    and all(required_checks.get(key) == "PASS" for key in ("comfyui_api", "h3_model", "required_nodes", "native_audio"))
                )
                detail = "protocol and H3 runtime checks passed" if worker_ok else "worker checks: " + ", ".join(f"{key}={value}" for key, value in required_checks.items())
            except json.JSONDecodeError:
                detail = detail or "remote worker returned invalid JSON"
            checks.append({"name": "H3 worker protocol", "status": "PASS" if worker_ok else "FAIL", "detail": detail})
        else:
            checks.append({"name": "H3 worker protocol", "status": "BLOCKED", "detail": "remote runtime path is missing"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        checks.append({"name": "remote checks", "status": "FAIL", "detail": str(exc)})
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {"status": status, "checks": checks}


def prepare_episode(root: str | Path, episode_id: str, shot_id: str | None = None) -> list[Path]:
    root = Path(root).resolve()
    _episode_directory(root, episode_id)
    if shot_id is not None and not SHOT_RE.fullmatch(shot_id):
        raise ValueError("shot_id is invalid")
    return prepare_h3_jobs(root, episode_id, [shot_id] if shot_id else None)


def submit_episode(root: str | Path, episode_id: str, shot_id: str | None = None) -> list[dict[str, Any]]:
    root = Path(root).resolve()
    episode_root = _episode_directory(root, episode_id)
    if shot_id is not None and not SHOT_RE.fullmatch(shot_id):
        raise ValueError("shot_id is invalid")
    doctor = h3_doctor(root)
    if doctor.get("status") != "PASS":
        failed_checks = [item.get("name") for item in doctor.get("checks", []) if item.get("status") != "PASS"]
        raise RuntimeError("H3 submit blocked; doctor checks failed: " + ", ".join(str(item) for item in failed_checks))
    manifest_path = episode_root / "episode.yaml"
    manifest = load_manifest(manifest_path)
    assert_valid_manifest(manifest, manifest_path)
    config = load_remote_h3_config(root)
    connection = resolve_connection(config, root)
    result: list[dict[str, Any]] = []
    selected = [item for item in manifest["shots"] if shot_id is None or item.get("id") == shot_id]
    if shot_id and not selected:
        raise ValueError(f"Unknown shot id: {shot_id}")
    for item in selected:
        if item.get("remote_status") != "REMOTE_READY":
            continue
        relative_job = item.get("remote_job")
        if not isinstance(relative_job, str):
            raise ValueError(f"{item.get('id')} is REMOTE_READY without a remote_job path")
        raw_job_path = episode_root / relative_job
        if _has_symlink_component(episode_root, raw_job_path):
            raise ValueError(f"{item.get('id')} remote_job cannot contain symlinks")
        job_path = raw_job_path.resolve()
        if not job_path.is_relative_to(episode_root) or not job_path.is_file():
            raise ValueError(f"{item.get('id')} remote_job path is unsafe or missing")
        package = job_path.parent
        job_path = package / "job.json"
        job = json.loads(job_path.read_text(encoding="utf-8"))
        assert_valid_h3_job(job)
        if job.get("job_id") != package.name or not JOB_ID_RE.fullmatch(package.name):
            raise ValueError(f"Invalid local H3 package directory: {package}")
        if (job.get("episode_id"), job.get("shot_id")) != (episode_id, item.get("id")):
            raise ValueError(f"{item.get('id')} manifest points to a different H3 job")
        hashes = job.get("input_sha256")
        if not isinstance(hashes, dict):
            raise ValueError(f"{package.name} input_sha256 must be a mapping")
        for relative, expected_hash in hashes.items():
            raw_asset = package / relative
            if _has_symlink_component(package, raw_asset):
                raise ValueError(f"Packaged H3 asset cannot contain symlinks: {relative}")
            asset = raw_asset.resolve()
            if not asset.is_relative_to(package.resolve()) or not asset.is_file():
                raise ValueError(f"Unsafe or missing packaged H3 asset: {relative}")
            if not isinstance(expected_hash, str) or sha256_file(asset) != expected_hash:
                raise ValueError(f"Packaged H3 asset hash mismatch: {relative}")
        remote_directory = transfer_job(config, connection, package)
        response = _remote_json(config, connection, ["submit", "--job-dir", remote_directory, "--json"])
        if response.get("schema_version") != H3_JOB_SCHEMA_VERSION or response.get("job_id") != job["job_id"]:
            raise RuntimeError(f"Remote H3 submit response does not match {job['job_id']}")
        if response.get("status") == "FAILED":
            item["remote_status"] = "FAILED"
            dump_yaml({key: value for key, value in manifest.items() if key != "_path"}, manifest_path)
            raise RuntimeError(f"Remote H3 job {job['job_id']} failed; it will not be retried automatically")
        if response.get("status") not in {"SUBMITTED", "QUEUED", "RUNNING", "COMPLETE"}:
            raise RuntimeError(f"Remote H3 submit response has an unsupported status for {job['job_id']}")
        result.append({"job_id": job["job_id"], "remote_directory": remote_directory, "response": response})
        item["remote_status"] = "COMPLETE" if response["status"] == "COMPLETE" else "SUBMITTED"
        dump_yaml({key: value for key, value in manifest.items() if key != "_path"}, manifest_path)
    if not result:
        target = f" for {shot_id}" if shot_id else ""
        raise ValueError(f"No REMOTE_READY H3 job found for {episode_id}{target}")
    return result


def remote_status(root: str | Path, episode_id: str, shot_id: str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    episode_root = _episode_directory(root, episode_id)
    if shot_id is not None and not SHOT_RE.fullmatch(shot_id):
        raise ValueError("shot_id is invalid")
    manifest_path = episode_root / "episode.yaml"
    manifest = load_manifest(manifest_path)
    assert_valid_manifest(manifest, manifest_path)
    config = load_remote_h3_config(root)
    connection = resolve_connection(config, root)
    arguments = ["status", "--episode-id", episode_id, "--json"]
    if shot_id:
        arguments += ["--shot-id", shot_id]
    response = _remote_json(config, connection, arguments)
    if response.get("schema_version") != "hajimi-h3-remote-v1" or not isinstance(response.get("jobs"), list):
        raise RuntimeError("Remote H3 status must return hajimi-h3-remote-v1 with a jobs list")
    jobs_by_id = {item.get("job_id"): item for item in response["jobs"] if isinstance(item, dict)}
    if len(jobs_by_id) != len(response["jobs"]):
        raise RuntimeError("Remote H3 status contains duplicate or invalid job entries")
    changed = False
    for item in manifest["shots"]:
        if shot_id and item.get("id") != shot_id:
            continue
        relative_job = item.get("remote_job")
        if not isinstance(relative_job, str):
            continue
        raw_job_path = episode_root / relative_job
        if _has_symlink_component(episode_root, raw_job_path):
            raise ValueError(f"{item.get('id')} remote_job cannot contain symlinks")
        job_path = raw_job_path.resolve()
        if not job_path.is_relative_to(episode_root) or not job_path.is_file():
            raise ValueError(f"{item.get('id')} remote_job path is unsafe or missing")
        package_job = json.loads(job_path.read_text(encoding="utf-8"))
        remote = jobs_by_id.get(package_job.get("job_id"))
        if remote is None:
            continue
        if remote.get("episode_id") != episode_id or remote.get("shot_id") != item.get("id"):
            raise RuntimeError(f"Remote status job identity mismatch for {package_job.get('job_id')}")
        remote_state = remote.get("status")
        if remote_state in {"SUBMITTED", "QUEUED", "RUNNING"}:
            local_state = "SUBMITTED"
        elif remote_state in {"COMPLETE", "FAILED"}:
            local_state = remote_state
        else:
            raise RuntimeError(f"Unsupported remote H3 job status: {remote_state!r}")
        if item.get("remote_status") in {"CANDIDATES_IMPORTED", "SELECTED"}:
            if local_state == "FAILED":
                raise RuntimeError(f"Remote H3 job {package_job.get('job_id')} failed after local result import")
            continue
        if item.get("remote_status") == "FAILED" and local_state != "FAILED":
            continue
        if item.get("remote_status") != local_state:
            item["remote_status"] = local_state
            changed = True
    if changed:
        dump_yaml({key: value for key, value in manifest.items() if key != "_path"}, manifest_path)
    return response


def pull_episode_result(root: str | Path, episode_id: str, shot_id: str) -> Path:
    root = Path(root).resolve()
    episode_root = _episode_directory(root, episode_id)
    if not SHOT_RE.fullmatch(shot_id):
        raise ValueError("shot_id is invalid")
    config = load_remote_h3_config(root)
    connection = resolve_connection(config, root)
    manifest = load_manifest(episode_root / "episode.yaml")
    shot = next((item for item in manifest.get("shots", []) if item.get("id") == shot_id), None)
    if not isinstance(shot, dict) or not isinstance(shot.get("remote_job"), str):
        raise ValueError(f"{shot_id} has no prepared H3 job")
    raw_job_path = episode_root / shot["remote_job"]
    if _has_symlink_component(episode_root, raw_job_path):
        raise ValueError("Manifest remote_job cannot contain symlinks")
    job_path = raw_job_path.resolve()
    if not job_path.is_relative_to(episode_root) or not job_path.is_file():
        raise ValueError("Manifest remote_job path is unsafe or missing")
    job = json.loads(job_path.read_text(encoding="utf-8"))
    source = pull_job_result(config, connection, job["job_id"], episode_root / ".h3_pull" / job["job_id"])
    try:
        imported = import_h3_result(root, episode_id, shot_id, source)
        result_hash = sha256_file(source / "result.json")
        cleanup = _remote_json(config, connection, [
            "cleanup", "--job-id", job["job_id"], "--confirm-result-sha256", result_hash, "--local-import-verified", "--json",
        ])
        if cleanup.get("schema_version") != H3_JOB_SCHEMA_VERSION or cleanup.get("job_id") != job["job_id"] or cleanup.get("status") != "CLEANED" or cleanup.get("result_sha256") != result_hash:
            raise RuntimeError("Remote H3 cleanup did not confirm the locally imported result")
        return imported
    finally:
        shutil.rmtree(episode_root / ".h3_pull", ignore_errors=True)


def select_candidate(root: str | Path, episode_id: str, shot_id: str, candidate: int, reviewer: str) -> Path:
    return select_h3_candidate(root, episode_id, shot_id, candidate, reviewer=reviewer)
