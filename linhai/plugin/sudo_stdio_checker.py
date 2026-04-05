"""sudo标准输入和bash -c命令检查插件，用于拦截缺少-S标志的sudo命令并提醒agent避免使用bash -c。"""

import time
from typing import TYPE_CHECKING, Union
from linhai.agent import Agent
from linhai.agent.messages import RuntimeMessage
from linhai.agent.lifecycle import Lifecycle
from linhai.registry import Registry
from linhai.tool.base import ToolResultFailed, ToolResultSuccess
from linhai.plugin import Plugin
from linhai.utils.common import UiNotice

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


class SudoStdioCheckerPlugin(Plugin):
    """检查process_create工具调用中是否包含sudo且缺少-S标志，或使用bash -c。"""

    TIME_WINDOW_SECONDS = 300

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self._last_warning_time: float | None = None

    def register(self, lifecycle: Lifecycle) -> None:
        """注册到before_tool_call和after_toolcall回调。"""
        lifecycle.register_before_tool_call(self.before_tool_call)
        lifecycle.register_after_toolcall(self.after_toolcall)

    async def before_tool_call(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
    ) -> Union[ToolResultSuccess, ToolResultFailed, dict, None]:
        """在工具调用前检查sudo命令。"""
        if tool_name != "process_create":
            return None

        argv = toolcall_arguments.get("argv")
        if not argv:
            return None

        if not isinstance(argv, list):
            return ToolResultFailed(
                content=f"argv参数必须是列表类型，但收到{type(argv).__name__}"
            )

        if len(argv) == 0:
            return None

        if argv[0] != "sudo":
            return None

        has_stdin_flag = any(
            arg == "-S" or arg == "--stdin" or arg.startswith("-S") for arg in argv
        )

        if not has_stdin_flag:
            return ToolResultFailed(
                content="sudo命令必须使用-S标志以确保从标准输入读取密码喵~。请使用sudo -S或sudo --stdin。"
            )

        return None

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: str,
        message,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ):
        """在工具调用后检查bash -c命令。"""
        if tool_name != "process_create":
            return None

        argv = toolcall_arguments.get("argv")
        if not argv or not isinstance(argv, list) or len(argv) < 2:
            return None

        first_arg = argv[0]
        if first_arg != "bash" and first_arg != "/bin/bash":
            return None

        second_arg = argv[1]
        if second_arg != "-c":
            return None

        if self._last_warning_time is not None:
            if time.time() - self._last_warning_time < self.TIME_WINDOW_SECONDS:
                return None

        self._last_warning_time = time.time()
        agent = self.registry.get_member_typechecked("agent", Agent)
        await agent.message_processor.add_new_message(
            RuntimeMessage(
                "警告：检测到你使用了bash -c运行一长串命令，这会导致命令难以被用户理解、审查和解析。"
                "如果方便的话请避免自发使用bash -c，直接调用process_create工具并传入参数列表会更好喵~"
            )
        )
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="WARNING",
                content="Agent使用了bash -c运行命令，已提醒agent避免使用",
            ),
        )
        return None
