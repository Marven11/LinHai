"""工具模块主文件。

包含工具消息类和管理器，用于处理工具调用请求和返回结果。
"""

from typing import Awaitable
from collections import Counter
from pathlib import Path

from linhai.llm import Message, ToolCallMessage
from linhai.group_chat import GroupChat
from linhai.tool.base import (
    to_tools_info,
    ToolSet,
    ToolResultMessage,
    ToolErrorMessage,
)
from linhai.tool.mcp_connector import MCPConnector
from linhai.config import ToolConfig, MCPConfig
from linhai.utils import CliRuntimeNotice
import asyncio


class ToolManager:
    """工具管理器，负责处理工具调用请求"""

    def __init__(
        self,
        group_chat: GroupChat,
        toolsets: list[ToolSet],
        config: ToolConfig,
        mcp_config: list[MCPConfig],
        mcp_basedir: Path
    ):
        """初始化工具管理器

        Args:
            config: 可选配置对象
        """
        group_chat.register_member("tool_manager", self)
        self.group_chat = group_chat
        self.config = config
        self.mcp_connector: MCPConnector | None = None
        self.mcp_config = mcp_config
        self.mcp_basedir = mcp_basedir

        names = Counter(
            [name for toolset in toolsets for name in toolset.get_tools().keys()]
        )
        if any(count >= 2 for count in names.values()):
            raise ValueError(
                f"Duplicate names: {[name for name, value in names.items() if value >= 2]}"
            )
        self._toolsets = toolsets

    async def ensure_mcp_connector(self):

        # MCP Connector只能在同一个async Task中关闭
        # 只能在这里连接
        if self.mcp_connector is not None:
            return
        self.mcp_connector = MCPConnector(self.group_chat)
        for mcp_config in self.mcp_config:
            server_script_path = (
                self.mcp_basedir / mcp_config.server_script_path
            )
            await self.mcp_connector.connect_stdio(
                mcp_config.name, server_script_path.absolute().as_posix()
            )

    @property
    def toolsets(self):
        toolsets = self._toolsets.copy()
        if self.mcp_connector:
            toolsets += self.mcp_connector.get_toolsets()
        return toolsets

    def add_toolset(self, toolset: ToolSet):
        existing_names = set(
            name for toolset in self.toolsets for name in toolset.get_tools().keys()
        )
        duplicate_names = [
            name for name in toolset.get_tools().keys() if name in existing_names
        ]
        if duplicate_names:
            raise ValueError(f"Duplicate names: {duplicate_names}")
        self._toolsets.append(toolset)

    def get_tools_info(self) -> list[dict]:
        return [
            info
            for toolset in self.toolsets
            for info in to_tools_info(toolset.get_tools())
        ]

    def get_mcp_connector(self):
        return self.mcp_connector

    async def process_tool_call(self, tool_call: ToolCallMessage) -> Message:
        """处理单个工具调用请求并返回结果

        Args:
            tool_call: 工具调用请求对象，包含函数名和参数

        Returns:
            Message: 工具调用结果消息
        """
        await self.ensure_mcp_connector()

        kwargs = tool_call.function_arguments if tool_call.function_arguments else {}

        target_toolset = None
        for toolset in self.toolsets:
            if toolset.has_tool(tool_call.function_name):
                target_toolset = toolset
        if target_toolset is None:
            # 发送错误消息
            await self.group_chat.send(
                "cli_runtime_output",
                CliRuntimeNotice(
                    level="ERROR", content=f"未找到工具: {tool_call.function_name}"
                ),
            )
            return ToolErrorMessage(f"未找到工具: {tool_call.function_name}")

        try:

            func = target_toolset.get_tool(tool_call.function_name)

            if asyncio.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = await asyncio.to_thread(func, **kwargs)

            # 检查工具返回结果，如果是ToolErrorMessage则发送失败通知
            if isinstance(result, ToolErrorMessage):
                # 发送工具调用失败消息
                await self.group_chat.send(
                    "cli_runtime_output",
                    CliRuntimeNotice(
                        level="ERROR",
                        content=f"工具执行失败: {tool_call.function_name}",
                    ),
                )
            else:
                # 发送工具调用成功消息
                await self.group_chat.send(
                    "cli_runtime_output",
                    CliRuntimeNotice(
                        level="INFO", content=f"工具执行成功: {tool_call.function_name}"
                    ),
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            # 发送工具调用失败消息
            await self.group_chat.send(
                "cli_runtime_output",
                CliRuntimeNotice(
                    level="ERROR",
                    content=f"工具执行失败: {tool_call.function_name} - {str(e)}",
                ),
            )
            return ToolErrorMessage(content=str(e))

        if isinstance(result, Awaitable):
            result = await result

        # 如果工具返回的是 Message 实例，直接返回
        if isinstance(result, Message):
            return result

        # 否则，用 ToolResultMessage 包装，使用配置的max_output_length或默认值
        if self.config and self.config.max_output_length is not None:
            max_output_length = self.config.max_output_length
        else:
            await self.group_chat.send(
                "cli_runtime_output",
                CliRuntimeNotice(level="INFO", content="使用默认输出长度限制: 50000"),
            )
            max_output_length = 50000

        return ToolResultMessage(content=result, max_output_length=max_output_length)
