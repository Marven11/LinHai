from __future__ import annotations

from __future__ import annotations

from pathlib import Path

from linhai.skills import SkillsManager


def test_skills_manager_no_dir(tmp_path: Path) -> None:
    manager = SkillsManager(skills_dir=tmp_path / "nonexistent")
    manager.load()
    assert manager.skills == {}
    assert manager.get_introduction() is None


def test_skills_manager_empty_dir(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir()
    manager = SkillsManager(skills_dir=tmp_path / "skills")
    manager.load()
    assert manager.skills == {}
    assert manager.get_introduction() is None


def test_skills_manager_loads_skill(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "weather"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: weather\ndescription: Get weather info\n---\n\n## Instructions\nGet weather.",
        encoding="utf-8",
    )
    manager = SkillsManager(skills_dir=tmp_path / "skills")
    manager.load()
    assert "weather" in manager.skills
    assert manager.skills["weather"]["description"] == "Get weather info"
    intro = manager.get_introduction()
    assert intro is not None
    assert "[weather]" in intro
    assert "Get weather info" in intro


def test_skills_manager_default_name_from_dir(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: A skill\n---\n\nBody.", encoding="utf-8"
    )
    manager = SkillsManager(skills_dir=tmp_path / "skills")
    manager.load()
    assert "my-skill" in manager.skills


def test_skills_manager_multiple_skills(tmp_path: Path) -> None:
    for name in ("alpha", "beta"):
        d = tmp_path / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: desc {name}\n---\n\nBody.",
            encoding="utf-8",
        )
    manager = SkillsManager(skills_dir=tmp_path / "skills")
    manager.load()
    assert len(manager.skills) == 2
    intro = manager.get_introduction()
    assert intro is not None
    assert intro.index("alpha") < intro.index("beta")


def test_skills_manager_ignores_files(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "README.md").write_text("not a skill dir", encoding="utf-8")
    manager = SkillsManager(skills_dir=skills_dir)
    manager.load()
    assert manager.skills == {}
