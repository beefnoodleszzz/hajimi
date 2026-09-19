"""Hajimi skill inventory, runtime checks, and guarded upstream synchronization."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .config import load_yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = PROJECT_ROOT / "config" / "skill-sources.yaml"
ROUTING_PATH = PROJECT_ROOT / "config" / "skill-routing.yaml"
LOCK_PATH = PROJECT_ROOT / ".local" / "skill-lock.json"
IGNORED_PARTS = {".git", "__pycache__"}


def canonical_skill_root() -> Path:
    configured = os.environ.get("HAJIMI_SKILLS_ROOT")
    root = Path(configured).expanduser() if configured else Path.home() / ".agents" / "skills"
    return root.resolve()


def skill_tree_hash(root: str | Path) -> str:
    root = Path(root)
    digest = hashlib.sha256()
    files = []
    links = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if IGNORED_PARTS.intersection(relative.parts) or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            links.append(path)
        elif path.is_file():
            files.append(path)
    for path in sorted(links):
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0link\0" + str(path.readlink()).encode("utf-8") + b"\n")
    for path in sorted(files):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8") + b"\0file\0" + hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


def _sources() -> dict[str, Any]:
    value = load_yaml(SOURCES_PATH)
    if not isinstance(value, dict) or not isinstance(value.get("skills"), dict):
        raise ValueError("config/skill-sources.yaml must contain a skills mapping")
    return value


def _routing() -> dict[str, Any]:
    value = load_yaml(ROUTING_PATH)
    if not isinstance(value, dict) or not isinstance(value.get("stages"), dict):
        raise ValueError("config/skill-routing.yaml must contain a stages mapping")
    return value


def _lock() -> dict[str, Any]:
    if not LOCK_PATH.is_file():
        return {"schema_version": "hajimi-skill-lock-v1", "skills": {}}
    try:
        value = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"local skill lock is invalid JSON: {LOCK_PATH}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("skills"), dict):
        raise ValueError("local skill lock must contain a skills mapping")
    return value


def _consumer_roots() -> dict[str, Path]:
    home = Path.home()
    return {
        "codex": home / ".codex-shared" / "skills",
        "claude": home / ".claude" / "skills",
        # Gemini CLI discovers ~/.agents/skills directly. Mirroring those same
        # skills into ~/.gemini/skills creates runtime conflict warnings.
        "gemini": canonical_skill_root(),
    }


def shared_skill_identity(name: str) -> dict[str, Any]:
    metadata = _sources()["skills"].get(name)
    if not isinstance(metadata, dict) or metadata.get("scope") != "global":
        raise ValueError(f"skill {name} is not registered")
    skill_dir = canonical_skill_root() / name
    if not (skill_dir / "SKILL.md").is_file():
        raise FileNotFoundError(f"shared skill is missing: {name}")
    actual_hash = skill_tree_hash(skill_dir)
    expected_hash = metadata.get("content_sha256")
    if expected_hash and actual_hash != expected_hash:
        raise ValueError(f"shared skill content does not match the registry: {name}")
    return {
        "name": name,
        "repo": metadata.get("upstream_repo"),
        "commit": metadata.get("upstream_commit"),
        "content_sha256": actual_hash,
    }


def skills_doctor() -> dict[str, Any]:
    errors: list[str] = []
    checks: list[dict[str, Any]] = []
    try:
        sources = _sources()
        routing = _routing()
        lock = _lock()
    except (OSError, ValueError) as exc:
        return {"status": "FAIL", "errors": [str(exc)], "checks": []}

    root = canonical_skill_root()
    if not root.is_dir():
        errors.append("canonical shared skill root is missing")
    checks.append({"name": "canonical_root", "status": "PASS" if root.is_dir() else "FAIL"})
    source_skills = sources["skills"]
    shared_scope = "global"
    project_scope = "project"
    project_names: set[str] = set()
    empty_directories: list[str] = []
    content_owners: dict[str, str] = {}
    source_owners: dict[tuple[str, str, str], str] = {}
    duplicate_skills: set[str] = set()
    supported_sources = {"local", "upstream_git", "project_adapter"}
    for name, metadata in source_skills.items():
        source_type = metadata.get("source_type")
        scope = metadata.get("scope")
        if source_type not in supported_sources:
            errors.append(f"skill {name} has unsupported source_type {source_type!r}")
        if not metadata.get("role") or metadata.get("status") != "keep":
            errors.append(f"skill {name} is missing its role or keep status")
        content_hash = metadata.get("content_sha256")
        if isinstance(content_hash, str):
            previous = content_owners.get(content_hash)
            if previous and previous != name:
                duplicate_skills.update((previous, name))
            content_owners[content_hash] = name
        if source_type == "upstream_git":
            identity = (
                str(metadata.get("upstream_repo", "")),
                str(metadata.get("upstream_path", "")),
                str(metadata.get("upstream_commit", "")),
                name,
            )
            logical_source = identity[:3]
            previous = source_owners.get(logical_source)
            if previous and previous != name:
                duplicate_skills.update((previous, name))
            source_owners[logical_source] = name
        if scope == shared_scope:
            skill_dir = root / name
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                errors.append(f"canonical skill is missing {name}/SKILL.md")
                checks.append({"name": f"skill:{name}", "status": "FAIL"})
                continue
            actual_hash = skill_tree_hash(skill_dir)
            expected_hash = metadata.get("content_sha256")
            if expected_hash and actual_hash != expected_hash:
                errors.append(f"canonical skill content hash differs from registry: {name}")
            empty_directories.extend(
                str(Path("~/.agents/skills") / name / path.relative_to(skill_dir))
                for path in skill_dir.rglob("*")
                if path.is_dir() and not path.is_symlink() and not any(path.iterdir())
            )
            checks.append({"name": f"skill:{name}", "status": "PASS" if not expected_hash or actual_hash == expected_hash else "FAIL", "content_sha256": actual_hash})
        elif scope == project_scope:
            relative = metadata.get("path")
            if not isinstance(relative, str):
                errors.append(f"project skill {name} has no project-relative path")
                checks.append({"name": f"project_skill:{name}", "status": "FAIL"})
                continue
            skill_dir = (PROJECT_ROOT / relative).resolve()
            try:
                skill_dir.relative_to(PROJECT_ROOT.resolve())
            except ValueError:
                errors.append(f"project skill path escapes the repository: {name}")
                checks.append({"name": f"project_skill:{name}", "status": "FAIL"})
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                errors.append(f"project skill is missing SKILL.md: {relative}")
                checks.append({"name": f"project_skill:{name}", "status": "FAIL"})
                continue
            try:
                frontmatter = skill_file.read_text(encoding="utf-8").split("---", 2)[1]
                skill_name = next(line.split(":", 1)[1].strip() for line in frontmatter.splitlines() if line.startswith("name:"))
            except (IndexError, StopIteration):
                skill_name = ""
            if skill_name != name:
                errors.append(f"project skill frontmatter name differs from registry: {name}")
            expected_hash = metadata.get("content_sha256")
            actual_hash = skill_tree_hash(skill_dir)
            if expected_hash and actual_hash != expected_hash:
                errors.append(f"project skill content hash differs from registry: {name}")
            project_names.add(name)
            empty = [str(path.relative_to(skill_dir)) for path in skill_dir.rglob("*") if path.is_dir() and not path.is_symlink() and not any(path.iterdir())]
            empty_directories.extend(str(path.relative_to(PROJECT_ROOT)) for path in skill_dir.rglob("*") if path.is_dir() and not path.is_symlink() and not any(path.iterdir()))
            if empty:
                errors.append(f"project skill contains empty directories: {name}")
            checks.append({"name": f"project_skill:{name}", "status": "PASS" if skill_name == name and not empty and (not expected_hash or actual_hash == expected_hash) else "FAIL", "content_sha256": actual_hash})
        elif scope != shared_scope and scope != project_scope:
            errors.append(f"skill {name} has unsupported scope {scope!r}")

    stale_project_shared = sorted(project_names & {name for name, item in source_skills.items() if item.get("scope") == shared_scope})
    if stale_project_shared:
        errors.append(f"shared upstream skills are duplicated in project skills: {', '.join(stale_project_shared)}")
    checks.append({"name": "project_skill_names", "status": "PASS" if not stale_project_shared else "FAIL", "count": len(project_names)})
    project_skill_root = PROJECT_ROOT / ".agents" / "skills"
    discovered_project_names = {
        path.name for path in project_skill_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    } if project_skill_root.is_dir() else set()
    unregistered = sorted(discovered_project_names - project_names)
    missing_registered = sorted(project_names - discovered_project_names)
    if unregistered or missing_registered:
        errors.append(f"project skill inventory mismatch: unregistered={unregistered}; missing={missing_registered}")
    checks.append({"name": "project_skill_inventory", "status": "PASS" if not unregistered and not missing_registered else "FAIL", "count": len(discovered_project_names)})

    project_adapters = [
        (name, str(metadata.get("role", "")).strip().casefold())
        for name, metadata in source_skills.items()
        if metadata.get("scope") == project_scope and metadata.get("source_type") == "project_adapter"
    ]
    adapter_roles: dict[str, str] = {}
    for name, role in project_adapters:
        if role and role in adapter_roles:
            duplicate_skills.update((adapter_roles[role], name))
        if role:
            adapter_roles[role] = name
    if duplicate_skills:
        errors.append("duplicate skill source/content/adapter role: " + ", ".join(sorted(duplicate_skills)))
    checks.append({"name": "logical_duplicates", "status": "FAIL" if duplicate_skills else "PASS", "count": len(duplicate_skills)})
    if empty_directories:
        errors.append("empty managed skill directories: " + ", ".join(sorted(set(empty_directories))))
    checks.append({"name": "empty_managed_directories", "status": "FAIL" if empty_directories else "PASS", "count": len(set(empty_directories))})

    required_consumers = _consumer_roots()
    for name, metadata in source_skills.items():
        if metadata.get("scope") != shared_scope:
            continue
        canonical = root / name
        for consumer in metadata.get("consumers", []):
            consumer_root = required_consumers.get(consumer)
            installed = consumer_root / name if consumer_root else Path("/") / "missing"
            valid = bool(consumer_root and installed.is_dir() and (installed / "SKILL.md").is_file() and installed.resolve() == canonical.resolve())
            if not valid:
                errors.append(f"{consumer} does not resolve {name} to the canonical skill")
            checks.append({"name": f"consumer:{consumer}:{name}", "status": "PASS" if valid else "FAIL"})

    for consumer, consumer_root in required_consumers.items():
        names = [name for name, item in source_skills.items() if item.get("scope") == shared_scope and consumer in item.get("consumers", [])]
        broken = [name for name in names if (consumer_root / name).is_symlink() and not (consumer_root / name).exists()]
        if broken:
            errors.append(f"{consumer} has broken managed skill links: {', '.join(sorted(broken))}")
        checks.append({"name": f"broken_symlinks:{consumer}", "status": "PASS" if not broken else "FAIL", "count": len(broken)})

    gemini_alias_root = Path.home() / ".gemini" / "skills"
    gemini_duplicates = [
        name for name, item in source_skills.items()
        if item.get("scope") == shared_scope
        and (gemini_alias_root / name).exists()
    ] if gemini_alias_root.is_dir() else []
    if gemini_duplicates:
        errors.append(f"Gemini has redundant copies/links beside its canonical skills: {', '.join(sorted(gemini_duplicates))}")
    checks.append({"name": "gemini_no_duplicate_aliases", "status": "PASS" if not gemini_duplicates else "FAIL", "count": len(gemini_duplicates)})

    stages = routing.get("stages", {})
    for stage, contract in stages.items():
        if not isinstance(contract, dict) or not contract.get("gate"):
            errors.append(f"skill route stage {stage} lacks an explicit gate")
    routed_fields = {"specialists", "specialist", "director", "adapter", "methods", "contract", "qc", "optional_finish"}
    route_errors: list[str] = []
    def validate_route(value: Any, key: str = "") -> None:
        if key in routed_fields:
            values = value if isinstance(value, list) else [value]
            for routed_name in values:
                if isinstance(routed_name, str) and routed_name not in source_skills:
                    route_errors.append(routed_name)
        elif isinstance(value, dict):
            for child_key, child in value.items():
                validate_route(child, child_key)
    validate_route(stages)
    if route_errors:
        errors.append("skill route references unregistered skills: " + ", ".join(sorted(set(route_errors))))
    routing_passes = bool(stages) and all(isinstance(item, dict) and item.get("gate") for item in stages.values()) and not route_errors
    checks.append({"name": "routing_registry", "status": "PASS" if routing_passes else "FAIL"})

    for name, expected in lock.get("skills", {}).items():
        if name not in source_skills or source_skills[name].get("scope") == project_scope:
            continue
        current_dir = root / name
        current_hash = skill_tree_hash(current_dir) if current_dir.is_dir() else None
        if current_hash != expected.get("content_sha256"):
            errors.append(f"installed skill differs from local lock: {name}")
    checks.append({"name": "local_lock", "status": "PASS" if not any("local lock" in error for error in errors) else "FAIL"})
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "canonical_skills": sorted(name for name, item in source_skills.items() if item.get("scope") == shared_scope),
        "project_adapters": sorted(name for name, item in source_skills.items() if item.get("scope") == project_scope and item.get("source_type") == "project_adapter"),
        "missing_skills": sorted(missing_registered),
        "duplicate_skills": sorted(duplicate_skills),
        "broken_links": [check["name"] for check in checks if check["name"].startswith("broken_symlinks:") and check["status"] == "FAIL"],
        "empty_directories": sorted(set(empty_directories)),
        "upstream_status": {"status": "pinned; not fetched by doctor", "check_command": "hajimi skills updates"},
        "routing_status": "PASS" if routing_passes else "FAIL",
        "checks": checks,
    }


def skills_list() -> dict[str, Any]:
    sources = _sources()["skills"]
    routing = _routing()["stages"]
    rows: list[dict[str, Any]] = []
    for name, metadata in sources.items():
        consumers = metadata.get("consumers", []) if metadata.get("scope") == "project" else [consumer for consumer, root in _consumer_roots().items() if (root / name / "SKILL.md").is_file()]
        stages = [stage for stage, contract in routing.items() if name in json.dumps(contract, ensure_ascii=False)]
        rows.append({
            "name": name,
            "role": metadata.get("role"),
            "path": metadata.get("path", f"~/.agents/skills/{name}"),
            "scope": metadata.get("scope"),
            "source_type": metadata.get("source_type"),
            "upstream_repo": metadata.get("upstream_repo"),
            "upstream_commit": metadata.get("upstream_commit"),
            "version": metadata.get("version"),
            "content_sha256": metadata.get("content_sha256"),
            "status": metadata.get("status"),
            "stages": stages,
            "consumers": consumers,
        })
    return {"status": "PASS", "skills": rows}


def check_skill_updates(*, timeout: int = 30) -> dict[str, Any]:
    sources = _sources()["skills"]
    updates: list[dict[str, Any]] = []
    for name, metadata in sources.items():
        if metadata.get("scope") == "project":
            continue
        repo = metadata.get("upstream_repo")
        commit = metadata.get("upstream_commit")
        if not repo or not commit:
            updates.append({"name": name, "status": "UNTRACKED", "pinned_commit": commit})
            continue
        result = subprocess.run(["git", "ls-remote", "--symref", str(repo), "HEAD"], capture_output=True, text=True, timeout=timeout, check=False)
        if result.returncode:
            updates.append({"name": name, "status": "UNKNOWN", "error": result.stderr.strip() or "git ls-remote failed"})
            continue
        latest = next((line.split()[0] for line in result.stdout.splitlines() if line.strip().endswith("HEAD") and line.split()[0] != "ref:"), None)
        status = "UP_TO_DATE" if latest == commit else "UPDATE_AVAILABLE" if latest else "UNKNOWN"
        updates.append({"name": name, "status": status, "pinned_commit": commit, "latest_head": latest})
    return {"status": "PASS" if all(item["status"] != "UNKNOWN" for item in updates) else "PARTIAL", "updates": updates}


def _checkout_skill(repo: str, commit: str, subpath: str, parent: Path) -> Path:
    checkout = parent / "checkout"
    subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", repo, str(checkout)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(checkout), "fetch", "--quiet", "--depth=1", "origin", commit], check=True, capture_output=True, text=True)
    if subpath not in {"", "."}:
        subprocess.run(["git", "-C", str(checkout), "sparse-checkout", "init", "--cone"], check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(checkout), "sparse-checkout", "set", subpath], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(checkout), "checkout", "--quiet", "--detach", commit], check=True, capture_output=True, text=True)
    return checkout if subpath in {"", "."} else checkout / subpath


def sync_skills(names: list[str] | None = None) -> dict[str, Any]:
    registry = _sources()["skills"]
    lock = _lock()
    installed = lock.setdefault("skills", {})
    root = canonical_skill_root()
    selected = names or [name for name, entry in registry.items() if entry.get("source_type") == "upstream_git"]
    synced: list[dict[str, Any]] = []
    for name in selected:
        metadata = registry.get(name)
        if not isinstance(metadata, dict) or metadata.get("source_type") != "upstream_git":
            raise ValueError(f"{name} is not a pinned upstream skill")
        target = root / name
        current_hash = skill_tree_hash(target) if target.is_dir() and not target.is_symlink() else None
        previous = installed.get(name)
        expected_current = previous.get("content_sha256") if isinstance(previous, dict) else metadata.get("content_sha256")
        if current_hash is not None and current_hash != expected_current:
            raise RuntimeError(f"refusing to overwrite locally changed skill {name}; current content differs from its recorded lock")
        with tempfile.TemporaryDirectory(prefix="hajimi-skill-sync-") as temporary:
            temp_root = Path(temporary)
            source = _checkout_skill(str(metadata["upstream_repo"]), str(metadata["upstream_commit"]), str(metadata.get("upstream_path", ".")), temp_root)
            if not (source / "SKILL.md").is_file():
                raise RuntimeError(f"pinned upstream path has no SKILL.md: {name}")
            source_hash = skill_tree_hash(source)
            if source_hash != metadata.get("content_sha256"):
                raise RuntimeError(f"pinned upstream content hash differs from config for {name}; review source before sync")
            if current_hash == source_hash:
                result_path = target
            else:
                staged = root / f".{name}.sync-staging"
                retired = root / f".{name}.sync-retired"
                if staged.exists() or staged.is_symlink() or retired.exists() or retired.is_symlink():
                    raise RuntimeError(f"skill sync staging path already exists for {name}")
                shutil.copytree(
                    source,
                    staged,
                    symlinks=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
                )
                if target.exists():
                    os.replace(target, retired)
                try:
                    os.replace(staged, target)
                except OSError:
                    if retired.exists():
                        os.replace(retired, target)
                    raise
                if retired.exists():
                    shutil.rmtree(retired)
                result_path = target
            installed[name] = {
                "actual_path": str(result_path.resolve()),
                "upstream_repo": metadata["upstream_repo"],
                "upstream_path": metadata.get("upstream_path"),
                "upstream_commit": metadata["upstream_commit"],
                "content_sha256": source_hash,
                "last_synced": datetime.now(timezone.utc).isoformat(),
                "consumers": ["codex", "claude", "gemini"],
            }
            synced.append({"name": name, "status": "UP_TO_DATE" if current_hash == source_hash else "SYNCED", "content_sha256": source_hash})
    lock["schema_version"] = "hajimi-skill-lock-v1"
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "PASS", "skills": synced}


def write_initial_skill_lock() -> dict[str, Any]:
    """Capture the already audited install without changing skill contents."""

    registry = _sources()["skills"]
    root = canonical_skill_root()
    lock = {"schema_version": "hajimi-skill-lock-v1", "skills": {}}
    for name, metadata in registry.items():
        if metadata.get("scope") == "project":
            continue
        skill_dir = root / name
        if not (skill_dir / "SKILL.md").is_file():
            continue
        lock["skills"][name] = {
            "actual_path": str(skill_dir.resolve()),
            "upstream_repo": metadata.get("upstream_repo"),
            "upstream_path": metadata.get("upstream_path"),
            "upstream_commit": metadata.get("upstream_commit"),
            "content_sha256": skill_tree_hash(skill_dir),
            "last_synced": datetime.now(timezone.utc).isoformat(),
            "consumers": ["codex", "claude", "gemini"],
        }
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "PASS", "count": len(lock["skills"]), "lock_path": str(LOCK_PATH)}
