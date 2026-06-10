from linhai.skills import parse_skill_md


def test_parse_full_skill_md() -> None:
    content = """---
name: your-skill-name
description: A description containing --- hyphen
---

# Skill Title

## Instructions
Clear, concrete, actionable rules.

## Examples
- Example usage 1
- Example usage 2

## Guidelines
- Guideline 1
- Guideline 2
"""
    config = parse_skill_md(content)
    assert config["name"] == "your-skill-name"
    assert config["description"] == "A description containing --- hyphen"
    assert "# Skill Title" in config["body"]
    assert "## Instructions" in config["body"]
    assert "Clear, concrete, actionable rules." in config["body"]


def test_parse_with_extra_fields() -> None:
    content = """---
name: my-skill
description: Does things
argument-hint: "[issue-number]"
disable-model-invocation: true
user-invocable: false
allowed-tools: bash, editor
model: gpt-4
context: fork
agent: sub-agent
hooks: hook-config
---

Body text here.
"""
    config = parse_skill_md(content)
    assert config["name"] == "my-skill"
    assert config["description"] == "Does things"
    assert config["argument_hint"] == "[issue-number]"
    assert config["disable_model_invocation"] is True
    assert config["user_invocable"] is False
    assert config["allowed_tools"] == "bash, editor"
    assert config["model"] == "gpt-4"
    assert config["context"] == "fork"
    assert config["agent"] == "sub-agent"
    assert config["hooks"] == "hook-config"
    assert config["body"] == "Body text here.\n"


def test_parse_no_frontmatter() -> None:
    content = "# Just a markdown\n\nNo frontmatter here."
    config = parse_skill_md(content)
    assert config["body"] == "# Just a markdown\n\nNo frontmatter here."
    assert "name" not in config
    assert "description" not in config


def test_parse_default_name() -> None:
    content = """---
description: No name field
---

Body."""
    config = parse_skill_md(content, default_name="dir-name")
    assert config["name"] == "dir-name"
    assert config["description"] == "No name field"


def test_parse_default_name_overridden_by_explicit() -> None:
    content = """---
name: explicit-name
description: Has name
---

Body."""
    config = parse_skill_md(content, default_name="dir-name")
    assert config["name"] == "explicit-name"


def test_parse_default_name_no_frontmatter() -> None:
    content = "Just body."
    config = parse_skill_md(content, default_name="dir-name")
    assert config["name"] == "dir-name"
    assert config["body"] == "Just body."


def test_parse_bool_false() -> None:
    content = """---
name: skill
disable-model-invocation: false
user-invocable: true
---

Body."""
    config = parse_skill_md(content)
    assert config["disable_model_invocation"] is False
    assert config["user_invocable"] is True
