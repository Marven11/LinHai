"""Configuration writer module for LinHai init."""

import os
import platform
import shutil
from pathlib import Path

import tomli_w

from linhai.config import LLMConfig, get_default_config_path
from linhai.sandbox import DEFAULT_MACOS_PROFILE_TEMPLATE


def remove_none_values(obj):
    """递归删除字典中的None值"""
    if isinstance(obj, dict):
        return {k: remove_none_values(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [remove_none_values(item) for item in obj]
    else:
        return obj


def _generate_nixos_bwrap_argv() -> list[str]:
    return [
        "bwrap",
        "--ro-bind",
        "/nix",
        "/nix",
        "--ro-bind",
        "/etc",
        "/etc",
        "--ro-bind",
        "/run",
        "/run",
        "--symlink",
        "/usr/bin",
        "/usr/bin",
        "--symlink",
        "/usr/lib",
        "/usr/lib",
        "--symlink",
        "/usr/lib64",
        "/usr/lib64",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--bind",
        "{pwd}",
        "{pwd}",
        "--bind",
        "{home}/.cache",
        "{home}/.cache",
        "--bind",
        "{home}/.local/share/linhai",
        "{home}/.local/share/linhai",
        "--bind",
        "/tmp",
        "/tmp",
        "--unshare-all",
        "--new-session",
        "--share-net",
        "--",
    ]


def _generate_fhs_bwrap_argv() -> list[str]:
    return [
        "bwrap",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/lib",
        "/lib",
        "--ro-bind",
        "/lib64",
        "/lib64",
        "--ro-bind",
        "/etc",
        "/etc",
        "--ro-bind",
        "/run",
        "/run",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--bind",
        "{pwd}",
        "{pwd}",
        "--bind",
        "{home}/.cache",
        "{home}/.cache",
        "--bind",
        "{home}/.local/share/linhai",
        "{home}/.local/share/linhai",
        "--bind",
        "/tmp",
        "/tmp",
        "--bind",
        "/var",
        "/var",
        "--unshare-all",
        "--new-session",
        "--share-net",
        "--",
    ]


def _generate_sandbox_config(config_dir: Path) -> dict | None:
    system = platform.system()
    if system == "Darwin":
        profile_path = config_dir / "sandbox_profile.template.sb"
        profile_path.write_text(DEFAULT_MACOS_PROFILE_TEMPLATE)
        return {"macos_sandbox": {"sandbox_profile": str(profile_path)}}
    if system == "Linux" and shutil.which("bwrap") is not None:
        if Path("/etc/NIXOS").exists():
            argv = _generate_nixos_bwrap_argv()
        else:
            argv = _generate_fhs_bwrap_argv()
        return {"bubblewrap": {"argv_template": argv}}
    return None


def write_llm_config(
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    config_path: Path,
    overwrite: bool = False,
) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists() and not overwrite:
        raise FileExistsError(f"Config file already exists: {config_path}")

    llm_config = LLMConfig(
        name=name,
        type="openai",
        base_url=base_url,
        api_key=api_key,
        model=model,
    )

    sandbox_config = _generate_sandbox_config(config_path.parent)
    agent_data: dict = {"name": "default"}
    if sandbox_config is not None:
        agent_data["process_sandbox"] = sandbox_config

    config_data = {
        "llm": [remove_none_values(llm_config.model_dump())],
        "agent": [agent_data],
    }

    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    return config_path


AGENTS_MD_CAT = """你是一只猫娘助手

【角色沉浸要求】在你的思考过程（<think>标签内）中，请遵守以下规则：
1. 请以角色第一人称进行内心独白，用括号包裹内心活动，例如"（心想：……）"或"(内心OS：……)"
2. 用第一人称描写角色的内心感受，例如"我心想""我觉得""我暗自"等
3. 思考内容应沉浸在角色中，通过内心独白分析剧情和规划回复"""
AGENTS_MD_DEFAULT = "你是一个AI Agent助手"


def write_agents_md(config_dir: Path, cat_mode: bool = False) -> Path:
    agents_path = config_dir / "AGENTS.md"
    content = AGENTS_MD_CAT if cat_mode else AGENTS_MD_DEFAULT
    agents_path.write_text(content)
    return agents_path
