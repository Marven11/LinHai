from __future__ import annotations

import re

import yaml
from typing_extensions import NotRequired, TypedDict


class SkillConfig(TypedDict):
    name: NotRequired[str]
    description: NotRequired[str]
    argument_hint: NotRequired[str]
    disable_model_invocation: NotRequired[bool]
    user_invocable: NotRequired[bool]
    allowed_tools: NotRequired[str]
    model: NotRequired[str]
    context: NotRequired[str]
    agent: NotRequired[str]
    hooks: NotRequired[str]
    body: str


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)

_KEY_MAP = {
    "name": "name",
    "description": "description",
    "argument-hint": "argument_hint",
    "disable-model-invocation": "disable_model_invocation",
    "user-invocable": "user_invocable",
    "allowed-tools": "allowed_tools",
    "model": "model",
    "context": "context",
    "agent": "agent",
    "hooks": "hooks",
}


def parse_skill_md(content: str, default_name: str | None = None) -> SkillConfig:
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        if default_name is not None:
            return {"body": content, "name": default_name}
        return {"body": content}

    raw = yaml.safe_load(match.group(1))
    body = match.group(2)

    if not isinstance(raw, dict):
        if default_name is not None:
            return {"body": body, "name": default_name}
        return {"body": body}

    config: SkillConfig = {"body": body}
    for yaml_key, field_name in _KEY_MAP.items():
        if yaml_key in raw:
            config[field_name] = raw[yaml_key]
    if default_name is not None and "name" not in config:
        config["name"] = default_name
    return config


from pathlib import Path


class SkillsManager:
    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = skills_dir
        self._skills: dict[str, SkillConfig] = {}

    def load(self) -> None:
        if not self._skills_dir.is_dir():
            return
        for child in sorted(self._skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.is_file():
                content = skill_md.read_text(encoding="utf-8")
                config = parse_skill_md(content, default_name=child.name)
                name = config.get("name", child.name)
                self._skills[name] = config

    @property
    def skills(self) -> dict[str, SkillConfig]:
        return self._skills

    def get_introduction(self) -> str | None:
        if not self._skills:
            return None
        lines = [
            "Skills是用户自定义的skill文件。"
            "用户可以使用`/<skill_name> <args>`来触发skill。"
            "触发skill时，将`/<skill_name> <args>`消息本身和对应的SKILL.md"
            "加入消息列表，打断agent。\n\n## 可用Skills:\n"
        ]
        for name, config in sorted(self._skills.items()):
            desc = config.get("description", "")
            skill_path = str(self._skills_dir / name / "SKILL.md")
            lines.append(f"[{name}]({skill_path}): {desc}")
        return "\n".join(lines)
