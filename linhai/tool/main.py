"""工具模块主文件。

包含工具消息类和管理器，用于处理工具调用请求和返回结果。
"""

import asyncio
import inspect
import json
import jsonschema
from pathlib import Path
from typing import Any, Awaitable, Optional

from linhai.config import ToolConfig, MCPConfig
from linhai.registry import Registry
from linhai.base import Message, ToolCallMessage
from linhai.tool.base import (
    ToolSet,
    to_tools_info,
    ToolCallResultMessage,
    SuccessfulToolResult,
    FailedToolResult,
    ToolResult,
    FileContentToolResult,
    Tool,
)
from linhai.tool.mcp_connector import MCPConnector
from linhai.utils.common import UiNotice


class ToolManager:
    """工具管理器，负责处理工具调用请求"""

    def __init__(
        self,
        registry: Registry,
        config: ToolConfig,
        mcp_connector: MCPConnector,
    ):
        """初始化工具管理器

        Args:
            config: 可选配置对象
            mcp_connector: 已初始化的MCPConnector实例
        """
        registry.register_member("tool_manager", self)
        self.registry = registry
        self.config = config
        self.mcp_connector = mcp_connector
        self._toolsets: dict[str, ToolSet] = {}
        self._enabled: dict[str, bool] = {}

    def register_toolset(
        self, name: str, toolset: ToolSet, enabled: bool = True
    ) -> None:
        existing_names = set(
            name for ts in self._toolsets.values() for name in ts.get_tools().keys()
        )
        duplicate_names = [
            name for name in toolset.get_tools().keys() if name in existing_names
        ]
        if duplicate_names:
            raise ValueError(f"Duplicate names: {duplicate_names}")
        self._toolsets[name] = toolset
        self._enabled[name] = enabled

    def set_toolset_enabled(self, name: str, enabled: bool) -> None:
        if name not in self._toolsets:
            raise ValueError(f"Toolset '{name}' not registered")
        self._enabled[name] = enabled

    def apply_toolset_config(self, enabled_names: list[str]) -> None:
        for name in self._toolsets:
            if name not in enabled_names:
                self._enabled[name] = False

    @property
    def toolsets(self) -> list[ToolSet]:
        toolsets = [
            ts for name, ts in self._toolsets.items() if self._enabled.get(name, True)
        ]
        if self.mcp_connector:
            toolsets += self.mcp_connector.get_toolsets()
        return toolsets

    def get_tools_info(self) -> list[dict]:
        return [
            info
            for toolset in self.toolsets
            for info in to_tools_info(toolset.get_tools())
        ]

    def _validate_tool_arguments(
        self, tool_def: Tool, kwargs: dict[str, Any]
    ) -> list[str]:
        properties = {
            arg_name: arg_info["schema"]
            for arg_name, arg_info in tool_def["args"].items()
        }
        schema = {
            "type": "object",
            "properties": properties,
            "required": tool_def["required"],
        }
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(kwargs), key=lambda e: e.path)
        return [
            f"{'.'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors
        ]

    async def process_tool_call(
        self, tool_call: ToolCallMessage, tool_index: int
    ) -> Message:
        """处理单个工具调用请求并返回结果

        Args:
            tool_call: 工具调用请求对象，包含函数名和参数

        Returns:
            Message: 工具调用结果消息
        """
        kwargs = tool_call.function_arguments

        target_toolset = None
        for toolset in self.toolsets:
            if toolset.has_tool(tool_call.function_name):
                target_toolset = toolset
        if target_toolset is None:
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="ERROR", content=f"未找到工具: {tool_call.function_name}"
                ),
            )
            failed_result = FailedToolResult(
                content=f"未找到工具: {tool_call.function_name}"
            )
            return ToolCallResultMessage(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                result=failed_result,
                toolcall_arguments=kwargs,
            )

        try:

            func = target_toolset.get_tool(tool_call.function_name)

            tool_def = target_toolset.get_tools()[tool_call.function_name]
            validation_errors = self._validate_tool_arguments(tool_def, kwargs)
            if validation_errors:
                error_msg = "参数验证失败: " + "; ".join(validation_errors)
                await self.registry.send_if_exists(
                    "ui_log",
                    UiNotice(
                        level="ERROR",
                        content=f"工具参数验证失败: {tool_call.function_name} - {error_msg}",
                    ),
                )
                return ToolCallResultMessage(
                    tool_name=tool_call.function_name,
                    tool_index=tool_index,
                    result=FailedToolResult(content=error_msg),
                    toolcall_arguments=kwargs,
                )

            if inspect.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = await asyncio.to_thread(func, **kwargs)

            if isinstance(result, FailedToolResult):
                await self.registry.send_if_exists(
                    "ui_log",
                    UiNotice(
                        level="ERROR",
                        content=f"工具执行失败: {tool_call.function_name}",
                    ),
                )

            if isinstance(result, Awaitable):
                result = await result

            if isinstance(result, ToolResult):
                tool_result = result
            else:
                tool_result = SuccessfulToolResult(content=str(result))

            return ToolCallResultMessage(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                result=tool_result,
                toolcall_arguments={},
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = str(e)

            failed_result = ToolCallResultMessage(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                result=FailedToolResult(content=error_msg),
                toolcall_arguments={},
            )

            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="ERROR",
                    content=f"工具执行失败: {tool_call.function_name} - {error_msg}",
                ),
            )

            return failed_result

    def register_lifecycle(self):

        from linhai.agent.lifecycle import Lifecycle

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        lifecycle.before_message_generation.register(self.update_tools_definition)
        lifecycle.after_conversation_restore.register(self.update_tools_definition)

    async def update_tools_definition(self):
        """更新SystemMessage中的工具定义（before_message_generation回调）。"""
        from linhai.base import SystemMessage
        from linhai.agent.main import Agent

        system_message = self.registry.get_member_typechecked(
            "system_message", SystemMessage
        )

        system_message.remove_introduction("TOOLS")

        agent = self.registry.get_member_typechecked("agent", Agent)
        if agent.get_current_model().get_native_toolcall_format():
            return

        tools_info = self.get_tools_info()
        system_message.add_introduction(
            "TOOLS", json.dumps(tools_info, ensure_ascii=False)
        )
