"""sudo标准输入检查插件，用于拦截缺少-S标志的sudo命令调用。"""

from typing import Union
from linhai.agent.lifecycle import Lifecycle
from linhai.group_chat import GroupChat
from linhai.tool.base import ToolResultFailed, ToolResultSuccess
from linhai.plugin import Plugin


class SudoStdioCheckerPlugin(Plugin):
    """检查process_create工具调用中是否包含sudo且缺少-S标志。"""

    def __init__(self, group_chat: GroupChat):
        super().__init__(group_chat)

    def register(self, lifecycle: Lifecycle) -> None:
        """注册到before_tool_call回调。"""
        lifecycle.register_before_tool_call(self.before_tool_call)

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
