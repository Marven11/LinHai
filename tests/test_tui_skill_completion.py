from __future__ import annotations

from pathlib import Path

from linhai.registry import Registry
from linhai.skills import SkillsManager
from linhai.tui.components import CommandCompletionMenu


def _make_skills_dir(tmp_path: Path, skills: dict[str, str]) -> Path:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    for name, body in skills.items():
        skill_folder = skills_dir / name
        skill_folder.mkdir()
        (skill_folder / "SKILL.md").write_text(body, encoding="utf-8")
    return skills_dir


def test_command_completion_menu_add_candidates():
    registry = Registry()
    menu = CommandCompletionMenu(registry)

    menu.add_candidates(["/help", "/quit", "/exit"])
    assert menu._candidates == ["/help", "/quit", "/exit"]

    menu.add_candidates(["/weather"])
    assert menu._candidates == ["/help", "/quit", "/exit", "/weather"]


def test_command_completion_menu_filter_by_prefix():
    registry = Registry()
    menu = CommandCompletionMenu(registry)
    menu.add_candidates(["/help", "/quit", "/exit", "/weather", "/web_search"])

    matches = [c for c in menu._candidates if c.startswith("/wea")]
    assert matches == ["/weather"]

    matches = [c for c in menu._candidates if c.startswith("/w")]
    assert matches == ["/weather", "/web_search"]

    matches = [c for c in menu._candidates if c.startswith("/q")]
    assert matches == ["/quit"]

    matches = [c for c in menu._candidates if c.startswith("/xyz")]
    assert matches == []


def test_command_completion_menu_exact_match():
    registry = Registry()
    menu = CommandCompletionMenu(registry)
    menu.add_candidates(["/help"])

    matches = [c for c in menu._candidates if c.startswith("/help")]
    assert len(matches) == 1 and matches[0] == "/help"


def test_command_completion_menu_registers_to_registry():
    registry = Registry()
    menu = CommandCompletionMenu(registry)
    menu.on_mount()

    assert registry.has_member("command_completion_menu")
    retrieved = registry.get_member_typechecked(
        "command_completion_menu", CommandCompletionMenu
    )
    assert retrieved is menu


def test_skill_completion_integration(tmp_path: Path):
    skills_dir = _make_skills_dir(
        tmp_path, {"weather": "# Weather Skill\nCheck weather"}
    )
    manager = SkillsManager(skills_dir)
    manager.load()

    registry = Registry()
    menu = CommandCompletionMenu(registry)
    menu.add_candidates(["/help", "/quit", "/exit"])
    menu.add_candidates([f"/{name}" for name in manager.skills])

    matches = [c for c in menu._candidates if c.startswith("/wea")]
    assert matches == ["/weather"]


def test_skill_completion_multiple_skills(tmp_path: Path):
    skills_dir = _make_skills_dir(
        tmp_path,
        {
            "weather": "weather skill",
            "web_search": "web search skill",
            "wiki": "wiki skill",
        },
    )
    manager = SkillsManager(skills_dir)
    manager.load()

    registry = Registry()
    menu = CommandCompletionMenu(registry)
    menu.add_candidates(["/help", "/quit"])
    menu.add_candidates([f"/{name}" for name in manager.skills])

    matches = [c for c in menu._candidates if c.startswith("/w")]
    assert matches == ["/weather", "/web_search", "/wiki"]
