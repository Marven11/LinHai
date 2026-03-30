"""Configuration module for LinHai agent."""

import os
import re
from pathlib import Path
from typing import Optional, Union, Literal
from urllib.parse import urlparse

import tomllib
from pydantic import BaseModel, Field, field_validator

from .exceptions import ConfigValidationError


def get_default_config_path() -> Path:
    """获取默认配置文件路径。"""
    return Path.home() / ".config" / "linhai" / "config.toml"


class ExplicitCacheConfig(BaseModel):
    """显式缓存配置类型定义。"""

    enable: bool = Field(description="是否启用显式缓存")
    cache_write_price_ratio: float = Field(
        default=1.25, description="缓存写入价格相对于默认价格的比例"
    )
    cache_hit_price_ratio: float = Field(
        default=0.1, description="缓存命中价格相对于默认价格的比例"
    )


class LLMConfig(BaseModel):
    """单个LLM配置类型定义。"""

    name: str = Field(..., min_length=1, description="LLM实例的唯一标识名称")
    type: str = Field(default="openai", description="LLM服务提供商类型")
    compatibility: str = Field(
        default="", description="兼容性标识，用于指定兼容的模型变体"
    )
    support_image: bool = Field(default=False, description="是否支持图像输入")
    explicit_cache: Optional[ExplicitCacheConfig] = Field(
        default=None, description="显式缓存配置"
    )
    base_url: str = Field(..., description="API服务的基地址")
    api_key: str = Field(..., min_length=1, description="API认证密钥")
    model: str = Field(..., min_length=1, description="使用的模型名称")
    client_options: dict = Field(default_factory=dict, description="客户端额外配置选项")
    completion_options: dict = Field(
        default_factory=dict, description="完成请求的额外配置选项"
    )
    token_limit: int = Field(
        default=0, description="上下文窗口的token限制，0表示使用默认值"
    )
    fallback: Optional[str] = Field(
        default=None, description="回退LLM的名称，当主LLM不可用时使用"
    )

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

    name: str = Field(..., min_length=1, description="MCP服务器的唯一标识名称")
    server_script_path: str = Field(..., description="MCP服务器脚本的路径")

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

    compress_threshold: Union[int, float] = Field(
        default=0.8, ge=0.0, description="上下文压缩阈值。"
    )
    mcp: list[MCPConfig] = Field(
        default_factory=list, description="MCP服务器配置列表。"
    )
    enable_directory_change_detection: bool = Field(
        default=False, description="是否启用目录变化检测。"
    )
    enable_task_planning: bool = Field(default=False, description="是否启用任务规划。")
    allowed_commands: list[list[str]] = Field(
        default_factory=list, description="允许执行的命令列表。"
    )
    max_toolcall_for_llm: dict[str, int] = Field(
        default_factory=dict, description="每个LLM的最大工具调用次数限制。"
    )
    override_toolsets: Optional[list[str]] = Field(
        default=None, description="覆盖tools.toolsets的设置。"
    )
    default_llm: Optional[str] = Field(
        default=None, description="默认使用的LLM名称，优先级高于命令行参数。"
    )

    @field_validator("compress_threshold")
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
        return f"AgentConfig(compress_threshold={self.compress_threshold}, mcp={mcp_names})"


class UserPromptConfig(BaseModel):
    """内存配置类型定义。"""

    file_path: str = Field(description="用户提示文件路径。")

    def __str__(self) -> str:
        """返回内存配置的字符串表示"""
        return f"UserPromptConfig(file_path={self.file_path})"


class SecretSubConfig(BaseModel):
    """Secret子配置类型定义。"""

    config_path: str = Field(default="", description="Secret配置文件路径。")

    def __str__(self) -> str:
        """返回Secret子配置的字符串表示"""
        return f"SecretSubConfig(config_path={self.config_path})"


class TelegramConfig(BaseModel):
    """Telegram bot配置类型定义。"""

    bot_token: str = Field(..., min_length=1, description="Telegram bot的认证令牌")
    default_chat_id: str = Field(..., min_length=1, description="默认的聊天ID")

    def __str__(self) -> str:
        """返回Telegram配置的字符串表示"""
        return f"TelegramConfig(bot_token=***, default_chat_id={self.default_chat_id})"


