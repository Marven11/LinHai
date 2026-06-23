from __future__ import annotations

from pathlib import Path

from linhai.skills import SkillsManager


def test_skills_manager_no_dir(tmp_path: Path) -> None:
    manager = SkillsManager(skills_dirs=[tmp_path / "nonexistent"])
    manager.load()
    assert manager.skills == {}
    assert manager.get_introduction() is None


def test_skills_manager_empty_dir(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir()
    manager = SkillsManager(skills_dirs=[tmp_path / "skills"])
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
    manager = SkillsManager(skills_dirs=[tmp_path / "skills"])
    manager.load()
    assert "weather" in manager.skills
    assert manager.skills["weather"]["description"] == "Get weather info"
    assert "location" in manager.skills["weather"]
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
    manager = SkillsManager(skills_dirs=[tmp_path / "skills"])
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
    manager = SkillsManager(skills_dirs=[tmp_path / "skills"])
    manager.load()
    assert len(manager.skills) == 2
    intro = manager.get_introduction()
    assert intro is not None
    assert intro.index("alpha") < intro.index("beta")


def test_skills_manager_ignores_files(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "README.md").write_text("not a skill dir", encoding="utf-8")
    manager = SkillsManager(skills_dirs=[skills_dir])
    manager.load()
    assert manager.skills == {}


def test_skills_manager_multi_dir(tmp_path: Path) -> None:
    project_dir = tmp_path / "project" / "skills"
    user_dir = tmp_path / "user" / "skills"
    project_dir.mkdir(parents=True)
    user_dir.mkdir(parents=True)

    for name in ("shared", "project-only"):
        d = project_dir / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: from project\n---\n\nBody.",
            encoding="utf-8",
        )

    for name in ("shared", "user-only"):
        d = user_dir / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: from user\n---\n\nBody.",
            encoding="utf-8",
        )

    manager = SkillsManager(skills_dirs=[project_dir, user_dir])
    manager.load()
    assert len(manager.skills) == 3
    assert manager.skills["shared"]["description"] == "from project"
    assert manager.skills["project-only"]["description"] == "from project"
    assert manager.skills["user-only"]["description"] == "from user"


def test_skills_manager_project_overrides_user(tmp_path: Path) -> None:
    project_dir = tmp_path / "project" / "skills"
    user_dir = tmp_path / "user" / "skills"
    project_dir.mkdir(parents=True)
    user_dir.mkdir(parents=True)

    d = project_dir / "my-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: project version\n---\n\nBody.",
        encoding="utf-8",
    )

    d = user_dir / "my-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: user version\n---\n\nBody.",
        encoding="utf-8",
    )

    manager = SkillsManager(skills_dirs=[project_dir, user_dir])
    manager.load()
    assert len(manager.skills) == 1
    assert manager.skills["my-skill"]["description"] == "project version"


def test_skills_manager_location_field(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "test"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test\ndescription: test\n---\n\nBody.", encoding="utf-8"
    )
    manager = SkillsManager(skills_dirs=[tmp_path / "skills"])
    manager.load()
    expected_path = str((skill_dir / "SKILL.md").absolute())
    assert manager.skills["test"]["location"] == expected_path


def test_skills_manager_filters_disable_model_invocation(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    d = skills_dir / "visible"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: visible\ndescription: shown\n---\n\nBody.", encoding="utf-8"
    )

    d = skills_dir / "hidden"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: hidden\ndescription: not shown\ndisable-model-invocation: true\n---\n\nBody.",
        encoding="utf-8",
    )

    manager = SkillsManager(skills_dirs=[skills_dir])
    manager.load()
    assert len(manager.skills) == 2
    intro = manager.get_introduction()
    assert intro is not None
    assert "visible" in intro
    assert "hidden" not in intro


def test_skills_manager_filters_missing_description(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    d = skills_dir / "with-desc"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: with-desc\ndescription: has desc\n---\n\nBody.",
        encoding="utf-8",
    )

    d = skills_dir / "no-desc"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: no-desc\n---\n\nBody.", encoding="utf-8")

    manager = SkillsManager(skills_dirs=[skills_dir])
    manager.load()
    intro = manager.get_introduction()
    assert intro is not None
    assert "with-desc" in intro
    assert "no-desc" not in intro


def test_skills_manager_all_filtered_returns_none(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    d = skills_dir / "hidden"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: hidden\ndescription: not shown\ndisable-model-invocation: true\n---\n\nBody.",
        encoding="utf-8",
    )

    manager = SkillsManager(skills_dirs=[skills_dir])
    manager.load()
    assert manager.get_introduction() is None


def test_skills_manager_empty_dirs_list(tmp_path: Path) -> None:
    manager = SkillsManager(skills_dirs=[])
    manager.load()
    assert manager.skills == {}
    assert manager.get_introduction() is None


def test_skills_manager_nonexistent_dirs_skipped(tmp_path: Path) -> None:
    manager = SkillsManager(skills_dirs=[tmp_path / "noexist1", tmp_path / "noexist2"])
    manager.load()
    assert manager.skills == {}
