from typing import TypedDict, cast
import toml
from pathlib import Path
import re
from urllib.parse import urlparse

class LLMConfig(TypedDict):
    base_url: str
    api_key: str
    model: str

class Config(TypedDict):
    llm: LLMConfig

class ConfigValidationError(Exception):
    """配置验证失败异常"""
    pass

def validate_config(config: Config) -> None:
    """验证配置有效性"""
    llm_config = config["llm"]
    
    # 验证base_url
    try:
        result = urlparse(llm_config["base_url"])
        if not all([result.scheme, result.netloc]):
            raise ConfigValidationError("base_url must be a valid URL with scheme and netloc")
    except ValueError:
        raise ConfigValidationError("base_url is not a valid URL")
        
    # 验证api_key
    if not llm_config["api_key"]:
        raise ConfigValidationError("api_key cannot be empty")
        
    # 验证model
    if not llm_config["model"]:
        raise ConfigValidationError("model cannot be empty")

def load_config() -> Config:
    """从config.toml加载配置并验证"""
    config_path = Path(__file__).parent / "config.toml"
    config_data = toml.load(config_path)
    config = cast(Config, config_data)
    validate_config(config)
    return config
