from typing import TypedDict, cast, Union
import toml
from pathlib import Path
from urllib.parse import urlparse

from .exceptions import ConfigValidationError


class LLMConfig(TypedDict):
    base_url: str
    api_key: str
    model: str


class MemoryConfig(TypedDict):
    file_path: str


class Config(TypedDict):
    llm: LLMConfig
    memory: MemoryConfig
    compress_threshold: float
    compress_threshold: float


def validate_config(config: Config) -> None:
    """验证配置有效性"""
    llm_config = config["llm"]

    # 验证memory文件路径（可选）
    if "memory" in config:
        memory_config = config["memory"]
        if not memory_config.get("file_path"):
            raise ConfigValidationError("memory.file_path cannot be empty")

    # 验证base_url
    try:
        result = urlparse(llm_config["base_url"])
        if not all([result.scheme, result.netloc]):
            raise ConfigValidationError(
                "base_url must be a valid URL with scheme and netloc"
            )
    except ValueError as e:
        raise ConfigValidationError("base_url is not a valid URL") from e

    # 验证api_key
    if not llm_config["api_key"]:
        raise ConfigValidationError("api_key cannot be empty")

    # 验证model
    if not llm_config["model"]:
        raise ConfigValidationError("model cannot be empty")


def load_config(config_path: Union[str, Path, None] = None) -> Config:
    """从指定路径加载配置并验证
    参数:
        config_path: 配置文件路径，可以是str或Path对象，默认为linhai/config.toml
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.toml"
    elif isinstance(config_path, str):
        config_path = Path(config_path)
    config_data = toml.load(config_path)
    config = cast(Config, config_data)
    validate_config(config)
    return config
