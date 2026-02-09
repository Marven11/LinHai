"""工具模块主文件。

包含工具消息类和管理器，用于处理工具调用请求和返回结果。
"""

import asyncio
import inspect
import json
from collections import Counter
from pathlib import Path
from typing import Awaitable

from linhai.config import ToolConfig, MCPConfig
from linhai.group_chat import GroupChat
from linhai.llm import Message, ToolCallMessage
from linhai.tool.base import (
    ToolSet,
    to_tools_info,
    ToolCallResultMessage,
    ToolResultSuccess,
    ToolResultFailed,
)
from linhai.tool.mcp_connector import MCPConnector
from linhai.utils import CliRuntimeNotice





class ToolManager:
    """工具管理器，负责处理工具调用请求"""

    def __init__(
        self,
        group_chat: GroupChat,
        toolsets: list[ToolSet],
        config: ToolConfig,
        mcp_config: list[MCPConfig],
        mcp_basedir: Path,
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
        group_chat.add_postinit(self.postinit)

    def postinit(self):
        """后初始化：注册MachineControl工具集"""
        from linhai.machine_control.main import register_machine_control_tools
        from linhai.machine_control import MachineControl

        machine_control = self.group_chat.get_members("machine_control", MachineControl)
        self.add_toolset(register_machine_control_tools(machine_control))

    async def ensure_mcp_connector(self):
        if self.mcp_connector is not None:
            return
        self.mcp_connector = MCPConnector(self.group_chat)
        for mcp_config in self.mcp_config:
            server_script_path = self.mcp_basedir / mcp_config.server_script_path
            from contextlib import AsyncExitStack

            exit_stack = AsyncExitStack()
            await self.mcp_connector.connect_mcp_server(
                mcp_config.name, server_script_path.absolute().as_posix(), exit_stack
            )

    @property
    def toolsets(self) -> list[ToolSet]:
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

    async def process_tool_call(
        self, tool_call: ToolCallMessage, tool_index: int
    ) -> Message:
        """处理单个工具调用请求并返回结果

        Args:
            tool_call: 工具调用请求对象，包含函数名和参数

        Returns:
            Message: 工具调用结果消息
        """
        await self.ensure_mcp_connector()

        kwargs = tool_call.function_arguments

        # 处理on_machine参数
        original_machine = None
        machine_control = None
        if tool_call.on_machine is not None:
            from linhai.machine_control.main import MachineControl

            # machine_control应该总是存在，因为ToolManager.postinit会注册它
            # 如果不存在，说明系统初始化有问题，应该抛出异常
            machine_control = self.group_chat.get_members(
                "machine_control", MachineControl
            )
            if tool_call.on_machine not in machine_control.machines:
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="ERROR", content=f"机器未找到: {tool_call.on_machine}"
                    ),
                )
                failed_result = ToolResultFailed(
                    content=f"机器未找到: {tool_call.on_machine}"
                )
                return ToolCallResultMessage(
                    tool_name=tool_call.function_name,
                    tool_index=tool_index,
                    result=failed_result,
                    toolcall_arguments=kwargs,
                )
            original_machine = machine_control.target_machine
            machine_control.target_machine = tool_call.on_machine

        target_toolset = None
        for toolset in self.toolsets:
            if toolset.has_tool(tool_call.function_name):
                target_toolset = toolset
        if target_toolset is None:
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR", content=f"未找到工具: {tool_call.function_name}"
                ),
            )
            failed_result = ToolResultFailed(
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

            if inspect.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = await asyncio.to_thread(func, **kwargs)

            if isinstance(result, ToolResultFailed):
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="ERROR",
                        content=f"工具执行失败: {tool_call.function_name}",
                    ),
                )

            if isinstance(result, Awaitable):
                result = await result
            
            from ..multimodal import ImageMessage
            if isinstance(result, ImageMessage):
                return result
            
            if isinstance(result, Message):
                llm_msg = result.to_llm_message()
                content = llm_msg.get("content", "")
                assert isinstance(content, str), "Possible unfiltered complex content: " + repr(content)
                processed_content = content
                result_type = (
                    ToolResultFailed
                    if isinstance(result, ToolResultFailed)
                    else ToolResultSuccess
                )
                return ToolCallResultMessage(
                    tool_name=tool_call.function_name,
                    tool_index=tool_index,
                    result=result_type(content=processed_content),
                    toolcall_arguments=kwargs if isinstance(result, ToolResultFailed) else {},
                )

            if isinstance(result, ToolResultSuccess) or isinstance(
                result, ToolResultFailed
            ):
                tool_result = result
            else:
                tool_result = ToolResultSuccess(content=str(result))

            processed_content = tool_result.content
            if isinstance(tool_result, ToolResultFailed):
                tool_result = ToolResultFailed(content=processed_content)
            else:
                tool_result = ToolResultSuccess(content=processed_content)

            return ToolCallResultMessage(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                result=tool_result,
                toolcall_arguments={},
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR",
                    content=f"工具执行失败: {tool_call.function_name} - {str(e)}",
                ),
            )
            failed_result = ToolResultFailed(content=str(e))
            return ToolCallResultMessage(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                result=failed_result,
                toolcall_arguments=kwargs,
            )
        finally:
            # 恢复原始机器
            if machine_control is not None and original_machine is not None:
                machine_control.target_machine = original_machine

    def register_lifecycle(self):

        from linhai.agent.lifecycle import Lifecycle

        lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
        lifecycle.register_before_message_generation(self.update_tools_definition)

    async def update_tools_definition(
        self, _enable_compress: bool, _disable_waiting_user_warning: bool
    ):
        """更新SystemMessage中的工具定义（before_message_generation回调）。"""
        from linhai.llm import SystemMessage

        system_message = self.group_chat.get_members("system_message", SystemMessage)

        system_message.remove_introduction("TOOLS")

        tools_info = self.get_tools_info()
        system_message.add_introduction(
            "TOOLS", json.dumps(tools_info, ensure_ascii=False)
        )
