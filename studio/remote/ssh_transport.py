"""SSH and rsync/scp transport for small, self-contained H3 job packages."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ..config import load_yaml

_HOST_RE = re.compile(r"^[A-Za-z0-9_.@:\[\]-]+$")
_MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def load_remote_h3_config(root: str | Path) -> dict[str, Any]:
    path = Path(root) / "config" / "remote_h3.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Remote H3 config is missing: {path}")
    value = load_yaml(path)
    if value.get("schema_version") != "hajimi-remote-h3-v1":
        raise ValueError("config/remote_h3.yaml has an unsupported schema_version")
    if value.get("transport") != "ssh":
        raise ValueError("Remote H3 transport must be ssh")
    endpoint = value.get("comfyui", {}).get("endpoint") if isinstance(value.get("comfyui"), dict) else None
    endpoint_match = re.fullmatch(r"http://(?:127\.0\.0\.1|localhost):(\d{1,5})", endpoint) if isinstance(endpoint, str) else None
    if endpoint_match is None or not 1 <= int(endpoint_match.group(1)) <= 65535:
        raise ValueError("ComfyUI endpoint must stay on the remote localhost interface")
    backend = value.get("backend")
    if not isinstance(backend, dict) or backend.get("type") != "minimax_h3":
        raise ValueError("Remote video backend must be minimax_h3")
    remote = value.get("remote")
    if not isinstance(remote, dict):
        raise ValueError("remote H3 settings must be a mapping")
    remote_root = remote.get("root")
    if not isinstance(remote_root, str) or not re.fullmatch(r"/[A-Za-z0-9._/-]+", remote_root) or ".." in Path(remote_root).parts:
        raise ValueError("remote.root must be an absolute path containing only safe path characters")
    module = value.get("worker_module", "hajimi_h3_worker")
    if not isinstance(module, str) or not _MODULE_RE.fullmatch(module):
        raise ValueError("worker_module must be a Python module name")
    return value


def resolve_connection(config: Mapping[str, Any], root: str | Path | None = None) -> dict[str, Any]:
    remote = config["remote"]
    values: dict[str, Any] = {}
    missing: list[str] = []
    for key, default in (("host", None), ("user", None), ("port", "22")):
        env_name = remote.get(f"{key}_env")
        if not isinstance(env_name, str) or not env_name:
            missing.append(f"remote.{key}_env")
            continue
        value = os.environ.get(env_name, default)
        if value is None or value == "":
            missing.append(env_name)
            continue
        values[key] = value
    if missing:
        command_env = str(remote.get("command_env", "AUTODL_COMMAND"))
        port_env_name = remote.get("port_env")
        port_from_environment = isinstance(port_env_name, str) and bool(os.environ.get(port_env_name))
        project_root = Path(root).resolve() if root is not None else Path.cwd()
        env_file = project_root / ".env.local"
        if env_file.is_file():
            assignment = None
            for line in env_file.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith(f"{command_env}="):
                    assignment = stripped.split("=", 1)[1].strip()
                    break
            if assignment:
                # .env.local stores the whole ssh invocation as a quoted string.
                # Parse it as data; never source/eval the file or read its password key.
                outer = shlex.split(assignment)
                argv = shlex.split(outer[0]) if len(outer) == 1 else outer
                if argv and Path(argv[0]).name == "ssh":
                    parsed_port = "22"
                    target = None
                    index = 1
                    while index < len(argv):
                        token = argv[index]
                        if token == "-p" and index + 1 < len(argv):
                            parsed_port = argv[index + 1]
                            index += 2
                            continue
                        if token in {"-o", "-i", "-F", "-J", "-l"} and index + 1 < len(argv):
                            option, option_value = token, argv[index + 1]
                            if option in {"-J", "-l"}:
                                raise RuntimeError("AUTODL_COMMAND must use a direct SSH target, not a jump host or separate login option")
                            if option == "-i":
                                values["identity_file"] = option_value
                            if option == "-F":
                                values["ssh_config"] = option_value
                            if option == "-o" and option_value.lower().startswith("proxycommand="):
                                raise RuntimeError("AUTODL_COMMAND proxy commands are not supported by the project transport")
                            index += 2
                            continue
                        if token.startswith("-"):
                            raise RuntimeError("AUTODL_COMMAND contains an unsupported SSH option")
                        if target is not None:
                            raise RuntimeError("AUTODL_COMMAND must not include a remote shell command")
                        target = token
                        index += 1
                    if target and "@" in target:
                        parsed_user, parsed_host = target.rsplit("@", 1)
                        values.setdefault("user", parsed_user)
                        values.setdefault("host", parsed_host)
                        if not port_from_environment:
                            values["port"] = parsed_port
                        env_to_key = {str(remote.get(f"{key}_env")): key for key in ("host", "user", "port")}
                        missing = [name for name in missing if not values.get(env_to_key.get(name, ""))]
    if missing:
        raise RuntimeError("Remote H3 connection is not configured; missing " + ", ".join(missing))
    if not _HOST_RE.fullmatch(str(values["host"])) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", str(values["user"])):
        raise ValueError("Remote H3 host/user contains unsupported characters")
    try:
        port = int(values["port"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Remote H3 SSH port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("Remote H3 SSH port must be between 1 and 65535")
    values["port"] = port
    values["target"] = f"{values['user']}@{values['host']}"
    if values.get("identity_file"):
        identity = str(values["identity_file"])
        if not identity.startswith("/") and not identity.startswith("~"):
            raise ValueError("SSH identity file must be an absolute or home-relative path")
    return values


def ssh_command(connection: Mapping[str, Any], remote_command: str) -> list[str]:
    command = ["ssh", *_ssh_options(connection)]
    command += [connection["target"], remote_command]
    return command


def _ssh_options(connection: Mapping[str, Any]) -> list[str]:
    options = ["-p", str(connection["port"]), "-o", "BatchMode=yes"]
    if connection.get("identity_file"):
        options += ["-i", str(connection["identity_file"])]
    if connection.get("ssh_config"):
        options += ["-F", str(connection["ssh_config"])]
    return options


def _scp_options(connection: Mapping[str, Any]) -> list[str]:
    options = ["-P", str(connection["port"]), "-o", "BatchMode=yes"]
    if connection.get("identity_file"):
        options += ["-i", str(connection["identity_file"])]
    if connection.get("ssh_config"):
        options += ["-F", str(connection["ssh_config"])]
    return options


def run_remote(config: Mapping[str, Any], connection: Mapping[str, Any], arguments: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    entrypoint = str(config.get("worker_entrypoint", "worker.py"))
    if entrypoint != "worker.py":
        raise ValueError("worker_entrypoint must be worker.py")
    runtime = str(config["remote"]["root"])
    worker_python = str(config.get("worker_python", "/root/miniconda3/bin/python"))
    if not re.fullmatch(r"/[A-Za-z0-9._/-]+", worker_python) or ".." in Path(worker_python).parts:
        raise ValueError("worker_python must be a safe absolute path")
    worker_dir = f"{runtime}/worker"
    command = f"cd {shlex.quote(worker_dir)} && PYTHONPATH=. {shlex.join([worker_python, entrypoint, *arguments])}"
    return subprocess.run(ssh_command(connection, command), capture_output=True, text=True, timeout=timeout, check=False)


def _remote_path(config: Mapping[str, Any], category: str, job_id: str) -> str:
    base = str(config["remote"]["root"])
    path = f"{base}/{category}/{job_id}"
    if not re.fullmatch(r"/[A-Za-z0-9._/-]+", path) or ".." in Path(path).parts:
        raise ValueError("Remote H3 path contains unsupported characters")
    return path


def transfer_job(config: Mapping[str, Any], connection: Mapping[str, Any], package: str | Path) -> str:
    source = Path(package).resolve()
    if not source.is_dir() or not (source / "job.json").is_file():
        raise FileNotFoundError(f"H3 job package is incomplete: {source}")
    destination = _remote_path(config, "jobs/inbox", source.name)
    remote_mkdir = f"mkdir -p {shlex.quote(destination)}"
    completed = subprocess.run(ssh_command(connection, remote_mkdir), capture_output=True, text=True, timeout=60, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip()[-1500:] or "unable to create remote H3 job directory")
    rsync = shutil.which("rsync")
    if rsync:
        ssh_transport = shlex.join(["ssh", *_ssh_options(connection)])
        command = [rsync, "-az", "--protect-args", "-e", ssh_transport, f"{source}/", f"{connection['target']}:{destination}/"]
    else:
        scp = shutil.which("scp")
        if not scp:
            raise RuntimeError("Install rsync or scp locally to transfer H3 jobs")
        command = [scp, "-r", *_scp_options(connection), str(source / "."), f"{connection['target']}:{destination}/"]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip()[-2000:] or "H3 job upload failed")
    return destination


def pull_job_result(config: Mapping[str, Any], connection: Mapping[str, Any], job_id: str, destination: str | Path) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,119}", job_id):
        raise ValueError("Unsafe H3 job id")
    remote_source = _remote_path(config, "jobs/complete", job_id)
    target = Path(destination).resolve()
    if target.exists():
        raise FileExistsError(f"Preserve the existing H3 pull directory before retrying: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    scp = shutil.which("scp")
    if not scp:
        raise RuntimeError("Install scp locally to download H3 results")
    with tempfile.TemporaryDirectory(prefix=f".{target.name}.pulling-", dir=target.parent) as temporary:
        temporary_path = Path(temporary)
        result_file = temporary_path / "result.json"
        result_command = [scp, *_scp_options(connection), f"{connection['target']}:{remote_source}/result.json", str(result_file)]
        completed = subprocess.run(result_command, capture_output=True, text=True, timeout=120, check=False)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip()[-2000:] or "H3 result manifest download failed")
        try:
            result = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Remote H3 result manifest is invalid JSON") from exc
        if not isinstance(result, dict) or result.get("schema_version") != "hajimi-h3-remote-v1" or result.get("job_id") != job_id or result.get("status") != "COMPLETE":
            raise RuntimeError("Remote H3 result manifest does not match the requested completed job")
        candidates = result.get("candidates")
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= 8:
            raise RuntimeError("Remote H3 result manifest has an invalid candidate list")
        names = {"result.json"}
        for item in candidates:
            if not isinstance(item, dict):
                raise RuntimeError("Remote H3 result candidate entry is invalid")
            for key in ("filename", "metadata_file"):
                name = item.get(key)
                if not isinstance(name, str) or len(name) > 180 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
                    raise RuntimeError(f"Remote H3 result has an unsafe {key}")
                names.add(name)
        for name in sorted(names - {"result.json"}):
            command = [scp, *_scp_options(connection), f"{connection['target']}:{remote_source}/{name}", str(temporary_path / name)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip()[-2000:] or f"H3 result file download failed: {name}")
        temporary_path.rename(target)
        return target
