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
        profile_path = config_dir / "sandbox_profile.sb"
        rendered = DEFAULT_MACOS_PROFILE_TEMPLATE.format(
            pwd=os.getcwd(),
            home=str(Path.home()),
        )
        profile_path.write_text(rendered)
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
