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
