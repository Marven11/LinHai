"""工具模块主文件。

包含工具消息类和管理器，用于处理工具调用请求和返回结果。
"""

from typing import Any, Callable, Awaitable, Coroutine, Optional
from collections import Counter

from linhai.llm import Message, ToolCallMessage, RuntimeMessage
from linhai.group_chat import GroupChat
from linhai.tool.base import (
    Tool,
    to_tools_info,
    ToolSet,
    ToolResultMessage,
    ToolErrorMessage,
)
from linhai.tool.mcp_connector import MCPConnector
from linhai.config import Config
import asyncio


class ToolManager:
    """工具管理器，负责处理工具调用请求"""

    def __init__(
        self,
        group_chat: GroupChat,
        toolsets: list[ToolSet],
        config: Optional[Config] = None,
        mcp_connector: Optional[MCPConnector] = None
    ):
        """初始化工具管理器

        Args:
            config: 可选配置对象
        """
        group_chat.register_member("tool_manager", self)
        self.group_chat = group_chat
        self.workflows: dict[str, Tool] = {}
        self.config = config
        self.mcp_connector = mcp_connector

        names = Counter(
            [name for toolset in toolsets for name in toolset.get_tools().keys()]
        )
        if any(count >= 2 for count in names.values()):
            raise ValueError(
                f"Duplicate names: {[name for name, value in names.items() if value >= 2]}"
            )
        self._toolsets = toolsets

    @property
    def toolsets(self):
        toolsets = self._toolsets 
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

    def register_workflow(
        self, name: str, desc: str, func: Callable[[Any], Coroutine[None, None, bool]]
    ):
        self.workflows[name] = Tool(
            name=name, desc=desc, args={}, required=[], func=func
        )

    def get_workflow(self, name: str):
        return self.workflows.get(name)

    def get_tools_info(self) -> list[dict]:
        return [
            info
            for toolset in self.toolsets
            for info in to_tools_info(toolset.get_tools())
        ] + to_tools_info(self.workflows)

    def get_mcp_connector(self):
        return self.mcp_connector

    async def process_tool_call(self, tool_call: ToolCallMessage) -> Message:
        """处理单个工具调用请求并返回结果

        Args:
            tool_call: 工具调用请求对象，包含函数名和参数

        Returns:
            Message: 工具调用结果消息
        """
        kwargs = tool_call.function_arguments if tool_call.function_arguments else {}

        target_toolset = None
        for toolset in self.toolsets:
            if toolset.has_tool(tool_call.function_name):
                target_toolset = toolset
        if target_toolset is None:
            # 发送错误消息
            await self.group_chat.send("cli_runtime_output", RuntimeMessage(
                level="ERROR", 
                content=f"未找到工具: {tool_call.function_name}"
            ))
            return ToolErrorMessage(f"未找到工具: {tool_call.function_name}")

        try:
            # 发送工具调用开始消息
            await self.group_chat.send("cli_runtime_output", RuntimeMessage(
                level="INFO", 
                content=f"开始执行工具: {tool_call.function_name}"
            ))

            func = target_toolset.get_tool(tool_call.function_name)

            if asyncio.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = await asyncio.to_thread(
                    func, **kwargs
                )

            # 发送工具调用成功消息
            await self.group_chat.send("cli_runtime_output", RuntimeMessage(
                level="INFO", 
                content=f"工具执行成功: {tool_call.function_name}"
            ))

        except Exception as e:  # pylint: disable=broad-exception-caught
            # 发送工具调用失败消息
            await self.group_chat.send("cli_runtime_output", RuntimeMessage(
                level="ERROR", 
                content=f"工具执行失败: {tool_call.function_name} - {str(e)}"
            ))
            return ToolErrorMessage(content=str(e))

        if isinstance(result, Awaitable):
            result = await result

        # 如果工具返回的是 Message 实例，直接返回
        if isinstance(result, Message):
            return result

        # 否则，用 ToolResultMessage 包装，使用配置的max_output_length或默认值
        max_output_length = 50000
        if (
            self.config
            and self.config.tools
            and self.config.tools.max_output_length is not None
        ):
            max_output_length = self.config.tools.max_output_length

        return ToolResultMessage(content=result, max_output_length=max_output_length)
