import copy
import json
from pathlib import Path

import yaml

import studio.skills as skill_ops
from studio.skills import skills_doctor, skills_list


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents" / "skills"
ROUTES = yaml.safe_load((ROOT / "config" / "skill-routing.yaml").read_text(encoding="utf-8"))
SOURCES = yaml.safe_load((ROOT / "config" / "skill-sources.yaml").read_text(encoding="utf-8"))


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"missing frontmatter opener: {path}"
    closing = text.find("\n---\n", 4)
    assert closing >= 0, f"missing frontmatter closer: {path}"
    body = text[4:closing]
    assert "\n---\n" not in body, f"nested/duplicate frontmatter: {path}"
    value = yaml.safe_load(body)
    assert isinstance(value, dict), f"frontmatter must be a mapping: {path}"
    return value


def test_all_project_skill_frontmatter_is_valid_and_unique() -> None:
    names: list[str] = []
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        value = _frontmatter(path)
        assert isinstance(value.get("name"), str) and value["name"].strip()
        assert value["name"] == path.parent.name
        assert set(value) <= {"name", "description", "license", "metadata", "allowed-tools"}
        names.append(value["name"])
    assert len(names) == len(set(names))


def test_ai_generation_roles_are_present() -> None:
    assert (SKILLS / "ai-visual-producer" / "SKILL.md").exists()
    assert (SKILLS / "h3-video-director" / "SKILL.md").exists()
    assert (SKILLS / "ffmpeg-rough-editor" / "SKILL.md").exists()
    assert not (SKILLS / "h3-prompt-writing" / "SKILL.md").exists()
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "ffmpeg-rough-editor" in agents
    assert "Resolve is optional premium finishing" in agents


def test_skill_registry_covers_unique_project_skills_and_pinned_sources() -> None:
    skills = SOURCES["skills"]
    assert len(skills) == len(set(skills))
    project_entries = {name for name, entry in skills.items() if entry["scope"] == "project"}
    project_dirs = {path.name for path in SKILLS.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()}
    assert project_entries == project_dirs
    for name, entry in skills.items():
        assert entry["path"]
        assert entry["consumers"]
        assert entry["role"]
        assert len(entry["content_sha256"]) == 64
        assert entry["status"] == "keep"
        if entry["source_type"] == "upstream_git":
            assert entry["upstream_repo"].startswith("https://github.com/")
            assert entry["upstream_path"]
            assert len(entry["upstream_commit"]) == 40


def test_skill_doctor_and_list_expose_inventory_health_and_ownership(tmp_path: Path, monkeypatch) -> None:
    registry = copy.deepcopy(SOURCES)
    canonical_root = tmp_path / "canonical" / "skills"
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HAJIMI_SKILLS_ROOT", str(canonical_root))
    monkeypatch.setattr(skill_ops.Path, "home", classmethod(lambda _cls: fake_home))
    lock_path = tmp_path / "skill-lock.json"
    lock_path.write_text(json.dumps({"schema_version": "hajimi-skill-lock-v1", "skills": {}}), encoding="utf-8")
    monkeypatch.setattr(skill_ops, "LOCK_PATH", lock_path)

    for name, metadata in registry["skills"].items():
        if metadata["scope"] != "global":
            continue
        skill_dir = canonical_root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test fixture\n---\n", encoding="utf-8")
        metadata["content_sha256"] = skill_ops.skill_tree_hash(skill_dir)
        for consumer in ("codex", "claude"):
            consumer_root = fake_home / (".codex-shared/skills" if consumer == "codex" else ".claude/skills")
            consumer_root.mkdir(parents=True, exist_ok=True)
            (consumer_root / name).symlink_to(skill_dir, target_is_directory=True)

    monkeypatch.setattr(skill_ops, "_sources", lambda: registry)
    doctor = skills_doctor()
    assert doctor["status"] == "PASS", doctor["errors"]
    assert doctor["missing_skills"] == []
    assert doctor["duplicate_skills"] == []
    assert doctor["broken_links"] == []
    assert doctor["empty_directories"] == []
    assert doctor["routing_status"] == "PASS"
    assert doctor["upstream_status"]["check_command"] == "hajimi skills updates"

    listed = {entry["name"]: entry for entry in skills_list()["skills"]}
    upstream = listed["h3-prompt-writing"]
    assert upstream["scope"] == "global"
    assert upstream["role"]
    assert upstream["status"] == "keep"
    assert upstream["content_sha256"] == registry["skills"]["h3-prompt-writing"]["content_sha256"]
    adapter = listed["ai-visual-producer"]
    assert adapter["source_type"] == "project_adapter"
    assert adapter["scope"] == "project"


def test_production_routes_connect_upstream_knowledge_to_hajimi_adapters() -> None:
    stages = ROUTES["stages"]
    assert stages["script"]["specialist"] == "short-form-video-script"
    assert stages["script"]["adapter"] == "short-script-editor"
    assert stages["script"]["outputs"] == [
        "creative/hook_competition.yaml", "creative/mute_read.yaml", "creative/beat_script.yaml"
    ]
    assert stages["storyboard"]["methods"] == ["short-drama-agent"]
    assert stages["storyboard"]["contract"] == "shot-designer"
    assert stages["image"]["specialist"] == "gpt-image-2-style-library"
    assert stages["image"]["adapter"] == "ai-visual-producer"
    assert stages["image"]["executor"] == "codex_image_gen"
    assert stages["video_prompt"]["specialist"] == "h3-prompt-writing"
    assert stages["video_prompt"]["adapter"] == "h3-video-director"
    assert stages["editing"]["specialist"] == "video-editing"
    assert stages["editing"]["adapter"] == "ffmpeg-rough-editor"
    assert stages["editing"]["executor"] == "studio.roughcut.build_roughcut"


def test_agent_entry_files_point_to_one_router_and_resolve_is_optional() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    gemini = (ROOT / "GEMINI.md").read_text(encoding="utf-8")
    assert "config/skill-routing.yaml" in agents
    assert "AGENTS.md" in claude and "config/skill-routing.yaml" in claude
    assert "AGENTS.md" in gemini and "config/skill-routing.yaml" in gemini
    assert "EP001_earth-stop" not in claude + gemini
    assert "Resolve-exported master is required" not in (ROOT / "studio" / "cli.py").read_text(encoding="utf-8")
