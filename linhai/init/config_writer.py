"""Configuration writer module for LinHai init."""

from pathlib import Path

import tomli_w

from linhai.config import LLMConfig, get_default_config_path


def remove_none_values(obj):
    """递归删除字典中的None值"""
    if isinstance(obj, dict):
        return {k: remove_none_values(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [remove_none_values(item) for item in obj]
    else:
        return obj


def write_llm_config(
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    config_path: Path,
    overwrite: bool = False,
) -> Path:
    """Write LLM configuration to the config file.

    Args:
        name: LLM name
        base_url: API base URL
        api_key: API key
        model: Model name
        config_path: Path to config file
        overwrite: Whether to overwrite existing config

    Returns:
        Path to the written config file

    Raises:
        FileExistsError: If config file exists and overwrite is False
    """
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

    config_data = {
        "llm": [remove_none_values(llm_config.model_dump())],
    }

    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    return config_path
