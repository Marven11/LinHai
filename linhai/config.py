"""Configuration module for LinHai agent."""

import os
import re
from typing import Optional, Union
import tomllib
from pathlib import Path
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator

from .exceptions import ConfigValidationError


class LLMConfig(BaseModel):
    """单个LLM配置类型定义。"""

    name: str = Field(..., min_length=1)
    type: str = Field(default="openai")
    compatibility: Optional[str] = Field(default=None)
    base_url: str
    api_key: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    client_options: dict = Field(default_factory=dict)
    completion_options: dict = Field(default_factory=dict)
    token_limit: Optional[int] = Field(default=None)

    @field_validator("name")
    def validate_name(cls, v):  # pylint: disable=no-self-argument
        """验证name格式：只允许[a-zA-Z0-9-_]字符"""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ConfigValidationError(
                "LLM name can only contain letters, numbers, hyphens, and underscores"
            )
        return v

    @field_validator("base_url")
    def validate_base_url(cls, v):  # pylint: disable=no-self-argument
        """验证base_url格式"""
        try:
            result = urlparse(v)
            if not all([result.scheme, result.netloc]):
                raise ValueError("base_url must be a valid URL with scheme and netloc")
        except ValueError as e:
            raise ConfigValidationError("base_url is not a valid URL") from e
        return v

    def __str__(self) -> str:
        """返回LLM配置的字符串表示"""
        return f"LLMConfig(name={self.name}, model={self.model})"


class MCPConfig(BaseModel):
    """MCP服务器配置类型定义。"""

    name: str = Field(..., min_length=1)
    server_script_path: str

    @field_validator("name")
    def validate_name(cls, v):  # pylint: disable=no-self-argument
        """验证name格式：只允许[a-zA-Z0-9-_]字符"""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ConfigValidationError(
                "MCP server name can only contain letters, numbers, hyphens, and underscores"
            )
        return v

    def __str__(self) -> str:
        """返回MCP配置的字符串表示"""
        return (
            f"MCPConfig(name={self.name}, server_script_path={self.server_script_path})"
        )


class AgentConfig(BaseModel):
    """Agent配置类型定义。"""

    compress_threshold_soft: Union[int, float] = Field(default=0.5, ge=0.0)
    compress_threshold_hard: Union[int, float] = Field(default=0.8, ge=0.0)
    mcp: list[MCPConfig] = Field(default_factory=list)
    enable_directory_change_detection: bool = Field(default=False)

    @field_validator("compress_threshold_soft", "compress_threshold_hard")
    def validate_compress_threshold(cls, v):  # pylint: disable=no-self-argument
        """验证compress_threshold值：如果是float，应在0.0到1.0之间；如果是int，应大于0。"""
        if isinstance(v, float):
            if not 0.0 <= v <= 1.0:
                raise ValueError("如果为float类型，compress_threshold应在0.0到1.0之间")
        elif isinstance(v, int):
            if v <= 0:
                raise ValueError("如果为int类型，compress_threshold应大于0")
        else:
            raise TypeError("compress_threshold必须是int或float类型")
        return v

    def __str__(self) -> str:
        """返回Agent配置的字符串表示"""
        mcp_names = [mcp.name for mcp in self.mcp]
        return f"AgentConfig(soft_threshold={self.compress_threshold_soft}, hard_threshold={self.compress_threshold_hard}, mcp={mcp_names})"


class MemoryConfig(BaseModel):
    """内存配置类型定义。"""

    file_path: str

    def __str__(self) -> str:
        """返回内存配置的字符串表示"""
        return f"MemoryConfig(file_path={self.file_path})"


class ToolConfig(BaseModel):
    """工具配置类型定义。"""

    max_output_length: int = Field(default=50000, ge=1)

    def __str__(self) -> str:
        """返回工具配置的字符串表示"""
        return f"ToolConfig(max_output_length={self.max_output_length})"


class CLIConfig(BaseModel):
    """CLI配置类型定义。"""

    use_nerd_font: bool = Field(default=False)

    def __str__(self) -> str:
        """返回CLI配置的字符串表示"""
        return f"CLIConfig(use_nerd_font={self.use_nerd_font})"


class SubAgentConfig(BaseModel):
    """SubAgent配置类型定义。"""

    enable: bool = Field(default=True)
    default_llm: str = Field(default="deepseek", min_length=1)

    def __str__(self) -> str:
        """返回SubAgent配置的字符串表示"""
        return f"SubAgentConfig(enable={self.enable}, default_llm={self.default_llm})"


class Config(BaseModel):
    """主配置类型定义。"""

    llm: list[LLMConfig]
    agent: Optional[AgentConfig] = None
    memory: Optional[MemoryConfig] = None
    tools: Optional[ToolConfig] = None
    subagent: Optional[SubAgentConfig] = None
    cli: CLIConfig = Field(default_factory=CLIConfig)

    @property
    def subagent_enabled(self) -> bool:
        """检查SubAgent是否启用"""
        return self.subagent is not None and self.subagent.enable

    def __str__(self) -> str:
        """返回主配置的字符串表示"""
        llm_names = [llm.name for llm in self.llm]
        subagent_enabled = self.subagent_enabled
        return f"Config(llms={llm_names}, agent={self.agent is not None}, memory={self.memory is not None}, tools={self.tools is not None}, subagent_enabled={subagent_enabled})"


def load_config(config_path: Union[str, Path]) -> Config:
    """从指定路径加载配置并验证
    参数:
        config_path: 配置文件路径，必须是str或Path对象
    """
    if isinstance(config_path, str):
        config_path = Path(config_path)

    with config_path.open("rb") as f:
        config_data = tomllib.load(f)

    config = Config(**config_data)

    config_dir = config_path.parent
    if config.agent and config.agent.mcp:
        for mcp_config in config.agent.mcp:
            if not os.path.isabs(mcp_config.server_script_path):
                mcp_config.server_script_path = str(
                    config_dir / mcp_config.server_script_path
                )

    return config
