"""Configuration module for LinHai agent."""

from typing import Optional, Union
import tomllib
from pathlib import Path
from pydantic import BaseModel, Field, validator
from urllib.parse import urlparse

from .exceptions import ConfigValidationError


class CheapLLMConfig(BaseModel):
    """Configuration for cheap LLM mode."""

    base_url: str
    api_key: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)


class LLMConfig(BaseModel):
    """LLM配置类型定义。"""

    base_url: str
    api_key: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    cheap: Optional[CheapLLMConfig] = None

    @validator("base_url")
    def validate_base_url(cls, v):
        """验证base_url格式"""
        try:
            result = urlparse(v)
            if not all([result.scheme, result.netloc]):
                raise ValueError("base_url must be a valid URL with scheme and netloc")
        except ValueError as e:
            raise ConfigValidationError("base_url is not a valid URL") from e
        return v


class AgentConfig(BaseModel):
    """Agent配置类型定义。"""

    compress_threshold_soft: float = Field(default=0.5, ge=0.0, le=1.0)
    compress_threshold_hard: float = Field(default=0.8, ge=0.0, le=1.0)
    tool_confirmation: Optional[dict] = None


class MemoryConfig(BaseModel):
    """内存配置类型定义。"""

    file_path: str


class ToolConfig(BaseModel):
    """工具配置类型定义。"""

    max_output_length: int = Field(default=1000, ge=1)


class Config(BaseModel):
    """主配置类型定义。"""

    llm: LLMConfig
    agent: Optional[AgentConfig] = None
    memory: Optional[MemoryConfig] = None
    tools: Optional[ToolConfig] = None


def load_config(config_path: Union[str, Path, None] = None) -> Config:
    """从指定路径加载配置并验证
    参数:
        config_path: 配置文件路径，可以是str或Path对象，默认为linhai/config.toml
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.toml"
    elif isinstance(config_path, str):
        config_path = Path(config_path)
    
    config_data = tomllib.load(config_path.open("rb"))
    
    # 使用pydantic验证配置，捕获ValidationError并转换为ConfigValidationError
    try:
        config = Config(**config_data)
    except Exception as e:
        raise ConfigValidationError(f"配置验证失败: {str(e)}") from e
    return config