class RemoteControlConfig(BaseModel):
    """远程控制配置类型定义。"""

    telegram: Optional[TelegramConfig] = Field(
        default=None, description="Telegram远程控制配置"
    )

    def __str__(self) -> str:
        """返回远程控制配置的字符串表示"""
        return f"RemoteControlConfig(telegram={self.telegram})"


AVAILABLE_TOOLSETS = frozenset(
    ["utils", "sleep", "machine_control", "multimodal", "llm", "context_cleaning"]
)


class ToolConfig(BaseModel):
    """工具配置类型定义。"""

    secret: SecretSubConfig = Field(
        default_factory=SecretSubConfig, description="Secret子配置"
    )
    max_toolcall_token_in_round: Union[int, float] = Field(
        default=0.3,
        description="单轮工具调用中允许的最大token数。int为静态限制，float为相对于token_limit的比例",
    )
    toolsets: Union[Literal["defaults"], list[str]] = Field(default="defaults")

    @field_validator("max_toolcall_token_in_round")
    def validate_max_toolcall_token_in_round(cls, v):
        """验证max_toolcall_token_in_round值：如果是float，应在0.0到1.0之间；如果是int，应大于0。"""
        if isinstance(v, float):
            if not 0.0 < v <= 1.0:
                raise ValueError(
                    "如果为float类型，max_toolcall_token_in_round应在0.0到1.0之间"
                )
        elif isinstance(v, int):
            if v <= 0:
                raise ValueError("如果为int类型，max_toolcall_token_in_round应大于0")
        else:
            raise TypeError("max_toolcall_token_in_round必须是int或float类型")
        return v

    @field_validator("toolsets")
    def validate_toolsets(cls, v):
        """验证toolsets配置：如果是列表，检查是否包含有效名称"""
        if isinstance(v, list):
            invalid_toolsets = [t for t in v if t not in AVAILABLE_TOOLSETS]
            if invalid_toolsets:
                raise ConfigValidationError(
                    f"Invalid toolsets: {invalid_toolsets}. Available: {list(AVAILABLE_TOOLSETS)}"
                )
        return v

    def __str__(self) -> str:
        """返回工具配置的字符串表示"""
        return f"ToolConfig(max_toolcall_token_in_round={self.max_toolcall_token_in_round}, toolsets={self.toolsets}, secret={self.secret})"


class CLIConfig(BaseModel):
    """CLI配置类型定义。"""

    use_nerd_font: bool = Field(default=False, description="是否使用Nerd Font图标")
    theme: str = Field(default="nord", description="CLI主题名称")

    def __str__(self) -> str:
        """返回CLI配置的字符串表示"""
        return f"CLIConfig(use_nerd_font={self.use_nerd_font}, theme={self.theme})"


class Config(BaseModel):
    """主配置类型定义。"""

    llm: list[LLMConfig] = Field(description="LLM配置列表")
    agent: AgentConfig = Field(default_factory=AgentConfig, description="Agent行为配置")
    user_prompt: UserPromptConfig = Field(
        default_factory=lambda: UserPromptConfig(file_path=""),
        description="用户提示配置",
    )
    tools: ToolConfig = Field(default_factory=ToolConfig, description="工具相关配置")
    cli: CLIConfig = Field(default_factory=CLIConfig, description="CLI界面配置")
    remote_control: RemoteControlConfig = Field(
        default_factory=RemoteControlConfig, description="远程控制配置"
    )

    def __str__(self) -> str:
        """返回主配置的字符串表示"""
        llm_names = [llm.name for llm in self.llm]
        return f"Config(llms={llm_names}, agent={self.agent}, user_prompt={self.user_prompt}, tools={self.tools})"


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
    for mcp_config in config.agent.mcp:  # type: ignore  # pylint: disable=no-member
        if not os.path.isabs(mcp_config.server_script_path):
            mcp_config.server_script_path = str(
                config_dir / mcp_config.server_script_path
            )

    return config
