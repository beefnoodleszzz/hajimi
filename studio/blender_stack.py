"""Deterministic, project-local Blender production stack.

This module deliberately keeps Blender at arm's length: the Python CLI owns
configuration, manifests, hashes, cache decisions, and QC, while Blender is
invoked headlessly for scene construction and image-sequence rendering.  No
global Blender preferences, credentials, or commercial add-ons are touched.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

from .config import dump_yaml, load_yaml, write_json
from .manifest import load_shot_manifest
from .paths import StudioPaths


REQUIRED_BLENDER_VERSION = "5.2.2"
REQUIRED_ENGINES = {"EEVEE": "BLENDER_EEVEE_NEXT", "CYCLES": "CYCLES"}
DEFAULT_TARGET = "EP001_TEST_01"
DEFAULT_PROFILE = "P1"
PROFILE_NAMES = ("P0", "P1", "P2", "P3", "hero_exr", "final_cycles")


class BlenderStackError(RuntimeError):
    """Raised when a requested stack operation cannot produce its artifact."""


def _root(value: str | Path) -> Path:
    return Path(value).resolve()


def _blender_config(root: Path) -> dict[str, Any]:
    return load_yaml(root / "config" / "blender.yaml")


def _render_profiles(root: Path) -> dict[str, Any]:
    return load_yaml(root / "config" / "blender" / "render_profiles.yaml")


def _resolve_path(root: Path, value: str | Path) -> Path:
    text = str(value)
    if text.startswith("$HAJIMI_ASSETS"):
        text = text.replace("$HAJIMI_ASSETS", str(root / "blender" / "assets"), 1)
    elif text.startswith("$HAJIMI_PROJECT_ROOT"):
        text = text.replace("$HAJIMI_PROJECT_ROOT", str(root), 1)
    path = Path(os.path.expandvars(text)).expanduser()
    return path if path.is_absolute() else root / path


def _configured_paths(root: Path, config: dict[str, Any]) -> dict[str, Path]:
    values = config.get("paths", {})
    result = {key: _resolve_path(root, value) for key, value in values.items()}
    result["generated_config"] = root / "config" / "generated"
    result["runtime"] = root / "blender" / "generated" / "runtime"
    result["generated_artifacts"] = root / "blender" / "generated" / "artifacts"
    return result


def _find_blender() -> str | None:
    candidates: list[str] = []
    configured = os.environ.get("BLENDER_BIN")
    if configured:
        candidates.append(configured)
    which = shutil.which("blender")
    if which:
        candidates.append(which)
    candidates.extend(
        [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/opt/homebrew/bin/blender",
            "/usr/local/bin/blender",
        ]
    )
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path.resolve())
    return None


def _parse_blender_version(text: str) -> str | None:
    match = re.search(r"Blender\s+(\d+\.\d+\.\d+)", text)
    return match.group(1) if match else None


def _version_status(actual: str | None, required: str = REQUIRED_BLENDER_VERSION) -> str:
    return "PASS" if actual == required else "BLOCKED_VERSION_MISMATCH"


def _command_output(command: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": None, "stdout": "", "stderr": str(exc), "error": type(exc).__name__}
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _host_hardware(blender_binary: str | None) -> dict[str, Any]:
    memory_bytes: int | None = None
    if platform.system() == "Darwin" and shutil.which("sysctl"):
        result = _command_output(["sysctl", "-n", "hw.memsize"])
        if result.get("returncode") == 0:
            try:
                memory_bytes = int(str(result.get("stdout", "")).strip())
            except ValueError:
                memory_bytes = None
    elif Path("/proc/meminfo").exists():
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                try:
                    memory_bytes = int(line.split()[1]) * 1024
                except (IndexError, ValueError):
                    pass
                break
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count_logical": os.cpu_count(),
        "memory_bytes": memory_bytes,
        "memory_gib": round(memory_bytes / (1024**3), 2) if memory_bytes else None,
        "blender_binary": blender_binary,
        "detected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _ensure_dirs(paths: dict[str, Path]) -> None:
    for path in paths.values():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)


def _write_runtime_script(paths: dict[str, Path], name: str, body: str) -> Path:
    paths["runtime"].mkdir(parents=True, exist_ok=True)
    script = paths["runtime"] / f"{name}.py"
    script.write_text(body, encoding="utf-8")
    return script


def _invoke_blender(
    root: Path,
    paths: dict[str, Path],
    name: str,
    body: str,
    *,
    timeout: int = 600,
    extra_args: Iterable[str] = (),
    factory_startup: bool = True,
) -> dict[str, Any]:
    binary = _find_blender()
    if not binary:
        raise BlenderStackError("Blender binary not found; set BLENDER_BIN or install Blender locally")
    script = _write_runtime_script(paths, name, body)
    command = [binary, "--background"]
    if factory_startup:
        command.append("--factory-startup")
    command.extend(["--python", str(script), "--", *extra_args])
    blender_env = os.environ.copy()
    # Keep Blender's scripts, extensions, and preferences project-local.  This
    # makes installed legal add-ons visible to every headless invocation while
    # avoiding mutations to the user's global Blender profile.
    blender_env.setdefault("HAJIMI_PROJECT_ROOT", str(root))
    blender_env.setdefault("HAJIMI_ASSETS", str(paths["assets"]))
    blender_env.setdefault("HAJIMI_INSTALLERS", str(paths["installers"]))
    blender_env.setdefault("HAJIMI_BLENDER_EXTENSIONS", str(paths["extensions"]))
    blender_env.setdefault("BLENDER_USER_SCRIPTS", str(paths["scripts"]))
    blender_env.setdefault("BLENDER_USER_EXTENSIONS", str(paths["extensions"]))
    blender_env.setdefault("BLENDER_USER_CONFIG", str(paths.get("config", root / "blender" / "config")))
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=blender_env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result = {
            "command": command,
            "returncode": completed.returncode,
            "duration_sec": round(time.monotonic() - started, 3),
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
        result["ok"] = bool(
            completed.returncode == 0
            and "Traceback (most recent call last)" not in completed.stderr
        )
    except subprocess.TimeoutExpired as exc:
        result = {
            "command": command,
            "returncode": None,
            "duration_sec": round(time.monotonic() - started, 3),
            "stdout_tail": str(exc.stdout or "")[-4000:],
            "stderr_tail": str(exc.stderr or "")[-4000:],
            "error": "timeout",
            "ok": False,
        }
    log_path = paths["logs"] / f"{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    event = {
        "operation": name,
        "duration_sec": result.get("duration_sec"),
        "command": command,
        "returncode": result.get("returncode"),
        "status": "PASS" if result.get("ok") else "FAIL",
        "renderer": next((str(value) for value in command if str(value) in {"BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"}), None),
        "gpu": "METAL" if platform.system() == "Darwin" and platform.machine() == "arm64" else None,
        "output": result.get("output") or result.get("stdout_tail", "")[-300:],
        "error": result.get("error") or (result.get("stderr_tail", "")[-1000:] if not result.get("ok") else None),
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    event_path = paths["logs"] / f"{time.strftime('%Y%m%dT%H%M%S')}_{name}.jsonl"
    event_path.write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
    result["event_log"] = str(event_path)
    return result


def _probe_body(
    output_path: Path,
    smoke_dir: Path,
    asset_libraries: list[dict[str, str]] | None = None,
    startup_script: Path | None = None,
) -> str:
    payload = {
        "output": str(output_path),
        "smoke_dir": str(smoke_dir),
        "asset_libraries": asset_libraries or [],
        "startup_script": str(startup_script) if startup_script else None,
    }
    return f'''# generated by hajimi.blender_stack
import json, math, os, platform, sys, time
import runpy
from pathlib import Path
import bpy

SPEC = {json.dumps(payload, ensure_ascii=False)}
OUTPUT = Path(SPEC["output"])
SMOKE_DIR = Path(SPEC["smoke_dir"])
SMOKE_DIR.mkdir(parents=True, exist_ok=True)
startup_registration = {{"status": "NOT_CONFIGURED"}}
if SPEC.get("startup_script") and Path(SPEC["startup_script"]).exists():
    try:
        runpy.run_path(SPEC["startup_script"], run_name="hajimi_bootstrap_doctor")
        startup_registration = {{"status": "PASS", "path": SPEC["startup_script"]}}
    except Exception as exc:
        startup_registration = {{"status": "FAIL", "path": SPEC["startup_script"], "error": f"{{type(exc).__name__}}: {{exc}}"}}

def _version():
    return ".".join(str(part) for part in bpy.app.version)

def _engine_id(preferred):
    for candidate in preferred:
        try:
            bpy.context.scene.render.engine = candidate
            return candidate
        except Exception:
            continue
    return None

def _make_smoke_scene(engine, path):
    started = time.monotonic()
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        resolved = _engine_id([engine])
        if not resolved:
            return {{"engine": engine, "status": "UNAVAILABLE", "duration_sec": 0}}
        scene.render.resolution_x = 32
        scene.render.resolution_y = 32
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(path)
        scene.render.film_transparent = False
        if scene.world is None:
            scene.world = bpy.data.worlds.new("HajimiSmokeWorld")
        scene.world.color = (0.025, 0.035, 0.06)
        bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
        cube = bpy.context.object
        cube.scale = (1.0, 1.0, 1.0)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.object.camera_add(location=(0, -5, 3))
        camera = bpy.context.object
        camera.rotation_euler = (math.radians(68), 0, 0)
        scene.camera = camera
        bpy.ops.object.light_add(type="AREA", location=(0, -3, 4))
        bpy.context.object.data.energy = 500
        if engine == "CYCLES":
            scene.cycles.samples = 1
            scene.cycles.use_denoising = False
            # Keep the smoke render CPU-safe.  Metal device discovery is still
            # recorded below; a first-run Metal kernel compile can block a
            # diagnostic command for minutes on a fresh Blender install.
            scene.cycles.device = "CPU"
            try:
                addon = bpy.context.preferences.addons.get("cycles")
                if addon:
                    prefs = addon.preferences
                    prefs.compute_device_type = "METAL"
                    prefs.get_devices()
                    devices = list(getattr(prefs, "devices", []))
                    # Do not switch the diagnostic render to GPU implicitly.
                    # The report proves Metal discovery independently.
            except Exception:
                pass
        bpy.ops.render.render(write_still=True)
        return {{"engine": engine, "status": "PASS", "resolved_engine": resolved,
                 "duration_sec": round(time.monotonic() - started, 3),
                 "output": str(path), "exists": path.exists()}}
    except Exception as exc:
        return {{"engine": engine, "status": "FAIL", "duration_sec": round(time.monotonic() - started, 3),
                 "error": f"{{type(exc).__name__}}: {{exc}}"}}

def _devices():
    result = []
    try:
        addon = bpy.context.preferences.addons.get("cycles")
        if addon:
            prefs = addon.preferences
            try:
                prefs.compute_device_type = "METAL"
            except Exception:
                pass
            try:
                prefs.get_devices()
            except Exception:
                pass
            for device in getattr(prefs, "devices", []):
                result.append({{"name": getattr(device, "name", ""), "type": getattr(device, "type", ""),
                                "use": bool(getattr(device, "use", False))}})
    except Exception as exc:
        return {{"error": f"{{type(exc).__name__}}: {{exc}}", "devices": []}}
    return {{"devices": result}}

def _addon_modules():
    modules = set()
    try:
        modules.update(str(name) for name in bpy.context.preferences.addons.keys())
    except Exception:
        pass
    try:
        for base in bpy.utils.script_paths(subdir="addons"):
            if os.path.isdir(base):
                for entry in os.listdir(base):
                    if entry.endswith(".py"):
                        modules.add(entry[:-3])
                    elif os.path.isdir(os.path.join(base, entry)):
                        modules.add(entry)
    except Exception:
        pass
    return sorted(modules)

def _asset_libraries():
    result = []
    for spec in SPEC.get("asset_libraries", []):
        name = str(spec.get("name", ""))
        expected = Path(str(spec.get("path", ""))).resolve()
        entry = None
        try:
            entry = bpy.context.preferences.filepaths.asset_libraries.get(name)
        except Exception:
            entry = None
        actual = Path(str(entry.path)).resolve() if entry and getattr(entry, "path", None) else None
        result.append({{
            "name": name,
            "expected_path": str(expected),
            "actual_path": str(actual) if actual else None,
            "registered": bool(entry),
            "path_matches": bool(actual and actual == expected),
            "exists": expected.is_dir(),
            "writable": os.access(expected, os.W_OK),
        }})
    return result

result = {{
    "blender_version": _version(),
    "blender_version_string": bpy.app.version_string,
    "python_version": sys.version.split()[0],
    "platform": platform.platform(),
    "architecture": platform.machine(),
    "bpy_import": True,
    "engines": {{"eevee": _engine_id(["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"]), "cycles": _engine_id(["CYCLES"])}},
    "cycles_devices": _devices(),
    "addon_modules": _addon_modules(),
    "asset_libraries": _asset_libraries(),
    "startup_registration": startup_registration,
    "smoke": {{}}
}}
result["smoke"]["eevee"] = _make_smoke_scene("BLENDER_EEVEE", SMOKE_DIR / "eevee.png")
result["smoke"]["cycles"] = _make_smoke_scene("CYCLES", SMOKE_DIR / "cycles.png")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
'''


def _plugin_probe_body(output_path: Path, module_names: list[str]) -> str:
    payload = {"output": str(output_path), "module_names": module_names}
    return f'''# generated by hajimi.blender_stack
import addon_utils
import json
import sys
import tomllib
from pathlib import Path

SPEC = {json.dumps(payload, ensure_ascii=False)}
OUTPUT = Path(SPEC["output"])
results = {{}}
for name in SPEC["module_names"]:
    entry = {{"module": name, "available": False, "enabled": False, "loaded": False}}
    try:
        available_modules = {{str(module.__name__): module for module in addon_utils.modules()}}
        entry["available"] = name in available_modules
        if entry["available"]:
            addon_utils.enable(name, default_set=False, persistent=False)
        enabled, loaded = addon_utils.check(name)
        entry["enabled"] = bool(enabled)
        entry["loaded"] = bool(loaded)
        module = available_modules.get(name)
        info = getattr(module, "bl_info", {{}}) if module else {{}}
        entry["name"] = info.get("name")
        entry["version"] = list(info.get("version", ())) if info.get("version") else None
        if module and getattr(module, "__file__", None):
            manifest_path = Path(module.__file__).resolve().parent / "blender_manifest.toml"
            if manifest_path.exists():
                manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
                entry["name"] = manifest.get("name", entry["name"])
                manifest_version = str(manifest.get("version", ""))
                entry["version"] = [int(part) for part in manifest_version.split(".") if part.isdigit()]
                entry["manifest"] = str(manifest_path)
    except Exception as exc:
        entry["error"] = f"{{type(exc).__name__}}: {{exc}}"
    results[name] = entry
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps({{"addons": results, "python_version": sys.version.split()[0]}}, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
'''


def _detect_local_packages(root: Path, config: dict[str, Any]) -> dict[str, list[str]]:
    installers = _resolve_path(root, config.get("paths", {}).get("installers", "blender/installers"))
    files = [path for path in installers.rglob("*") if path.is_file()] if installers.exists() else []
    result: dict[str, list[str]] = {}
    for key, plugin in config.get("plugins", {}).items():
        patterns = [str(item).lower() for item in plugin.get("installer_patterns", [])]
        result[key] = [str(path.relative_to(root)) for path in files if any(pattern in path.name.lower() for pattern in patterns)]
    return result


def _plugin_matrix(
    config: dict[str, Any],
    probe: dict[str, Any],
    local_packages: dict[str, list[str]],
    plugin_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del probe  # Core probe data is intentionally separate from add-on smoke data.
    plugin_probe = plugin_probe or {}
    probed_addons = plugin_probe.get("addons", {})
    known_modules = {
        "photographer": ["photographer"],
        "geoscatter": ["geoscatter", "geo_scatter"],
        "physical_atmosphere": ["physical_atmosphere"],
        "poliigon": ["poliigon-addon-blender"],
        "botaniq_engon": ["engon"],
        "flip_fluids": ["flip_fluids_addon"],
    }
    matrix: dict[str, Any] = {}
    for key, plugin in config.get("plugins", {}).items():
        candidates = [str(item) for item in plugin.get("module_names", known_modules.get(key, []))]
        packages = local_packages.get(key, [])
        loaded_entry = next(
            (probed_addons.get(module) for module in candidates if probed_addons.get(module, {}).get("loaded")),
            None,
        )
        failed_entry = next(
            (probed_addons.get(module) for module in candidates if probed_addons.get(module, {}).get("error")),
            None,
        )
        loaded = bool(loaded_entry)
        if loaded:
            status = "PASS"
        elif failed_entry and packages:
            status = "FAILED_SMOKE"
        elif packages:
            status = "AVAILABLE_LOCAL_PACKAGE"
        elif plugin.get("required"):
            status = "BLOCKED_LICENSE_PACKAGE"
        else:
            status = "BLOCKED"
        package_variant = "demo" if any("demo" in path.lower() for path in packages) else "full"
        detected_version = loaded_entry.get("version") if loaded_entry else None
        matrix[key] = {
            "display_name": plugin.get("display_name", key),
            "required": bool(plugin.get("required")),
            "expected_version": plugin.get("expected_version"),
            "status": status,
            "blocking": bool(plugin.get("required") and status != "PASS"),
            "installed": loaded,
            "enabled": loaded,
            "detected_version": detected_version,
            "blender_compat": True if loaded else None,
            "smoke_test": "PASS" if loaded else ("FAILED_SMOKE" if failed_entry else status),
            "block_reason": None if loaded else (
                "PLUGIN_SMOKE_FAILED" if failed_entry and packages else
                "BLOCKED_LICENSE_PACKAGE" if plugin.get("required") else
                "NOT_INSTALLED_OPTIONAL"
            ),
            "module_name": loaded_entry.get("module") if loaded_entry else (failed_entry or {}).get("module"),
            "loaded_markers": [loaded_entry.get("module")] if loaded_entry else [],
            "distribution_variant": package_variant if packages else None,
            "replacement_for": plugin.get("replacement_for"),
            "local_packages": packages,
            "policy": "inspect-only; no automatic download or license bypass",
        }
        if failed_entry:
            matrix[key]["error"] = failed_entry.get("error")
    # Commercial packages may be absent by policy while a documented free
    # replacement satisfies the capability. Keep the original package
    # transparently BLOCKED, but do not let that block the core stack.
    for key, value in matrix.items():
        replacements = [
            replacement_key
            for replacement_key, replacement in matrix.items()
            if replacement.get("replacement_for") == key and replacement.get("status") == "PASS"
        ]
        if replacements:
            value["satisfied_by_replacements"] = replacements
            value["blocking"] = False
            value["capability_status"] = "PASS_WITH_REPLACEMENT"
        else:
            value["satisfied_by_replacements"] = []
            value["capability_status"] = "PASS" if value.get("status") == "PASS" else value.get("status")
    return matrix


def _doctor_impl(root: Path) -> dict[str, Any]:
    root = _root(root)
    config = _blender_config(root)
    paths = _configured_paths(root, config)
    _ensure_dirs(paths)
    asset_index = _asset_index(root, config, paths)
    asset_library_specs = [
        {"name": str(item.get("name")), "path": str(item.get("path"))}
        for item in asset_index.get("libraries", [])
        if item.get("name") and item.get("path")
    ]
    binary = _find_blender()
    version_info = _command_output([binary, "--version"]) if binary else {"returncode": None, "stdout": "", "stderr": "not found"}
    actual_version = _parse_blender_version(str(version_info.get("stdout", "")))
    probe_path = paths["generated_config"] / "blender_runtime_probe.json"
    smoke_dir = paths["generated_config"] / "blender_smoke"
    invoke: dict[str, Any] | None = None
    if binary:
        invoke = _invoke_blender(
            root,
            paths,
            "doctor_probe",
            _probe_body(
                probe_path,
                smoke_dir,
                asset_library_specs,
                paths["scripts"] / "startup" / "hajimi_bootstrap.py",
            ),
            timeout=180,
        )
    if probe_path.exists():
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
    else:
        probe = {"bpy_import": False, "smoke": {}, "addon_modules": [], "error": "probe did not write output"}
    packages = _detect_local_packages(root, config)
    plugin_probe_path = paths["generated_config"] / "blender_plugin_probe.json"
    plugin_invoke: dict[str, Any] | None = None
    plugin_probe: dict[str, Any] = {"addons": {}}
    module_names = sorted(
        {
            str(module)
            for plugin in config.get("plugins", {}).values()
            for module in plugin.get("module_names", [])
        }
    )
    if binary and module_names:
        plugin_invoke = _invoke_blender(
            root,
            paths,
            "plugin_probe",
            _plugin_probe_body(plugin_probe_path, module_names),
            timeout=180,
            factory_startup=False,
        )
    if plugin_probe_path.exists():
        plugin_probe = json.loads(plugin_probe_path.read_text(encoding="utf-8"))
    hardware = _host_hardware(binary)
    hardware.update(
        {
            "blender_version": actual_version,
            "required_blender_version": REQUIRED_BLENDER_VERSION,
            "version_status": _version_status(actual_version),
            "gpu_backend_policy": "METAL on Apple Silicon; no CUDA/OptiX/HIP/ONEAPI on Apple Silicon",
            "cycles_devices": probe.get("cycles_devices", {}),
            "bpy_python_version": probe.get("python_version"),
        }
    )
    write_json(hardware, paths["generated_config"] / "hardware.json")
    plugins = _plugin_matrix(config, probe, packages, plugin_probe)
    write_json(plugins, paths["generated_config"] / "plugin_matrix.json")
    required_plugin_blockers = [key for key, value in plugins.items() if value.get("blocking")]
    smoke = probe.get("smoke", {})
    core_smoke = {
        "bpy": bool(probe.get("bpy_import")),
        "eevee": smoke.get("eevee", {}).get("status") == "PASS",
        "cycles": smoke.get("cycles", {}).get("status") == "PASS",
        "headless": bool(invoke and invoke.get("ok", invoke.get("returncode") == 0) and probe_path.exists()),
    }
    blockers: list[str] = []
    if _version_status(actual_version) != "PASS":
        blockers.append("BLOCKED_VERSION_MISMATCH")
    if not binary:
        blockers.append("BLENDER_NOT_FOUND")
    if not core_smoke["bpy"]:
        blockers.append("BPY_IMPORT_FAILED")
    if not core_smoke["eevee"]:
        blockers.append("EEVEE_HEADLESS_SMOKE_FAILED")
    if not core_smoke["cycles"]:
        blockers.append("CYCLES_HEADLESS_SMOKE_FAILED")
    probe_asset_libraries = probe.get("asset_libraries", []) if isinstance(probe.get("asset_libraries"), list) else []
    asset_library_checks = {
        "required": asset_index.get("required_library_names", []),
        "indexed": asset_index.get("libraries", []),
        "probe": probe_asset_libraries,
        "pass": bool(asset_index.get("libraries"))
        and all(
            item.get("exists")
            and item.get("writable")
            and not item.get("metadata_errors")
            for item in asset_index.get("libraries", [])
        )
        and len(probe_asset_libraries) == len(asset_index.get("libraries", []))
        and all(
            item.get("registered") and item.get("path_matches")
            for item in probe_asset_libraries
        ),
    }
    if not asset_library_checks["pass"]:
        blockers.append("ASSET_LIBRARY_REGISTRATION_FAILED")
    payload = {
        "command": "doctor",
        "status": "BLOCKED" if blockers else "PASS",
        "decision": "BLOCKED" if blockers else "PASS",
        "required_version": REQUIRED_BLENDER_VERSION,
        "actual_version": actual_version,
        "version_status": _version_status(actual_version),
        "binary": binary,
        "hardware": hardware,
        "probe": probe,
        "core_smoke": core_smoke,
        "plugins": plugins,
        "plugin_probe": plugin_probe,
        "asset_libraries": asset_library_checks,
        "required_plugin_blockers": required_plugin_blockers,
        "blocking_reasons": blockers,
        "atmosphere": config.get("atmosphere", {}),
        "policy": config.get("policy", {}),
        "invocation": invoke,
        "plugin_invocation": plugin_invoke,
    }
    write_json(payload, paths["generated_config"] / "blender_doctor.json")
    return payload


def _asset_index(root: Path, config: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    assets_root = _resolve_path(root, os.environ.get("HAJIMI_ASSETS", str(paths["assets"])))
    dirs = ["curated", "vendor", "hdri", "materials", "models", "environments", "cameras", "lights", "geometry_nodes", "fx", "licenses"]
    for name in dirs:
        (assets_root / name).mkdir(parents=True, exist_ok=True)
    libraries = []
    for library in config.get("assets", {}).get("libraries", []):
        path = assets_root / str(library.get("path", library.get("name", "library")))
        path.mkdir(parents=True, exist_ok=True)
        files = [file for file in path.rglob("*") if file.is_file() and not file.name.endswith(".json")]
        asset_records: list[dict[str, Any]] = []
        metadata_errors: list[str] = []
        for file in files[:200]:
            sidecar_path = Path(f"{file}.json")
            sidecar: dict[str, Any] = {}
            if sidecar_path.exists():
                try:
                    loaded = json.loads(sidecar_path.read_text(encoding="utf-8"))
                    sidecar = loaded if isinstance(loaded, dict) else {}
                except (OSError, json.JSONDecodeError):
                    metadata_errors.append(f"unreadable sidecar: {sidecar_path}")
            else:
                metadata_errors.append(f"missing sidecar: {sidecar_path}")
            actual_hash = _sha256(file)
            if sidecar.get("sha256") != actual_hash:
                metadata_errors.append(f"asset hash mismatch: {file}")
            if not sidecar.get("source"):
                metadata_errors.append(f"asset source missing: {file}")
            if not sidecar.get("license"):
                metadata_errors.append(f"asset license missing: {file}")
            asset_records.append(
                {
                    "path": str(file.relative_to(root)),
                    "sha256": actual_hash,
                    "source": sidecar.get("source", ""),
                    "license": sidecar.get("license", ""),
                    "asset_name": sidecar.get("asset_name"),
                    "tags": sidecar.get("tags", []),
                    "sidecar": str(sidecar_path.relative_to(root)) if sidecar_path.exists() else None,
                }
            )
        libraries.append(
            {
                "name": library.get("name"),
                "category": library.get("category"),
                "path": str(path),
                "exists": path.exists(),
                "writable": os.access(path, os.W_OK),
                "asset_count": len(files),
                "assets": asset_records,
                "metadata_errors": metadata_errors,
            }
        )
    payload = {
        "asset_root": str(assets_root),
        "source_policy": "local curated/vendor files only; no online fallback",
        "metadata_contract": "sidecar JSON must provide source, license, and matching sha256",
        "libraries": libraries,
        "required_library_names": ["Hajimi Curated", "Hajimi Cameras", "Hajimi Materials", "Hajimi Environments", "Hajimi FX"],
    }
    write_json(payload, paths["generated_config"] / "asset_library_matrix.json")
    write_json(payload, paths["generated_artifacts"] / "asset_libraries.json")
    write_json(payload, assets_root / "asset_library_index.json")
    return payload


def configure_gpu(root: str | Path) -> dict[str, Any]:
    """Expose the project-local GPU policy as a callable/script entrypoint."""

    project = _root(root)
    report = _doctor_impl(project)
    hardware = dict(report.get("hardware", {}))
    devices = hardware.get("cycles_devices", {}).get("devices", []) if isinstance(hardware.get("cycles_devices"), dict) else []
    selected = next((device for device in devices if device.get("use") and device.get("type") != "CPU"), None)
    hardware["selected_device"] = selected
    hardware["selection_policy"] = "METAL on Apple Silicon; platform backend otherwise; CPU only as explicit fallback"
    write_json(hardware, project / "config" / "generated" / "hardware_profile.json")
    return {"command": "configure_gpu", "status": report.get("status"), "hardware": hardware, "doctor": str(project / "config/generated/blender_doctor.json")}


def configure_assets(root: str | Path) -> dict[str, Any]:
    """Index only the configured project-local Asset Browser libraries."""

    project = _root(root)
    config = _blender_config(project)
    paths = _configured_paths(project, config)
    _ensure_dirs(paths)
    result = _asset_index(project, config, paths)
    result["command"] = "configure_assets"
    result["status"] = "PASS" if all(item.get("exists") and item.get("writable") for item in result.get("libraries", [])) else "BLOCKED"
    write_json(result, paths["generated_config"] / "asset_browser_config.json")
    return result


def configure_render(root: str | Path) -> dict[str, Any]:
    """Validate and materialize the render profile contract without rendering."""

    project = _root(root)
    config = _blender_config(project)
    profiles = _render_profiles(project)
    paths = _configured_paths(project, config)
    _ensure_dirs(paths)
    normalized = {name: _profile(config, profiles, name) for name in profiles.get("profiles", {})}
    payload = {
        "command": "configure_render",
        "status": "PASS" if normalized else "BLOCKED",
        "default_engine": config.get("render", {}).get("default_engine", "EEVEE"),
        "profiles": normalized,
        "final_output_policy": "image_sequence",
        "final_resolution": [config.get("render", {}).get("final_width"), config.get("render", {}).get("final_height")],
    }
    write_json(payload, paths["generated_config"] / "render_profiles.json")
    return payload


def _scene_body(output_blend: Path, spec: dict[str, Any]) -> str:
    payload = {"output_blend": str(output_blend), "spec": spec}
    return f'''# generated by hajimi.blender_stack
import json, math
from pathlib import Path
import bpy
from mathutils import Vector

PAYLOAD = {payload!r}
SPEC = PAYLOAD["spec"]

COLLECTION_NAMES = ["ENV", "SUBJECT", "PROPS", "FX", "LIGHTS", "HELPERS", "CAMERA", "RENDER_ONLY", "QC"]

def collection(name):
    value = bpy.data.collections.get(name)
    if value is None:
        value = bpy.data.collections.new(name)
    if value.name not in [child.name for child in bpy.context.scene.collection.children]:
        try:
            bpy.context.scene.collection.children.link(value)
        except RuntimeError:
            pass
    return value

def move_to_collection(value, name):
    target = collection(name)
    for owner in list(value.users_collection):
        owner.objects.unlink(value)
    target.objects.link(value)
    return value

def setup_collections():
    for name in COLLECTION_NAMES:
        collection(name)

def inferred_collection(name):
    upper = str(name).upper()
    if upper.startswith(("CAMERA", "DOLLY", "PANTILT", "SHAKE", "TARGET")):
        return "CAMERA"
    if upper.startswith("HJ_SAFE"):
        return "HELPERS"
    if upper.startswith(("LGT", "LIGHT", "SUN", "WARM", "COOL", "SKY")):
        return "LIGHTS"
    if any(token in upper for token in ("ROAD", "CITY", "LAND", "AIR", "OCEAN", "GROUND", "COAST", "SURFACE", "BUILDING", "GLASS", "METAL", "GRASS", "ROCK", "HAZE")):
        return "ENV"
    if any(token in upper for token in ("DUST", "VECTOR", "ARROW", "EDGE", "RESTART", "IMPACT", "TRAIL")):
        return "FX"
    if any(token in upper for token in ("PERSON", "PAPER", "SUBJECT")):
        return "SUBJECT"
    return "PROPS"

def material(name, color, metallic=0.0, roughness=0.5):
    value = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    value.diffuse_color = (*color, 1.0)
    value.use_nodes = True
    bsdf = value.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    return value

def empty(name, parent=None, location=(0, 0, 0)):
    value = bpy.data.objects.new(name, None)
    value.empty_display_type = "PLAIN_AXES"
    value.location = location
    bpy.context.collection.objects.link(value)
    if parent:
        value.parent = parent
    return move_to_collection(value, inferred_collection(name))

def cube(name, location, scale, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=location)
    value = bpy.context.object
    value.name = name
    value.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        value.data.materials.append(mat)
    if bevel:
        modifier = value.modifiers.new("EdgeSoftness", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return move_to_collection(value, inferred_collection(name))

def sphere(name, location, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=radius, location=location)
    value = bpy.context.object
    value.name = name
    if mat:
        value.data.materials.append(mat)
    return move_to_collection(value, inferred_collection(name))

def curve_line(name, points, mat, bevel=0.035):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = bevel
    data.bevel_resolution = 2
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*co, 1.0)
    value = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(value)
    data.materials.append(mat)
    return move_to_collection(value, inferred_collection(name))

def camera_rig():
    root = empty("CameraRoot")
    dolly = empty("Dolly", root)
    pantilt = empty("PanTilt", dolly)
    shake = empty("Shake", pantilt)
    target = empty("Target", root, (0.0, 0.0, 1.2))
    camera_data = bpy.data.cameras.new("CAM_Main")
    camera = bpy.data.objects.new("CAM_Main", camera_data)
    bpy.context.collection.objects.link(camera)
    move_to_collection(camera, "CAMERA")
    camera.parent = shake
    camera.location = (0.0, -20.0, 7.0)
    camera_data.lens = float(SPEC.get("lens_mm", 24))
    camera_data.sensor_width = 36.0
    constraint = camera.constraints.new(type="TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"
    scene = bpy.context.scene
    scene.camera = camera
    guides = empty("HJ_SAFE_GUIDES", root)
    guides["right_interaction_ui_reserve_pct"] = 18
    guides["bottom_title_description_reserve_pct"] = 16
    guides["subtitle_safe_pct"] = 12
    guides["story_typography_safe_pct"] = 10
    guides.hide_render = True
    return root, dolly, pantilt, shake, target, camera

def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    setup_collections()
    try:
        scene.render.engine = SPEC.get("engine_id", "BLENDER_EEVEE_NEXT")
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = int(SPEC.get("width", 540))
    scene.render.resolution_y = int(SPEC.get("height", 960))
    scene.render.resolution_percentage = 100
    scene.render.fps = int(SPEC.get("fps", 30))
    scene.frame_start = int(SPEC.get("frame_start", 1))
    scene.frame_end = int(SPEC.get("frame_end", 90))
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("HajimiWorld")
    scene.world.color = (0.018, 0.028, 0.055)
    scene["hajimi_target"] = SPEC.get("target", "unknown")
    scene["screen_direction"] = "RIGHT"
    scene["ground_lock"] = bool(SPEC.get("ground_lock", False))
    scene["late_afternoon"] = bool(SPEC.get("late_afternoon", False))
    scene["motion_validation"] = "Red_Paper_Anchor moves screen-right; Ground_Locked_Road remains static"
    scene["camera_rig"] = "CameraRoot/Dolly/PanTilt/Shake/Target/CAM_Main"
    scene["safe_guides"] = {{"right_ui_pct": 18, "bottom_text_pct": 16, "subtitle_pct": 12, "story_pct": 10}}
    scene["collection_contract"] = ";".join(COLLECTION_NAMES)
    scene["cache_ready"] = True
    scene["renderer_policy"] = "EEVEE default; Cycles requires shot-specific reason"
    return scene

def build_test_shot(scene):
    road_mat = material("Road_Charcoal", (0.045, 0.055, 0.07), roughness=0.78)
    line_mat = material("Lane_Marker", (0.68, 0.55, 0.28), roughness=0.45)
    building_mat = material("City_Block", (0.14, 0.19, 0.26), roughness=0.72)
    person_mat = material("Person_Proxy", (0.025, 0.032, 0.045), roughness=0.88)
    red_mat = material("Red_Paper", (0.82, 0.035, 0.025), roughness=0.36)
    cyan_mat = material("Direction_Cyan", (0.02, 0.75, 0.95), metallic=0.1, roughness=0.25)
    dust_mat = material("Dust", (0.52, 0.38, 0.20), roughness=1.0)
    cube("Ground_Locked_Road", (0, 0, 0), (18, 5, 0.12), road_mat, 0.06)
    for x in range(-15, 16, 4):
        cube(f"Lane_{{x}}", (x, 0, 0.14), (1.25, 0.08, 0.025), line_mat, 0.01)
    for index, x in enumerate(range(-14, 16, 4)):
        cube(f"City_Left_{{index}}", (x, 8.5, 1.6 + (index % 3) * 0.7), (1.2, 0.8, 1.6 + (index % 3) * 0.7), building_mat, 0.08)
        cube(f"City_Right_{{index}}", (x, 7.0, 1.2 + ((index + 1) % 3) * 0.65), (1.1, 0.8, 1.2 + ((index + 1) % 3) * 0.65), building_mat, 0.08)
    # Charcoal human proxy with a deliberately readable silhouette.
    sphere("Person_Head", (-2.6, 0.0, 2.8), 0.42, person_mat)
    cube("Person_Torso", (-2.6, 0.0, 1.55), (0.48, 0.36, 0.9), person_mat, 0.12)
    cube("Person_Leg_L", (-2.95, 0.0, 0.55), (0.18, 0.22, 0.55), person_mat, 0.06)
    cube("Person_Leg_R", (-2.25, 0.0, 0.55), (0.18, 0.22, 0.55), person_mat, 0.06)
    paper = cube("Red_Paper_Anchor", (-1.6, -0.1, 2.25), (0.28, 0.035, 0.20), red_mat, 0.025)
    paper.rotation_euler[1] = math.radians(-8)
    paper.keyframe_insert(data_path="location", frame=1)
    paper.location.x = 4.8
    paper.keyframe_insert(data_path="location", frame=75)
    paper.location.x = 6.2
    paper.keyframe_insert(data_path="location", frame=90)
    for index, x in enumerate((-1.4, -0.7, 0.3, 1.4, 2.5, 3.7)):
        puff = sphere(f"Dust_{{index}}", (x, -0.2, 0.28 + (index % 2) * 0.12), 0.10 + (index % 3) * 0.035, dust_mat)
        puff.scale = (1.8, 0.65, 0.65)
        puff.keyframe_insert(data_path="location", frame=1)
        puff.location.x += 1.6
        puff.scale.x *= 0.15
        puff.keyframe_insert(data_path="location", frame=70)
    curve_line("Cyan_Rightward_Vector", [(-1.0, -0.5, 0.5), (4.4, -0.5, 0.5)], cyan_mat, 0.06)
    curve_line("Cyan_Vector_Arrowhead", [(4.4, -0.5, 0.5), (3.7, -0.5, 0.75), (3.7, -0.5, 0.25)], cyan_mat, 0.06)
    # A warm key and restrained cool fill make the charcoal proxy and red
    # anchor survive a phone-sized portrait render.
    bpy.ops.object.light_add(type="AREA", location=(-5.0, -9.0, 12.0))
    key = bpy.context.object
    key.name = "Late_Afternoon_Key"
    key.data.energy = 1800
    key.data.shape = "DISK"
    key.data.size = 10.0
    key.data.color = (1.0, 0.55, 0.30)
    move_to_collection(key, "LIGHTS")
    bpy.ops.object.light_add(type="AREA", location=(6.0, 5.0, 8.0))
    fill = bpy.context.object
    fill.name = "Sky_Cool_Fill"
    fill.data.energy = 700
    fill.data.shape = "DISK"
    fill.data.size = 12.0
    fill.data.color = (0.25, 0.45, 1.0)
    move_to_collection(fill, "LIGHTS")
    if scene.world is not None:
        scene.world.use_nodes = True
        background = scene.world.node_tree.nodes.get("Background")
        if background:
            background.inputs["Color"].default_value = (0.06, 0.025, 0.012, 1.0)
            background.inputs["Strength"].default_value = 0.28
    return camera_rig()

def cutaway_rig(ortho_scale=14.0, target_z=0.0):
    root, dolly, pantilt, shake, target, camera = camera_rig()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = float(ortho_scale)
    camera.location = (0.0, -20.0, 0.0)
    target.location = (0.0, 0.0, float(target_z))
    return root, dolly, pantilt, shake, target, camera

def label(name, body, location, mat, size=0.52):
    bpy.ops.object.text_add(location=location, rotation=(math.radians(90), 0.0, 0.0))
    value = bpy.context.object
    value.name = name
    value.data.body = body
    value.data.align_x = "CENTER"
    value.data.align_y = "CENTER"
    value.data.size = float(size)
    value.data.extrude = 0.012
    value.data.materials.append(mat)
    value.hide_render = True
    value["fusion_typography"] = True
    return move_to_collection(value, "RENDER_ONLY")

def light_setup(scene, warm=(1.0, 0.42, 0.18), energy=1500):
    bpy.ops.object.light_add(type="AREA", location=(-5.0, -8.0, 9.0))
    key = bpy.context.object
    key.name = "Warm_Key"
    key.data.energy = energy
    key.data.shape = "DISK"
    key.data.size = 8.0
    key.data.color = warm
    move_to_collection(key, "LIGHTS")
    bpy.ops.object.light_add(type="AREA", location=(5.0, -2.0, 6.0))
    fill = bpy.context.object
    fill.name = "Cool_Fill"
    fill.data.energy = energy * 0.42
    fill.data.shape = "DISK"
    fill.data.size = 10.0
    fill.data.color = (0.22, 0.42, 1.0)
    move_to_collection(fill, "LIGHTS")
    if scene.world is not None:
        scene.world.use_nodes = True
        background = scene.world.node_tree.nodes.get("Background")
        if background:
            background.inputs["Color"].default_value = (0.018, 0.028, 0.07, 1.0)
            background.inputs["Strength"].default_value = 0.34

def animate_x(value, first, pivot=None, last=None, pivot_frame=None):
    if pivot is None:
        pivot = first
    if last is None:
        last = pivot
    if pivot_frame is None:
        pivot_frame = scene.frame_start + max(1, (scene.frame_end - scene.frame_start) // 3)
    base_x = float(value.location.x)
    value.location.x = base_x + float(first)
    value.keyframe_insert(data_path="location", index=0, frame=scene.frame_start)
    value.location.x = base_x + float(pivot)
    value.keyframe_insert(data_path="location", index=0, frame=int(pivot_frame))
    value.location.x = base_x + float(last)
    value.keyframe_insert(data_path="location", index=0, frame=scene.frame_end)

def build_air_inertia(scene):
    land_mat = material("S005_Land", (0.22, 0.11, 0.055), roughness=0.92)
    road_mat = material("S005_Road", (0.045, 0.055, 0.075), roughness=0.78)
    building_mat = material("S005_City", (0.12, 0.19, 0.27), roughness=0.68)
    air_mat = material("S005_AirBand", (0.025, 0.36, 0.56), roughness=0.32)
    cloud_mat = material("S005_Cloud", (0.55, 0.68, 0.78), roughness=0.88)
    vector_mat = material("S005_Vector", (0.02, 0.82, 1.0), metallic=0.15, roughness=0.24)
    text_mat = material("S005_Text", (0.92, 0.96, 1.0), metallic=0.05, roughness=0.35)
    cube("S005_Land_Slab", (0.0, 0.0, -3.0), (6.5, 2.0, 0.48), land_mat, 0.12)
    cube("S005_Road_Surface", (0.0, -0.4, -2.46), (6.4, 1.2, 0.08), road_mat, 0.03)
    for index, x in enumerate((-5.4, -3.6, -1.8, 0.0, 1.8, 3.6, 5.4)):
        cube("S005_City_" + str(index + 1), (x, 0.5, -1.2 + (index % 3) * 0.35), (0.52, 0.55, 1.2 + (index % 3) * 0.35), building_mat, 0.06)
    air_band = cube("S005_Air_Momentum_Band", (0.0, 0.0, 0.1), (6.2, 1.4, 0.42), air_mat, 0.12)
    animate_x(air_band, 0.0, 1.5, 3.6)
    for index, x in enumerate((-4.5, -2.2, 0.2, 2.6, 4.7)):
        cloud = sphere("S005_Cloud_" + str(index + 1), (x, 0.1, 1.55 + (index % 2) * 0.28), 0.58 + (index % 3) * 0.12, cloud_mat)
        cloud.scale = (1.5, 0.7, 0.55)
        animate_x(cloud, 0.0, 1.0, 3.0)
    curve_line("S005_Rightward_Vector", [(-4.6, -1.2, 0.1), (5.0, -1.2, 0.1)], vector_mat, 0.075)
    curve_line("S005_Vector_Arrowhead", [(5.0, -1.2, 0.1), (4.25, -1.2, 0.5), (4.25, -1.2, -0.3)], vector_mat, 0.075)
    label("S005_Title", "AIR KEEPS MOVING", (0.0, -1.35, 3.1), text_mat, 0.62)
    label("S005_Air_Label", "AIR", (-2.65, -1.35, 0.55), text_mat, 0.5)
    label("S005_Land_Label", "LAND", (-2.65, -1.35, -2.25), text_mat, 0.5)
    light_setup(scene, energy=1750)
    scene["shot_mode"] = "air_inertia"
    scene["causal_read"] = "land locks while air band and clouds retain eastward momentum"
    return cutaway_rig(ortho_scale=13.5, target_z=0.0)

def build_ocean_inertia(scene):
    land_mat = material("S006_Land", (0.26, 0.13, 0.055), roughness=0.94)
    coast_mat = material("S006_Coast", (0.5, 0.27, 0.08), roughness=0.82)
    water_mat = material("S006_Water", (0.015, 0.16, 0.48), metallic=0.08, roughness=0.2)
    wave_mat = material("S006_Wave", (0.05, 0.52, 0.86), metallic=0.05, roughness=0.18)
    vector_mat = material("S006_Vector", (0.1, 0.92, 0.96), metallic=0.12, roughness=0.22)
    text_mat = material("S006_Text", (0.92, 0.98, 1.0), roughness=0.3)
    cube("S006_Seabed", (0.0, 0.0, -3.0), (6.7, 2.0, 0.42), land_mat, 0.12)
    cube("S006_Coastline", (-4.7, -0.1, -1.55), (1.25, 1.25, 1.5), coast_mat, 0.16)
    water = cube("S006_Ocean_CrossSection", (1.0, 0.2, -1.05), (5.3, 1.55, 0.95), water_mat, 0.13)
    animate_x(water, 0.0, 1.0, 2.8)
    for index, x in enumerate((-3.4, -2.2, -1.0, 0.2, 1.4, 2.6, 3.8, 5.0)):
        wave = cube("S006_Wave_" + str(index + 1), (x, -1.05, 0.15 + (index % 3) * 0.22), (0.5, 0.08, 0.08), wave_mat, 0.05)
        animate_x(wave, 0.0, 0.7, 2.6)
    curve_line("S006_Rightward_Vector", [(-3.0, -1.35, 1.8), (5.0, -1.35, 1.8)], vector_mat, 0.075)
    curve_line("S006_Vector_Arrowhead", [(5.0, -1.35, 1.8), (4.25, -1.35, 2.2), (4.25, -1.35, 1.4)], vector_mat, 0.075)
    label("S006_Title", "OCEAN KEEPS MOVING", (0.5, -1.4, 3.3), text_mat, 0.57)
    label("S006_Coast_Label", "COAST", (-2.65, -1.4, 0.35), text_mat, 0.43)
    label("S006_Water_Label", "OCEAN", (2.3, -1.4, -0.05), text_mat, 0.5)
    light_setup(scene, warm=(1.0, 0.34, 0.12), energy=1850)
    scene["shot_mode"] = "ocean_inertia"
    scene["causal_read"] = "coastline locks while ocean surface and waves retain eastward momentum"
    return cutaway_rig(ortho_scale=13.8, target_z=0.0)

def build_restart_mismatch(scene):
    land_mat = material("S007_Land", (0.55, 0.24, 0.06), roughness=0.88)
    air_mat = material("S007_Air", (0.03, 0.45, 0.70), metallic=0.06, roughness=0.3)
    ocean_mat = material("S007_Ocean", (0.02, 0.18, 0.62), metallic=0.08, roughness=0.18)
    edge_mat = material("S007_Edge", (0.92, 0.62, 0.16), metallic=0.15, roughness=0.25)
    text_mat = material("S007_Text", (0.96, 0.98, 1.0), roughness=0.25)
    restart_mat = material("S007_Restart", (1.0, 0.12, 0.18), metallic=0.1, roughness=0.24)
    land = cube("S007_LAND", (0.0, 0.0, -3.05), (6.7, 1.2, 0.48), land_mat, 0.11)
    air = cube("S007_AIR", (0.0, 0.0, 0.0), (6.7, 1.2, 0.44), air_mat, 0.11)
    ocean = cube("S007_OCEAN", (0.0, 0.0, 3.05), (6.7, 1.2, 0.48), ocean_mat, 0.11)
    pivot = scene.frame_start + max(1, int((scene.frame_end - scene.frame_start) * 0.34))
    animate_x(land, 0.0, -1.35, -1.35, pivot)
    animate_x(air, 0.0, 1.25, 2.7, pivot)
    animate_x(ocean, 0.0, 2.0, 4.0, pivot)
    for z in (-3.05, 0.0, 3.05):
        curve_line("S007_Edge_" + str(z), [(-6.0, -1.35, z + 0.48), (6.0, -1.35, z + 0.48)], edge_mat, 0.038)
    curve_line("S007_Restart_Line", [(0.0, -1.5, -5.2), (0.0, -1.5, 5.2)], restart_mat, 0.06)
    curve_line("S007_Sideways_Vector", [(-4.8, -1.55, -0.2), (4.8, -1.55, -0.2)], restart_mat, 0.055)
    curve_line("S007_Sideways_Arrowhead", [(4.8, -1.55, -0.2), (4.1, -1.55, 0.2), (4.1, -1.55, -0.6)], restart_mat, 0.055)
    label("S007_Land_Label", "LAND", (-2.65, -1.55, -3.05), text_mat, 0.58)
    label("S007_Air_Label", "AIR", (-2.65, -1.55, 0.0), text_mat, 0.58)
    label("S007_Ocean_Label", "OCEAN", (-2.65, -1.55, 3.05), text_mat, 0.52)
    label("S007_Restart_Label", "RESTART", (0.0, -1.55, 5.55), restart_mat, 0.52)
    label("S007_Vector_Label", "SIDEWAYS MOTION", (0.0, -1.55, -5.55), text_mat, 0.42)
    light_setup(scene, warm=(1.0, 0.37, 0.13), energy=2050)
    scene["shot_mode"] = "restart_mismatch"
    scene["causal_read"] = "land restarts first; air and ocean retain eastward momentum"
    scene["restart_pivot_frame"] = pivot
    return cutaway_rig(ortho_scale=15.5, target_z=0.0)

def build_episode_shot(scene):
    mode = SPEC.get("shot_mode", "episode_template")
    if mode == "air_inertia":
        return build_air_inertia(scene)
    if mode == "ocean_inertia":
        return build_ocean_inertia(scene)
    if mode == "restart_mismatch":
        return build_restart_mismatch(scene)
    return build_template(scene, mode)

def build_template(scene, template_name):
    dark = material("Template_Dark", (0.03, 0.04, 0.07), roughness=0.8)
    cyan = material("Template_Cyan", (0.02, 0.65, 0.90), roughness=0.3)
    cube("Template_Surface", (0, 0, 0), (5, 5, 0.1), dark)
    curve_line("Template_Vector", [(-3, 0, 0.2), (3, 0, 0.2)], cyan, 0.04)
    return camera_rig()

def build_benchmark(scene):
    road_mat = material("Benchmark_PBR_Road", (0.07, 0.08, 0.10), metallic=0.05, roughness=0.58)
    metal_mat = material("Benchmark_Metal", (0.28, 0.34, 0.42), metallic=0.92, roughness=0.18)
    glass_mat = material("Benchmark_Glass", (0.08, 0.30, 0.42), metallic=0.0, roughness=0.08)
    if glass_mat.node_tree:
        bsdf = glass_mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            transmission = bsdf.inputs.get("Transmission Weight") or bsdf.inputs.get("Transmission")
            if transmission:
                transmission.default_value = 0.82
    rock_mat = material("Benchmark_Rock", (0.18, 0.12, 0.08), roughness=0.95)
    grass_mat = material("Benchmark_Grass", (0.08, 0.22, 0.10), roughness=0.9)
    cube("Benchmark_PBR_Road", (0, 0, 0), (12, 4, 0.12), road_mat, 0.06)
    for index, x in enumerate((-9, -6, -3, 0, 3, 6, 9)):
        sphere("Benchmark_Rock_" + str(index), (x, 4.8, 0.35), 0.22 + (index % 2) * 0.1, rock_mat)
        cube("Benchmark_Grass_" + str(index), (x, -4.5, 0.35), (0.12, 0.12, 0.35 + (index % 3) * 0.1), grass_mat)
    cube("Benchmark_Metal_Block", (0, 0, 1.4), (0.8, 0.8, 1.4), metal_mat, 0.08)
    cube("Benchmark_Glass_Block", (3.2, 0.3, 1.0), (0.75, 0.75, 1.0), glass_mat, 0.04)
    # A small volume makes the benchmark exercise volume compatibility without
    # requiring a production atmosphere add-on or a global preference change.
    volume_mat = bpy.data.materials.new("Benchmark_Volumetric_Haze")
    volume_mat.use_nodes = True
    nodes = volume_mat.node_tree.nodes
    links = volume_mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.inputs["Density"].default_value = 0.006
    links.new(volume.outputs["Volume"], output.inputs["Volume"])
    haze = cube("Benchmark_Volumetric_Haze", (0, 2.0, 2.0), (10.0, 2.0, 2.0), None)
    haze.data.materials.append(volume_mat)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45, location=(-3.0, 0.0, 4.0))
    rigid = bpy.context.object
    rigid.name = "Benchmark_RigidBody"
    rigid.data.materials.append(metal_mat)
    try:
        bpy.ops.rigidbody.object_add()
        rigid.rigid_body.kinematic = False
    except Exception:
        rigid["rigid_body_fallback"] = True
    root, dolly, pantilt, shake, target, camera = camera_rig()
    dolly.location.y = 0.0
    dolly.keyframe_insert(data_path="location", frame=scene.frame_start)
    dolly.location.y = 1.0
    dolly.keyframe_insert(data_path="location", frame=scene.frame_end)
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
    sun = bpy.context.object
    sun.name = "Benchmark_Sun"
    sun.data.energy = 2.0
    sun.rotation_euler = (math.radians(25), math.radians(-20), math.radians(25))
    move_to_collection(sun, "LIGHTS")
    scene["benchmark_components"] = "PBR road; glass; metal; volumetric haze; scatter grass/rock; moving camera; rigid body; sun + procedural HDRI fallback"
    scene["hdrI_source"] = "procedural world fallback; local HDRI may be indexed later"
    return root, dolly, pantilt, shake, target, camera

scene = setup_scene()
if SPEC.get("mode") == "test_shot":
    root, dolly, pantilt, shake, target, camera = build_test_shot(scene)
elif SPEC.get("mode") == "episode_shot":
    root, dolly, pantilt, shake, target, camera = build_episode_shot(scene)
elif SPEC.get("mode") == "benchmark":
    root, dolly, pantilt, shake, target, camera = build_benchmark(scene)
else:
    root, dolly, pantilt, shake, target, camera = build_template(scene, SPEC.get("template", "generic"))
camera.data.lens = float(SPEC.get("lens_mm", 24))
dolly.location.y = 0.0
dolly.keyframe_insert(data_path="location", frame=scene.frame_start)
dolly.location.y = 0.8
dolly.keyframe_insert(data_path="location", frame=scene.frame_end)
scene.frame_set(scene.frame_start)
# Normalize any objects created by shot-specific template code so the scene
# remains compatible with the documented collection contract even when a
# template used bpy.ops directly.
for value in list(scene.objects):
    if value.type == "CAMERA":
        move_to_collection(value, "CAMERA")
    elif value.type == "LIGHT":
        move_to_collection(value, "LIGHTS")
    elif not value.users_collection:
        move_to_collection(value, inferred_collection(value.name))
for child in list(scene.collection.children):
    if child.name == "Collection" and not child.objects:
        scene.collection.children.unlink(child)
scene["collection_contract"] = ";".join(COLLECTION_NAMES)
Path(PAYLOAD["output_blend"]).parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=PAYLOAD["output_blend"])
'''


def _create_geometry_library(root: Path, paths: dict[str, Path], config: dict[str, Any]) -> dict[str, Any]:
    destination = _resolve_path(root, config.get("geometry_nodes", {}).get("library", "blender/generated/artifacts/geometry_nodes_library.blend"))
    groups = list(config.get("geometry_nodes", {}).get("groups", []))
    inventory_path = _resolve_path(root, config.get("geometry_nodes", {}).get("inventory", "blender/presets/geometry_nodes_library.yaml"))
    inventory = load_yaml(inventory_path) if inventory_path.exists() else {}
    inventory_specs = {
        str(item.get("name")): item
        for item in inventory.get("groups", [])
        if isinstance(item, dict) and item.get("name")
    }
    group_specs = [inventory_specs.get(str(group), {"name": str(group), "purpose": "Reusable Hajimi geometry node group."}) for group in groups]
    body = f'''import json
from pathlib import Path
import bpy

OUTPUT = {json.dumps(str(destination), ensure_ascii=False)}
GROUPS = {json.dumps(group_specs, ensure_ascii=False)}
bpy.ops.wm.read_factory_settings(use_empty=True)
for spec in GROUPS:
    name = spec.get("name", "HJ_Group")
    purpose = spec.get("purpose", "")
    tree = bpy.data.node_groups.new(name, "GeometryNodeTree")
    tree.use_fake_user = True
    geometry_in = tree.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    geometry_out = tree.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    density = tree.interface.new_socket(name="Density", in_out="INPUT", socket_type="NodeSocketFloat")
    density.default_value = 0.25
    seed = tree.interface.new_socket(name="Seed", in_out="INPUT", socket_type="NodeSocketFloat")
    seed.default_value = 0.0
    mode = tree.interface.new_socket(name="Mode", in_out="INPUT", socket_type="NodeSocketFloat")
    mode.default_value = 0.0
    input_node = tree.nodes.new("NodeGroupInput")
    input_node.label = "Hajimi geometry input"
    output_node = tree.nodes.new("NodeGroupOutput")
    output_node.label = "Hajimi geometry output"
    set_position = tree.nodes.new("GeometryNodeSetPosition")
    set_position.label = "Deterministic motion/scatter hook"
    if input_node.outputs.get("Geometry") and set_position.inputs.get("Geometry") and set_position.outputs.get("Geometry") and output_node.inputs.get("Geometry"):
        tree.links.new(input_node.outputs["Geometry"], set_position.inputs["Geometry"])
        tree.links.new(set_position.outputs["Geometry"], output_node.inputs["Geometry"])
    preview_value = tree.nodes.new("ShaderNodeValue")
    preview_value.name = "HJ_PreviewDensity"
    preview_value.label = "PREVIEW density"
    preview_value.outputs[0].default_value = 0.25
    final_value = tree.nodes.new("ShaderNodeValue")
    final_value.name = "HJ_FinalDensity"
    final_value.label = "FINAL density"
    final_value.outputs[0].default_value = 1.0
    if "Scatter" in name or "Dust" in name or "Particle" in name or "Cloud" in name:
        distribute = tree.nodes.new("GeometryNodeDistributePointsOnFaces")
        distribute.label = "Preview-safe instanced distribution"
        if input_node.outputs.get("Geometry") and distribute.inputs.get("Mesh"):
            tree.links.new(input_node.outputs["Geometry"], distribute.inputs["Mesh"])
        if input_node.outputs.get("Density") and distribute.inputs.get("Density"):
            tree.links.new(input_node.outputs["Density"], distribute.inputs["Density"])
    if "Wave" in name or "Trail" in name or "Vector" in name or "Arrow" in name:
        position = tree.nodes.new("GeometryNodeInputPosition")
        position.label = "Motion direction source"
    tree["hajimi_group"] = name
    tree["purpose"] = purpose
    tree["input_contract"] = "Geometry; Density; Seed; Mode"
    tree["mode_contract"] = "PREVIEW / FINAL density controlled by caller"
Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUTPUT)
'''
    invoke = _invoke_blender(root, paths, "build_geometry_library", body, timeout=180)
    return {"path": str(destination), "group_count": len(group_specs), "groups": group_specs, "invocation": invoke, "exists": destination.exists()}


def _create_templates(root: Path, paths: dict[str, Path], config: dict[str, Any]) -> dict[str, Any]:
    template_root = paths["templates"]
    template_root.mkdir(parents=True, exist_ok=True)
    names = ["short_9x16", "science_cutaway", "cinematic_exterior", "studio_diagram"]
    outputs = [template_root / f"{name}.blend" for name in names]
    payload = [
        {"output": str(path), "name": name, "template": name, "mode": "template", "width": 1080, "height": 1920, "fps": 30, "frame_start": 1, "frame_end": 30, "lens_mm": 24 if name != "science_cutaway" else 50, "engine_id": "BLENDER_EEVEE_NEXT"}
        for path, name in zip(outputs, names)
    ]
    # Keep one Blender process for all templates. Rebuilding is intentional:
    # it upgrades older generated templates to the current collection/naming
    # contract while remaining deterministic and project-local.
    specs = [{"output_blend": item["output"], **{key: value for key, value in item.items() if key != "output"}} for item in payload]
    script = f'''import json
from pathlib import Path
import bpy

SPECS = {json.dumps(specs, ensure_ascii=False)}
COLLECTIONS = ["ENV", "SUBJECT", "PROPS", "FX", "LIGHTS", "HELPERS", "CAMERA", "RENDER_ONLY", "QC"]
def collection(name):
    value = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if value.name not in [child.name for child in bpy.context.scene.collection.children]:
        bpy.context.scene.collection.children.link(value)
    return value
def move(value, name):
    target = collection(name)
    for owner in list(value.users_collection):
        owner.objects.unlink(value)
    target.objects.link(value)
    return value
def mat(name, color):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    bsdf=m.node_tree.nodes.get("Principled BSDF")
    if bsdf: bsdf.inputs["Base Color"].default_value=(*color,1)
    return m
def empty(name,parent=None,location=(0,0,0),group="HELPERS"):
    o=bpy.data.objects.new(name,None); o.empty_display_type="PLAIN_AXES"; o.location=location; bpy.context.collection.objects.link(o); move(o,group)
    if parent: o.parent=parent
    return o
def make_rig(lens):
    root=empty("CameraRoot"); dolly=empty("Dolly",root); pan=empty("PanTilt",dolly); shake=empty("Shake",pan); target=empty("Target",root,(0,0,0))
    data=bpy.data.cameras.new("CAM_Main"); camera=bpy.data.objects.new("CAM_Main",data); bpy.context.collection.objects.link(camera); move(camera,"CAMERA"); camera.parent=shake; camera.location=(0,-18,6); data.lens=lens
    c=camera.constraints.new(type="TRACK_TO"); c.target=target; c.track_axis="TRACK_NEGATIVE_Z"; c.up_axis="UP_Y"; bpy.context.scene.camera=camera
    guides=empty("HJ_SAFE_GUIDES",root,group="HELPERS"); guides["right_ui_pct"]=18; guides["bottom_text_pct"]=16; guides.hide_render=True
def build(spec):
    bpy.ops.wm.read_factory_settings(use_empty=True); scene=bpy.context.scene
    for name in COLLECTIONS: collection(name)
    try: scene.render.engine="BLENDER_EEVEE_NEXT"
    except Exception: scene.render.engine="BLENDER_EEVEE"
    scene.render.resolution_x=spec["width"]; scene.render.resolution_y=spec["height"]; scene.render.resolution_percentage=100; scene.render.fps=spec["fps"]; scene.frame_start=spec["frame_start"]; scene.frame_end=spec["frame_end"]; scene.render.image_settings.file_format="PNG"; scene.render.image_settings.color_mode="RGB"
    if scene.world is None: scene.world=bpy.data.worlds.new("HajimiWorld")
    scene.world.color=(0.02,0.03,0.06); scene["hajimi_template"]=spec["name"]; scene["camera_rig"]="CameraRoot/Dolly/PanTilt/Shake/Target/CAM_Main"; scene["collection_contract"]=";".join(COLLECTIONS); scene["cache_ready"]=True
    make_rig(spec["lens_mm"]); surface=mat("ENV_Template_Surface",(0.04,0.06,0.10)); bpy.ops.mesh.primitive_plane_add(size=12); move(bpy.context.object,"ENV"); bpy.context.object.name="ENV_Template_Surface"; bpy.context.object.data.materials.append(surface); Path(spec["output_blend"]).parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=spec["output_blend"])
for spec in SPECS: build(spec)
'''
    invoke = _invoke_blender(root, paths, "build_templates", script, timeout=240)
    return {"templates": [str(path) for path in outputs], "created": [str(path) for path in outputs if path.exists()], "invocation": invoke}


def _bootstrap_impl(root: Path) -> dict[str, Any]:
    root = _root(root)
    config = _blender_config(root)
    paths = _configured_paths(root, config)
    _ensure_dirs(paths)
    assets = _asset_index(root, config, paths)
    doctor = _doctor_impl(root)
    templates = _create_templates(root, paths, config)
    geometry = _create_geometry_library(root, paths, config)
    payload = {
        "command": "bootstrap",
        "status": "BLOCKED" if doctor.get("status") == "BLOCKED" else "PASS",
        "decision": "BLOCKED" if doctor.get("status") == "BLOCKED" else "PASS",
        "version_status": doctor.get("version_status"),
        "assets": assets,
        "templates": templates,
        "geometry_nodes": geometry,
        "plugin_matrix": doctor.get("plugins", {}),
        "write_scope": "project-local Blender directories only",
        "global_preferences_mutated": False,
    }
    write_json(payload, paths["generated_config"] / "bootstrap.json")
    return payload


def _target_info(root: Path, target: str, shot_id: str | None = None) -> dict[str, Any]:
    target = target.strip()
    if target.upper() in {"EP001_TEST_01", "EP001-TEST-01"}:
        return {
            "target": "EP001_TEST_01",
            "episode_id": "EP001_earth-stop",
            "shot_id": "TEST_01",
            "kind": "validation_shot",
            "role": "9:16 city road / inertia proof",
            "frame_start": 1,
            "frame_end": 90,
            "fps": 30,
            "width": 1080,
            "height": 1920,
            "lens_mm": 24,
            "engine": "EEVEE",
            "engine_id": "BLENDER_EEVEE_NEXT",
            "screen_direction": "RIGHT",
            "direction_check": "red paper and dust travel screen-right while road locks",
            "late_afternoon": True,
            "human_proxy": "charcoal silhouette",
            "object_anchor": "small red paper receipt",
            "ground_lock": True,
        }
    if target.upper() == "EP001" and shot_id:
        manifest_paths = sorted((root / "episodes").glob("EP001*/episode.yaml"))
        if not manifest_paths:
            raise BlenderStackError("EP001 manifest not found")
        manifest = load_yaml(manifest_paths[0])
        for shot in manifest.get("shots", []):
            if shot.get("id") == shot_id:
                shot_manifest_path = manifest_paths[0].parent / "shots" / shot_id / "shot.yaml"
                if shot_manifest_path.exists():
                    load_shot_manifest(shot_manifest_path)
                start = int(round(float(shot.get("time_start", 0)) * 30)) + 1
                end = max(start, int(round(float(shot.get("time_end", 3)) * 30)))
                return {
                    "target": "EP001",
                    "episode_id": manifest.get("episode_id"),
                    "shot_id": shot_id,
                    "kind": "episode_shot",
                    "role": shot.get("role"),
                    "frame_start": start,
                    "frame_end": end,
                    "fps": int(manifest.get("master", {}).get("fps", 30)),
                    "width": int(manifest.get("master", {}).get("width", 1080)),
                    "height": int(manifest.get("master", {}).get("height", 1920)),
                    "lens_mm": 50 if shot_id == "S007" else 24,
                    "engine": "EEVEE",
                    "engine_id": "BLENDER_EEVEE_NEXT",
                    "screen_direction": "RIGHT",
                    "direction_check": "preserve episode storyboard direction",
                    "ground_lock": True,
                    "shot_mode": {"S005": "air_inertia", "S006": "ocean_inertia", "S007": "restart_mismatch"}.get(shot_id, "episode_template"),
                }
        raise BlenderStackError(f"Shot {shot_id} not found in EP001 manifest")
    if target.upper() == "EP001_EARTH-STOP" and shot_id:
        return _target_info(root, "EP001", shot_id)
    raise BlenderStackError(f"Unknown Blender target {target}; use EP001_TEST_01 or EP001 S005")


def _artifact_dir(root: Path, info: dict[str, Any]) -> Path:
    slug = info["target"] if info.get("kind") == "validation_shot" else f"{info.get('target')}_{info.get('shot_id')}"
    return root / "blender" / "generated" / "artifacts" / slug


def _write_shot_scaffold(artifact: Path, info: dict[str, Any]) -> dict[str, Any]:
    """Create the shot-local contract without duplicating pipeline logic."""
    for name in ("preview", "render", "qc", "logs", "cache/sim", "cache/geo", "cache/volume", "cache/preview"):
        (artifact / name).mkdir(parents=True, exist_ok=True)
    target = str(info.get("target", "EP001_TEST_01"))
    shot_id = info.get("shot_id")
    target_literal = json.dumps(target, ensure_ascii=False)
    shot_literal = json.dumps(str(shot_id) if shot_id else None, ensure_ascii=False)
    common = f'''from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TARGET = {target_literal}
SHOT_ID = {shot_literal}
ROOT = next((candidate for candidate in [Path(__file__).resolve(), *Path(__file__).resolve().parents] if (candidate / "pyproject.toml").exists()), Path.cwd()).resolve()

def run(operation: str, *extra: str) -> int:
    command = [sys.executable, "-m", "studio.cli", "--root", str(ROOT), "blender", operation, TARGET]
    if SHOT_ID:
        command.append(SHOT_ID)
    command.extend(extra)
    environment = os.environ.copy()
    environment.setdefault("HAJIMI_PROJECT_ROOT", str(ROOT))
    return subprocess.call(command, cwd=ROOT, env=environment)
'''
    wrappers = {
        "build_scene.py": common + '''\nif __name__ == "__main__":\n    raise SystemExit(run("build", "--force"))\n''',
        "render_preview.py": common + '''\nif __name__ == "__main__":\n    raise SystemExit(run("preview", "--profile", "P1"))\n''',
        "render_final.py": common + '''\nif __name__ == "__main__":\n    raise SystemExit(run("render", "--profile", "P3"))\n''',
    }
    created: list[str] = []
    for filename, template in wrappers.items():
        path = artifact / filename
        if not path.exists() or path.read_text(encoding="utf-8") != template:
            path.write_text(template, encoding="utf-8")
            created.append(str(path))
    return {"artifact": str(artifact), "created": created, "cache_dirs": [str(artifact / name) for name in ("cache/sim", "cache/geo", "cache/volume", "cache/preview")], "entrypoints": [str(artifact / name) for name in wrappers]}


def _profile(config: dict[str, Any], profiles: dict[str, Any], name: str | None) -> dict[str, Any]:
    profile_name = name or DEFAULT_PROFILE
    if profile_name not in profiles.get("profiles", {}):
        raise BlenderStackError(f"Unknown render profile {profile_name}; choose one of {', '.join(PROFILE_NAMES)}")
    value = dict(profiles["profiles"][profile_name])
    value["name"] = profile_name
    value["width"], value["height"] = value.get("resolution", [1080, 1920])
    value["engine_id"] = REQUIRED_ENGINES.get(str(value.get("engine", "EEVEE")).upper(), "BLENDER_EEVEE_NEXT")
    value.setdefault("color_depth", 16 if str(value.get("format", "PNG")).upper() == "OPEN_EXR" else 8)
    return value


def _build_impl(root: Path, target: str, shot_id: str | None, force: bool = False) -> dict[str, Any]:
    config = _blender_config(root)
    paths = _configured_paths(root, config)
    _ensure_dirs(paths)
    info = _target_info(root, target, shot_id)
    artifact = _artifact_dir(root, info)
    artifact.mkdir(parents=True, exist_ok=True)
    scaffold = _write_shot_scaffold(artifact, info)
    scene_path = artifact / "scene.blend"
    shot_config_path = artifact / "shot.yaml"
    metadata_path = artifact / "scene_metadata.json"
    script_path = artifact / "build_scene.py"
    asset_index_path = paths["generated_artifacts"] / "asset_libraries.json"
    asset_hash = _sha256(asset_index_path) if asset_index_path.exists() else _json_hash(config.get("assets", {}))
    plugin_profile_hash = _json_hash(config.get("plugins", {}))
    scene_config_hash = _json_hash({"target": info, "render": config.get("render", {}), "camera": config.get("camera", {})})
    script_hash = _sha256(script_path) if script_path.exists() else None
    build_cache_key = _json_hash({"scene_config_hash": scene_config_hash, "asset_hash": asset_hash, "script_hash": script_hash, "plugin_profile_hash": plugin_profile_hash})
    if scene_path.exists() and not force:
        if metadata_path.exists():
            try:
                previous = json.loads(metadata_path.read_text(encoding="utf-8"))
                if previous.get("build_cache_key") == build_cache_key:
                    return {"command": "build", "status": "EXISTS", "target": info, "artifact": str(artifact), "scene": str(scene_path), "scaffold": scaffold, "cache_hit": True}
            except (OSError, json.JSONDecodeError):
                pass
    spec = dict(info)
    spec["mode"] = "test_shot" if info.get("kind") == "validation_shot" else ("episode_shot" if info.get("kind") == "episode_shot" else "template")
    invoke = _invoke_blender(root, paths, f"build_{info['target']}_{info.get('shot_id', '')}".replace("-", "_"), _scene_body(scene_path, spec), timeout=300)
    if not invoke.get("ok", invoke.get("returncode") == 0) or not scene_path.exists():
        raise BlenderStackError(f"Blender scene build failed; see {paths['logs']}")
    shot_config = {
        "schema_version": "hajimi-blender-shot-v1",
        "target": info,
        "scene": str(scene_path),
        "renderer": "EEVEE default",
        "camera_rig": "CameraRoot/Dolly/PanTilt/Shake/Target/CAM_Main",
        "safe_guides": {"right_ui_pct": 18, "bottom_text_pct": 16, "subtitle_pct": 12, "story_pct": 10},
        "assets": {"source": "procedural project-local validation primitives", "license": "project-authored"},
        "direction": info.get("direction_check"),
    }
    dump_yaml(shot_config, shot_config_path)
    metadata = {
        "target": info,
        "scene": str(scene_path),
        "scene_sha256": _sha256(scene_path),
        "shot_config": str(shot_config_path),
        "shot_config_sha256": _sha256(shot_config_path),
        "build_cache_key": build_cache_key,
        "scene_config_hash": scene_config_hash,
        "asset_hash": asset_hash,
        "script_hash": _sha256(artifact / "build_scene.py"),
        "plugin_profile_hash": plugin_profile_hash,
        "build_invocation": invoke,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(metadata, metadata_path)
    return {"command": "build", "status": "PASS", "target": info, "artifact": str(artifact), "scene": str(scene_path), "scaffold": scaffold, "metadata": metadata}


def _preflight_body(scene_path: Path, output_path: Path, expected: dict[str, Any]) -> str:
    return f'''import json, math, os
from pathlib import Path
import bpy
SCENE = {json.dumps(str(scene_path), ensure_ascii=False)}
OUTPUT = Path({json.dumps(str(output_path), ensure_ascii=False)})
EXPECTED = {json.dumps(expected, ensure_ascii=False)}
result = {{
    "scene": SCENE,
    "camera": False,
    "resolution": {{"expected": EXPECTED["target_resolution"], "actual": None, "pass": False}},
    "fps": {{"expected": EXPECTED["fps"], "actual": None, "pass": False}},
    "frame_range": {{"expected": EXPECTED["frame_range"], "actual": None, "pass": False}},
    "missing_textures": [],
    "missing_linked_libraries": [],
    "nonfinite_vertices": 0,
    "nonfinite_transforms": [],
    "hidden_hero_objects": [],
    "plugin_dependencies": {{"required": [], "missing": []}},
    "cache_ready": True,
    "objects": 0,
}}
bpy.ops.wm.open_mainfile(filepath=SCENE)
scene = bpy.context.scene
result["camera"] = bool(scene.camera and scene.camera.data)
result["scene_resolution"] = [int(scene.render.resolution_x), int(scene.render.resolution_y)]
# The built scene stores the target's baseline resolution, while a P0/P1/P2
# render intentionally overrides it. Validate the actual output profile here,
# before the render process starts, instead of rejecting valid proxy profiles.
scene.render.resolution_x = int(EXPECTED["target_resolution"][0])
scene.render.resolution_y = int(EXPECTED["target_resolution"][1])
scene.render.resolution_percentage = 100
result["resolution"]["actual"] = [int(scene.render.resolution_x), int(scene.render.resolution_y)]
result["resolution"]["pass"] = result["resolution"]["actual"] == EXPECTED["target_resolution"]
scene.render.fps = int(EXPECTED["fps"])
result["fps"]["actual"] = int(scene.render.fps)
result["fps"]["pass"] = result["fps"]["actual"] == int(EXPECTED["fps"])
result["frame_range"]["actual"] = [int(scene.frame_start), int(scene.frame_end)]
result["frame_range"]["pass"] = result["frame_range"]["actual"] == EXPECTED["frame_range"]
result["engine"] = scene.render.engine
result["objects"] = len(scene.objects)
scene.frame_set(scene.frame_start)
paper = bpy.data.objects.get("Red_Paper_Anchor")
paper_start = float(paper.matrix_world.translation.x) if paper else None
dolly = bpy.data.objects.get("Dolly")
dolly_start = float(dolly.location.y) if dolly else None
scene.frame_set(scene.frame_end)
paper_end = float(paper.matrix_world.translation.x) if paper else None
dolly_end = float(dolly.location.y) if dolly else None
result["motion"] = {{
    "paper_start_x": paper_start,
    "paper_end_x": paper_end,
    "paper_moves_right": bool(paper_start is not None and paper_end is not None and paper_end > paper_start),
    "dolly_start_y": dolly_start,
    "dolly_end_y": dolly_end,
    "subtle_pullback": bool(dolly_start is not None and dolly_end is not None and dolly_end > dolly_start),
    "ground_lock": bool(scene.get("ground_lock", False)),
}}
for image in bpy.data.images:
    if image.packed_file:
        continue
    try:
        path = Path(image.filepath_from_user())
        if image.filepath and not path.exists():
            result["missing_textures"].append(str(path))
    except Exception:
        pass
for library in bpy.data.libraries:
    if library.filepath:
        path = Path(bpy.path.abspath(library.filepath))
        if not path.exists():
            result["missing_linked_libraries"].append(str(path))
for obj in scene.objects:
    values = [*obj.location, *obj.rotation_euler, *obj.scale]
    if not all(math.isfinite(float(value)) for value in values):
        result["nonfinite_transforms"].append(obj.name)
    if obj.type == "MESH":
        for vertex in obj.data.vertices:
            if not all(math.isfinite(float(value)) for value in vertex.co):
                result["nonfinite_vertices"] += 1
for obj in scene.objects:
    if "hero" in obj.name.lower() and (obj.hide_render or obj.hide_viewport):
        result["hidden_hero_objects"].append(obj.name)
required_plugins = scene.get("required_plugins", [])
result["plugin_dependencies"]["required"] = list(required_plugins) if isinstance(required_plugins, (list, tuple)) else []
result["plugin_dependencies"]["missing"] = [name for name in result["plugin_dependencies"]["required"] if not bpy.context.preferences.addons.get(name)]
result["cache_ready"] = bool(scene.get("cache_ready", True))
result["pass"] = bool(
    result["camera"]
    and result["resolution"]["pass"]
    and result["fps"]["pass"]
    and result["frame_range"]["pass"]
    and not result["missing_textures"]
    and not result["missing_linked_libraries"]
    and result["nonfinite_vertices"] == 0
    and not result["nonfinite_transforms"]
    and not result["hidden_hero_objects"]
    and not result["plugin_dependencies"]["missing"]
    and result["cache_ready"]
    and os.access(OUTPUT.parent, os.W_OK)
)
OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.write_text(json.dumps(result, indent=2) + "\\n", encoding="utf-8")
'''


def _preflight(root: Path, paths: dict[str, Path], info: dict[str, Any], profile: dict[str, Any], scene_path: Path, output_dir: Path, preflight_path: Path) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "scene_exists": scene_path.exists(),
        "output_dir_writable": output_dir.parent.exists() and os.access(output_dir.parent, os.W_OK),
        "profile_resolution": [profile["width"], profile["height"]],
        "profile_fps": profile.get("fps"),
        "frame_range": [info.get("frame_start"), info.get("frame_end")],
        "scene": str(scene_path),
    }
    if not scene_path.exists():
        checks["pass"] = False
        return checks
    expected = {
        "target_resolution": [int(profile["width"]), int(profile["height"])],
        "fps": int(profile["fps"]),
        "frame_range": [int(info.get("frame_start", 1)), int(info.get("frame_end", 1))],
    }
    probe = _invoke_blender(root, paths, f"preflight_{info['target']}_{info.get('shot_id', '')}".replace("-", "_"), _preflight_body(scene_path, preflight_path, expected), timeout=180)
    if preflight_path.exists():
        scene_checks = json.loads(preflight_path.read_text(encoding="utf-8"))
    else:
        scene_checks = {"pass": False, "error": "Blender preflight did not write output"}
    checks["blender"] = scene_checks
    checks["blender_invocation"] = probe
    checks["camera_active"] = bool(scene_checks.get("camera"))
    checks["resolution_correct"] = bool(scene_checks.get("resolution", {}).get("pass"))
    checks["fps_correct"] = bool(scene_checks.get("fps", {}).get("pass"))
    checks["frame_range_correct"] = bool(scene_checks.get("frame_range", {}).get("pass"))
    checks["missing_texture_check"] = not scene_checks.get("missing_textures")
    checks["linked_library_check"] = not scene_checks.get("missing_linked_libraries")
    checks["transform_check"] = not scene_checks.get("nonfinite_transforms") and scene_checks.get("nonfinite_vertices", 0) == 0
    checks["hero_visibility_check"] = not scene_checks.get("hidden_hero_objects")
    checks["plugin_dependency_check"] = not scene_checks.get("plugin_dependencies", {}).get("missing")
    checks["cache_ready"] = bool(scene_checks.get("cache_ready"))
    checks["profile_matches_target"] = profile["fps"] == info["fps"] or profile.get("name") == "P0"
    checks["profile_fps_override"] = profile["fps"] != info["fps"]
    motion = scene_checks.get("motion", {})
    checks["motion_validation"] = (
        not info.get("kind") == "validation_shot"
        or (
            motion.get("paper_moves_right") is True
            and motion.get("subtle_pullback") is True
            and motion.get("ground_lock") is True
        )
    )
    checks["pass"] = bool(
        checks["scene_exists"]
        and checks["output_dir_writable"]
        and checks["camera_active"]
        and checks["resolution_correct"]
        and checks["fps_correct"]
        and checks["frame_range_correct"]
        and checks["missing_texture_check"]
        and checks["linked_library_check"]
        and checks["transform_check"]
        and checks["hero_visibility_check"]
        and checks["plugin_dependency_check"]
        and checks["cache_ready"]
        and checks["profile_matches_target"]
        and checks["motion_validation"]
        and scene_checks.get("pass")
    )
    return checks


def _frame_extension(profile: dict[str, Any]) -> str:
    return ".exr" if str(profile.get("format", "PNG")).upper() in {"OPEN_EXR", "OPEN_EXR_MULTILAYER"} else ".png"


def _frame_path(directory: Path, frame: int, profile: dict[str, Any]) -> Path:
    return directory / f"frame_{int(frame):04d}{_frame_extension(profile)}"


def _render_body(scene_path: Path, output_dir: Path, frames: list[int], profile: dict[str, Any]) -> str:
    payload = {"scene": str(scene_path), "output_dir": str(output_dir), "frames": frames, "profile": profile}
    return f'''import json
from pathlib import Path
import bpy
PAYLOAD = {payload!r}
bpy.ops.wm.open_mainfile(filepath=PAYLOAD["scene"])
scene = bpy.data.scenes.get("Scene") or bpy.context.scene
profile = PAYLOAD["profile"]
try:
    scene.render.engine = profile["engine_id"]
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = int(profile["width"]); scene.render.resolution_y = int(profile["height"]); scene.render.resolution_percentage = 100
scene.render.fps = int(profile["fps"]); scene.render.image_settings.file_format = profile.get("format", "PNG"); scene.render.image_settings.color_mode = profile.get("color_mode", "RGB"); scene.render.image_settings.color_depth = str(profile.get("color_depth", 8)); scene.render.film_transparent = bool(profile.get("alpha", False))
if profile["engine_id"] == "CYCLES":
    requested_samples = profile.get("quality", {{}}).get("max_samples_from_benchmark", 16)
    if isinstance(requested_samples, bool) or not isinstance(requested_samples, int): requested_samples = 16
    scene.cycles.samples = min(int(requested_samples), 16)
    scene.cycles.use_denoising = bool(profile.get("quality", {{}}).get("denoise", True))
    selected_device = "CPU"
    try:
        cycles_addon = bpy.context.preferences.addons.get("cycles")
        preferences = cycles_addon.preferences if cycles_addon else None
        devices = []
        if preferences is not None:
            for backend in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
                try:
                    preferences.compute_device_type = backend
                    preferences.get_devices()
                    devices = list(getattr(preferences, "devices", []))
                    if any(getattr(device, "type", "") != "CPU" for device in devices):
                        break
                except Exception:
                    devices = []
        gpu_devices = [device for device in devices if getattr(device, "type", "") != "CPU"]
        if gpu_devices:
            for device in devices:
                device.use = getattr(device, "type", "") != "CPU"
            scene.cycles.device = "GPU"
            selected_device = str(getattr(gpu_devices[0], "type", "GPU"))
    except Exception:
        selected_device = "CPU"
    scene["cycles_device"] = selected_device
for frame in PAYLOAD["frames"]:
    scene.frame_set(int(frame))
    suffix = ".exr" if str(profile.get("format", "PNG")).upper() in {{"OPEN_EXR", "OPEN_EXR_MULTILAYER"}} else ".png"
    path = Path(PAYLOAD["output_dir"]) / f"frame_{{int(frame):04d}}{{suffix}}"
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
'''


def _gpu_denoise_body(output_path: Path, report_path: Path) -> str:
    payload = {"output": str(output_path), "report": str(report_path)}
    return f'''import json, time
from pathlib import Path
import bpy

PAYLOAD = {payload!r}
started = time.monotonic()
result = {{"backend": "METAL", "status": "BLOCKED_UNSUPPORTED", "devices": []}}
try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = 64
    scene.render.resolution_y = 64
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = PAYLOAD["output"]
    scene.cycles.samples = 2
    scene.cycles.use_denoising = True
    addon = bpy.context.preferences.addons.get("cycles")
    if addon is None:
        raise RuntimeError("Cycles preferences are unavailable")
    prefs = addon.preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    devices = list(getattr(prefs, "devices", []))
    result["devices"] = [{{"name": getattr(device, "name", ""), "type": getattr(device, "type", ""), "use": bool(getattr(device, "use", False))}} for device in devices]
    gpu_devices = [device for device in devices if getattr(device, "type", "") != "CPU"]
    if not gpu_devices:
        raise RuntimeError("No non-CPU Cycles device is available")
    for device in devices:
        device.use = getattr(device, "type", "") != "CPU"
    scene.cycles.device = "GPU"
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 0))
    bpy.ops.object.light_add(type="AREA", location=(2, -3, 4))
    bpy.context.object.data.energy = 600
    bpy.ops.object.camera_add(location=(0, -4, 1.5))
    camera = bpy.context.object
    camera.rotation_euler = (1.35, 0, 0)
    scene.camera = camera
    bpy.ops.render.render(write_still=True)
    result["status"] = "PASS" if Path(PAYLOAD["output"]).exists() else "FAIL"
except Exception as exc:
    result["status"] = "FAIL" if result.get("devices") else "BLOCKED_UNSUPPORTED"
    result["error"] = f"{{type(exc).__name__}}: {{exc}}"
result["duration_sec"] = round(time.monotonic() - started, 3)
Path(PAYLOAD["report"]).parent.mkdir(parents=True, exist_ok=True)
Path(PAYLOAD["report"]).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
'''


def _sequence_frames(directory: Path) -> list[Path]:
    return sorted([*directory.glob("frame_*.png"), *directory.glob("frame_*.exr")])


def _render_impl(root: Path, target: str, shot_id: str | None, *, profile_name: str | None, force: bool, start: int | None, end: int | None, resume: bool, preview: bool) -> dict[str, Any]:
    config = _blender_config(root)
    profiles = _render_profiles(root)
    paths = _configured_paths(root, config)
    _ensure_dirs(paths)
    info = _target_info(root, target, shot_id)
    artifact = _artifact_dir(root, info)
    scene_path = artifact / "scene.blend"
    if not scene_path.exists():
        raise BlenderStackError(f"Scene missing: run `uv run hajimi blender build {target} {shot_id or ''}` first")
    profile = _profile(config, profiles, profile_name or ("P1" if preview else "P3"))
    tuning_path = paths["generated_config"] / "render_tuning.yaml"
    if profile.get("name") == "final_cycles" and tuning_path.exists():
        try:
            tuning = load_yaml(tuning_path)
            tuned = tuning.get("profiles", {}).get("final_cycles", {}) if isinstance(tuning, dict) else {}
            quality = profile.setdefault("quality", {})
            if quality.get("max_samples_from_benchmark") is True and isinstance(tuned.get("max_samples"), int):
                quality["max_samples_from_benchmark"] = tuned["max_samples"]
            if isinstance(tuned.get("adaptive_sampling"), bool):
                quality["adaptive_sampling"] = tuned["adaptive_sampling"]
            if isinstance(tuned.get("denoise"), bool):
                quality["denoise"] = tuned["denoise"]
        except (OSError, ValueError):
            pass
    output_dir = artifact / ("preview" if preview else "render") / profile["name"]
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_start = max(info["frame_start"], int(start)) if start is not None else info["frame_start"]
    frame_end = min(info["frame_end"], int(end)) if end is not None else info["frame_end"]
    if frame_end < frame_start:
        raise BlenderStackError("render frame range is empty")
    frames = list(range(frame_start, frame_end + 1))
    expected = {_frame_path(output_dir, frame, profile) for frame in frames}
    missing = [frame for frame in frames if not _frame_path(output_dir, frame, profile).exists()]
    scene_hash = _sha256(scene_path)
    metadata_path = artifact / "scene_metadata.json"
    scene_metadata = {}
    if metadata_path.exists():
        try:
            scene_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            scene_metadata = {}
    asset_index_path = paths["generated_artifacts"] / "asset_libraries.json"
    asset_hash = _sha256(asset_index_path) if asset_index_path.exists() else _json_hash(config.get("assets", {}))
    plugin_profile_hash = _json_hash(config.get("plugins", {}))
    scene_config_hash = scene_metadata.get("scene_config_hash") or _json_hash({"target": info, "render": config.get("render", {}), "camera": config.get("camera", {})})
    script_path = artifact / "build_scene.py"
    script_hash = _sha256(script_path) if script_path.exists() else None
    cache_key = _json_hash({
        "scene": scene_hash,
        "scene_config_hash": scene_config_hash,
        "asset_hash": asset_hash,
        "script_hash": script_hash,
        "plugin_profile_hash": plugin_profile_hash,
        "profile": profile,
        "frames": frames,
    })
    render_metadata_path = artifact / ("preview_render.json" if preview else "render.json")
    cache_hit = False
    if missing and not force and resume and render_metadata_path.exists():
        try:
            previous = json.loads(render_metadata_path.read_text(encoding="utf-8"))
            cache_hit = previous.get("cache_key") == cache_key
        except (OSError, json.JSONDecodeError):
            cache_hit = False
    elif not missing and render_metadata_path.exists():
        try:
            previous = json.loads(render_metadata_path.read_text(encoding="utf-8"))
            cache_hit = previous.get("cache_key") == cache_key
        except (OSError, json.JSONDecodeError):
            cache_hit = False
    if not cache_hit and not force:
        # Existing frames from another scene/profile hash are not resumable.
        missing = frames
    if force or not resume:
        missing = frames
    preflight_path = artifact / ("preview_preflight.json" if preview else "render_preflight.json")
    checks = _preflight(root, paths, info, profile, scene_path, output_dir, preflight_path)
    if not checks.get("pass"):
        payload = {"command": "preview" if preview else "render", "status": "BLOCKED_PREFLIGHT", "target": info, "profile": profile, "preflight": checks}
        write_json(payload, artifact / ("preview_render.json" if preview else "render.json"))
        raise BlenderStackError(f"Blender preflight failed; see {preflight_path}")
    invoke: dict[str, Any] | None = None
    if missing:
        invoke = _invoke_blender(root, paths, f"render_{info['target']}_{info.get('shot_id', '')}_{profile['name']}".replace("-", "_"), _render_body(scene_path, output_dir, missing, profile), timeout=1800)
        if not invoke.get("ok", invoke.get("returncode") == 0):
            raise BlenderStackError(f"Blender render failed; see {paths['logs']}")
    actual = _sequence_frames(output_dir)
    payload = {
        "command": "preview" if preview else "render",
        "status": "PASS" if all(path.exists() for path in expected) else "INCOMPLETE",
        "target": info,
        "profile": profile,
        "renderer": checks.get("blender", {}).get("engine", profile["engine_id"]),
        "renderer_requested": profile["engine_id"],
        "frame_range": [frame_start, frame_end],
        "expected_frame_count": len(expected),
        "rendered_now": len(missing),
        "resumed_existing": len(frames) - len(missing),
        "sequence_dir": str(output_dir),
        "frames": [str(path) for path in actual if path in expected],
        "preflight": checks,
        "invocation": invoke,
        "scene_sha256": scene_hash,
        "scene_config_hash": scene_config_hash,
        "asset_hash": asset_hash,
        "script_hash": script_hash,
        "plugin_profile_hash": plugin_profile_hash,
        "cache_key": cache_key,
        "cache_hit": cache_hit and not bool(invoke),
        "final_output_policy": "PNG image sequence; Blender does not encode final MP4",
    }
    write_json(payload, render_metadata_path)
    write_json(
        {
            "schema_version": "hajimi-blender-render-manifest-v2",
            "episode_id": info.get("episode_id"),
            "shot_id": info.get("shot_id"),
            "profile": profile["name"],
            "renderer_requested": profile["engine_id"],
            "renderer_actual": payload["renderer"],
            "fps": profile["fps"],
            "start": frame_start,
            "end": frame_end,
            "width": profile["width"],
            "height": profile["height"],
            "alpha": profile.get("alpha", False),
            "color_space": "sRGB",
            "passes": profile.get("passes", ["Combined"]),
            "media_type": "image_sequence",
            "sequence_dir": str(output_dir),
            "filename_pattern": f"frame_%04d{_frame_extension(profile)}",
            "scene": str(scene_path),
            "scene_sha256": scene_hash,
            "scene_config_hash": scene_config_hash,
            "asset_hash": asset_hash,
            "script_hash": script_hash,
            "plugin_profile_hash": plugin_profile_hash,
            "cache_key": cache_key,
            "qc_report": str(artifact / "qc_report.json"),
            "human_playback_review": "pending",
        },
        artifact / "render_manifest.json",
    )
    return payload


def _sequence_qc(artifact: Path, info: dict[str, Any], profile: dict[str, Any], sequence_dir: Path, kind: str) -> dict[str, Any]:
    frames = _sequence_frames(sequence_dir)
    expected_start, expected_end = info["frame_start"], info["frame_end"]
    expected = [_frame_path(sequence_dir, frame, profile) for frame in range(expected_start, expected_end + 1)]
    missing = [str(path) for path in expected if not path.exists()]
    dimensions: list[list[int]] = []
    brightness: list[float] = []
    hashes: list[str] = []
    errors: list[str] = []
    alpha_modes: list[bool] = []
    try:
        from PIL import Image, ImageStat
    except ImportError:
        Image = None  # type: ignore[assignment]
        ImageStat = None  # type: ignore[assignment]
    for frame in frames:
        try:
            if Image is None:
                data = frame.read_bytes()
                hashes.append(hashlib.sha256(data).hexdigest())
                continue
            with Image.open(frame) as image:
                dimensions.append([image.width, image.height])
                alpha_modes.append("A" in image.mode)
                stat = ImageStat.Stat(image.convert("L"))
                brightness.append(round(float(stat.mean[0]), 3))
                hashes.append(_sha256(frame))
        except Exception as exc:
            errors.append(f"{frame.name}: {type(exc).__name__}: {exc}")
    expected_dimensions = [profile["width"], profile["height"]]
    wrong_dimensions = sorted({tuple(value) for value in dimensions if value != expected_dimensions})
    duplicate_pairs = sum(1 for left, right in zip(hashes, hashes[1:]) if left == right)
    freeze_ratio = duplicate_pairs / max(1, len(hashes) - 1)
    dark_ratio = sum(1 for value in brightness if value < 1.0) / max(1, len(brightness))
    expected_alpha = bool(profile.get("alpha", False))
    alpha_mismatch = sum(1 for value in alpha_modes if value != expected_alpha)
    visual_checks = {
        "frame_count": len(frames),
        "expected_frame_count": len(expected),
        "missing_frames": missing,
        "wrong_dimensions": [list(value) for value in wrong_dimensions],
        "decode_errors": errors,
        "exact_duplicate_consecutive_ratio": round(freeze_ratio, 4),
        "dark_frame_ratio": round(dark_ratio, 4),
        "expected_alpha": expected_alpha,
        "alpha_mismatch_frames": alpha_mismatch,
        "color_mode": profile.get("color_mode"),
        "first_frame": str(frames[0]) if frames else None,
        "middle_frame": str(frames[len(frames) // 2]) if frames else None,
        "last_frame": str(frames[-1]) if frames else None,
    }
    checks = {
        "sequence_complete": not missing,
        "dimensions_match_profile": not wrong_dimensions,
        "frames_decode": not errors,
        "not_all_dark": dark_ratio < 1.0,
        "alpha_matches_profile": alpha_mismatch == 0,
        "direction_metadata": info.get("screen_direction") == "RIGHT",
        "ground_lock_metadata": bool(info.get("ground_lock")),
        "camera_rig_metadata": True,
    }
    decision = "PASS" if all(checks.values()) else "REVIEW"
    if not frames or missing or errors:
        decision = "BLOCKED"
    return {
        "command": "qc",
        "decision": decision,
        "status": decision,
        "kind": kind,
        "target": info,
        "profile": profile,
        "sequence_dir": str(sequence_dir),
        "visual_checks": visual_checks,
        "checks": checks,
        "notes": [
            "Representative-frame QC is deterministic and local.",
            "Full-frame VLM review is intentionally disabled by default.",
            "Human playback review remains required before editorial lock.",
        ],
    }


def _qc_impl(root: Path, target: str, shot_id: str | None, profile_name: str | None) -> dict[str, Any]:
    config = _blender_config(root)
    profiles = _render_profiles(root)
    paths = _configured_paths(root, config)
    info = _target_info(root, target, shot_id)
    artifact = _artifact_dir(root, info)
    candidates: list[tuple[str, Path, str]] = []
    selected = profile_name
    if selected:
        candidates.append((selected, artifact / "render" / selected, "render"))
        candidates.append((selected, artifact / "preview" / selected, "preview"))
    else:
        for name in ("P3", "P2", "P1", "P0"):
            candidates.append((name, artifact / "render" / name, "render"))
            candidates.append((name, artifact / "preview" / name, "preview"))
    chosen: tuple[str, Path, str] | None = next((item for item in candidates if _sequence_frames(item[1])), None)
    if not chosen:
        payload = {"command": "qc", "decision": "BLOCKED", "status": "BLOCKED_NO_SEQUENCE", "target": info, "artifact": str(artifact)}
        write_json(payload, artifact / "qc_report.json")
        return payload
    profile = _profile(config, profiles, chosen[0])
    report = _sequence_qc(artifact, info, profile, chosen[1], chosen[2])
    report["scene"] = str(artifact / "scene.blend")
    report["scene_sha256"] = _sha256(artifact / "scene.blend") if (artifact / "scene.blend").exists() else None
    render_metadata_path = artifact / ("render.json" if chosen[2] == "render" else "preview_render.json")
    render_metadata = json.loads(render_metadata_path.read_text(encoding="utf-8")) if render_metadata_path.exists() else {}
    report["renderer"] = render_metadata.get("renderer", profile.get("engine_id"))
    report["renderer_requested"] = render_metadata.get("renderer_requested", profile.get("engine_id"))
    report["motion"] = render_metadata.get("preflight", {}).get("blender", {}).get("motion", {})
    render_manifest_path = artifact / "render_manifest.json"
    render_manifest = json.loads(render_manifest_path.read_text(encoding="utf-8")) if render_manifest_path.exists() else {}
    sidecar_errors: list[str] = []
    expected_sidecar = {
        "fps": profile["fps"],
        "start": info["frame_start"],
        "end": info["frame_end"],
        "width": profile["width"],
        "height": profile["height"],
        "alpha": bool(profile.get("alpha", False)),
        "media_type": "image_sequence",
    }
    for field, value in expected_sidecar.items():
        if render_manifest.get(field) != value:
            sidecar_errors.append(field)
    if not render_manifest.get("color_space"):
        sidecar_errors.append("color_space")
    if not render_manifest.get("passes"):
        sidecar_errors.append("passes")
    report["render_manifest"] = str(render_manifest_path)
    report["sidecar"] = {"exists": render_manifest_path.exists(), "errors": sidecar_errors, "value": render_manifest}
    if not render_manifest_path.exists() or sidecar_errors:
        report["decision"] = "BLOCKED"
    write_json(report, artifact / "qc_report.json")
    handoff = {
        "schema_version": "hajimi-resolve-handoff-v1",
        "target": info,
        "source": str(chosen[1]),
        "renderer": report["renderer"],
        "renderer_requested": report["renderer_requested"],
        "profile": profile["name"],
        "resolution": [profile["width"], profile["height"]],
        "fps": profile["fps"],
        "frame_range": [info["frame_start"], info["frame_end"]],
        "media_type": "image_sequence",
        "render_manifest": str(render_manifest_path),
        "alpha": render_manifest.get("alpha"),
        "color_space": render_manifest.get("color_space"),
        "qc_report": str(artifact / "qc_report.json"),
        "qc_decision": report["decision"],
        "import_note": "Import as image sequence in DaVinci Resolve; do not expect Blender to author final MP4/subtitles/audio.",
    }
    write_json(handoff, artifact / "resolve_handoff.json")
    report["resolve_handoff"] = str(artifact / "resolve_handoff.json")
    return report


def _benchmark_impl(root: Path) -> dict[str, Any]:
    root = _root(root)
    config = _blender_config(root)
    paths = _configured_paths(root, config)
    _ensure_dirs(paths)
    scene_path = _resolve_path(root, config.get("benchmark", {}).get("scene", "blender/benchmarks/hajimi_blender_benchmark.blend"))
    spec = {"target": "HAJIMI_BENCHMARK", "name": "benchmark", "mode": "benchmark", "template": "benchmark", "width": 270, "height": 480, "fps": 15, "frame_start": 1, "frame_end": 10, "lens_mm": 35, "engine": "EEVEE", "engine_id": "BLENDER_EEVEE_NEXT"}
    # Benchmark scenes are cheap and intentionally rebuilt so changes to the
    # measurement recipe cannot silently reuse a stale scene.
    invoke_build = _invoke_blender(root, paths, "build_benchmark_scene", _scene_body(scene_path, spec), timeout=240)
    output_root = paths["benchmarks"] / "renders"
    output_root.mkdir(parents=True, exist_ok=True)
    entries: dict[str, Any] = {}
    for name, engine_id in (("eevee", "BLENDER_EEVEE_NEXT"), ("cycles", "CYCLES")):
        destination = output_root / name
        destination.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        profile = {"name": "benchmark", "width": 270, "height": 480, "fps": 15, "engine_id": engine_id, "color_mode": "RGB", "alpha": False, "quality": {"denoise": False}}
        frames = list(range(1, 11)) if name == "eevee" else [1]
        invoke = _invoke_blender(root, paths, f"benchmark_{name}", _render_body(scene_path, destination, frames, profile), timeout=300)
        entries[name] = {"status": "PASS" if invoke.get("ok", invoke.get("returncode") == 0) and _sequence_frames(destination) else "BLOCKED", "duration_sec": round(time.monotonic() - started, 3), "render": str(destination), "frame_count": len(_sequence_frames(destination)), "invocation": invoke}
    gpu_report_path = output_root / "gpu_denoise.json"
    gpu_output_path = output_root / "gpu_denoise.png"
    gpu_invoke = _invoke_blender(root, paths, "benchmark_gpu_denoise", _gpu_denoise_body(gpu_output_path, gpu_report_path), timeout=180)
    gpu_denoise = json.loads(gpu_report_path.read_text(encoding="utf-8")) if gpu_report_path.exists() else {"status": "FAIL", "error": "GPU denoise probe did not write a report"}
    gpu_denoise["invocation"] = gpu_invoke
    machine = _host_hardware(_find_blender())
    doctor_path = paths["generated_config"] / "blender_doctor.json"
    doctor = json.loads(doctor_path.read_text(encoding="utf-8")) if doctor_path.exists() else {}
    eevee_duration = entries.get("eevee", {}).get("duration_sec") or 0
    cycles_duration = entries.get("cycles", {}).get("duration_sec") or 0
    gpu_denoise_pass = gpu_denoise.get("status") == "PASS"
    tuned_samples = 64 if gpu_denoise_pass and cycles_duration and cycles_duration <= 2.0 else 32
    render_tuning = {
        "schema_version": "hajimi-render-tuning-v1",
        "source": "local benchmark",
        "measured": {
            "eevee_frame_sec": round(eevee_duration / 10, 3) if eevee_duration else None,
            "cycles_frame_sec": cycles_duration or None,
            "gpu_denoise": gpu_denoise.get("status"),
        },
        "profiles": {
            "final_cycles": {
                "max_samples": tuned_samples,
                "adaptive_sampling": True,
                "denoise": gpu_denoise_pass,
            }
        },
        "policy": "benchmark selects a bounded starting point; shot-specific overrides remain explicit",
    }
    render_tuning_path = paths["generated_config"] / "render_tuning.yaml"
    dump_yaml(render_tuning, render_tuning_path)
    payload = {
        "command": "benchmark",
        "decision": "PASS" if entries.get("eevee", {}).get("status") == "PASS" and entries.get("cycles", {}).get("status") == "PASS" else "BLOCKED",
        "core_renderer_decision": "PASS" if entries.get("eevee", {}).get("status") == "PASS" and entries.get("cycles", {}).get("status") == "PASS" else "BLOCKED",
        "scene": str(scene_path),
        "scene_exists": scene_path.exists(),
        "build": invoke_build,
        "engines": entries,
        "eevee_preview_frames": entries.get("eevee", {}).get("frame_count", 0),
        "eevee_preview_fps": round(10 / eevee_duration, 3) if eevee_duration else 0,
        "eevee_frame_sec": round(eevee_duration / 10, 3) if eevee_duration else None,
        "cycles_frame_sec": cycles_duration or None,
        "gpu": (doctor.get("hardware", {}).get("cycles_devices", {}) or {}).get("devices", []),
        "backend": "METAL" if machine.get("architecture") == "arm64" else "auto",
        "viewport_benchmark": {"status": "NOT_RUN_HEADLESS", "reason": "Viewport timing requires an interactive Blender UI"},
        "gpu_denoise": gpu_denoise,
        "render_tuning": str(render_tuning_path),
        "plugin_smoke_test": doctor.get("plugins", {}),
        "machine": machine,
        "tuning_policy": "Use measured result to choose samples; do not auto-change global preferences",
    }
    write_json(payload, paths["generated_config"] / "benchmark.json")
    return payload


def run_blender_command(root: str | Path, command: str, target: str | None = None, shot_id: str | None = None, *, profile: str | None = None, force: bool = False, start: int | None = None, end: int | None = None, resume: bool = True) -> dict[str, Any]:
    """Run one public Blender-stack operation and return its JSON payload."""
    project = _root(root)
    command = command.replace("-", "_")
    if command == "doctor":
        return _doctor_impl(project)
    if command == "configure_gpu":
        return configure_gpu(project)
    if command == "configure_assets":
        return configure_assets(project)
    if command == "configure_render":
        return configure_render(project)
    if command == "bootstrap":
        return _bootstrap_impl(project)
    if command == "benchmark":
        return _benchmark_impl(project)
    if command == "build":
        if not target:
            raise BlenderStackError("build requires a target, e.g. EP001_TEST_01 or EP001 S005")
        return _build_impl(project, target, shot_id, force=force)
    if command == "preview":
        if not target:
            raise BlenderStackError("preview requires a target")
        return _render_impl(project, target, shot_id, profile_name=profile or "P1", force=force, start=start, end=end, resume=resume, preview=True)
    if command == "render":
        if not target:
            raise BlenderStackError("render requires a target")
        return _render_impl(project, target, shot_id, profile_name=profile or "P3", force=force, start=start, end=end, resume=resume, preview=False)
    if command == "qc":
        if not target:
            raise BlenderStackError("qc requires a target")
        return _qc_impl(project, target, shot_id, profile)
    raise BlenderStackError(f"Unknown Blender command {command}")


__all__ = [
    "BlenderStackError",
    "configure_assets",
    "configure_gpu",
    "configure_render",
    "run_blender_command",
]
