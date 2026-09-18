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


def test_blender_roles_have_one_environment_and_one_production_owner() -> None:
    assert not (SKILLS / "blender-shot").exists()
    assert (SKILLS / "blender-bootstrap" / "SKILL.md").exists()
    assert (SKILLS / "blender-production" / "SKILL.md").exists()
