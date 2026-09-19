from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents" / "skills"


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
        names.append(value["name"])
    assert len(names) == len(set(names))


def test_ai_generation_roles_are_present() -> None:
    assert (SKILLS / "ai-visual-producer" / "SKILL.md").exists()
    assert (SKILLS / "h3-video-director" / "SKILL.md").exists()
    assert not (SKILLS / "ffmpeg-rough-editor" / "SKILL.md").exists()
    assert "installed `video-editing` skill" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")
