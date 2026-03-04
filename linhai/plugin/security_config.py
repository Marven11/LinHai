"""安全和配置插件。"""

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal, Union

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import RuntimeMessage
from linhai.group_chat import GroupChat
from linhai.utils import CliRuntimeNotice
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.llm import Message

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    @abstractmethod
    def register(self, lifecycle: "Lifecycle") -> None:
        """将Plugin注册到Lifecycle中。"""


class WithSecretParameterPositionPlugin(Plugin):
    """检查工具调用中with_secret参数位置错误的插件"""

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        if status != "failed":
            return None

        if "with_secret" not in toolcall_arguments:
            return None

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(level="WARNING", content="检测到with_secret参数位置错误"),
        )
        return RuntimeMessage(
            "错误：with_secret参数应该在工具调用的顶层，与name、arguments平级，而不是在arguments内部！\n"
            '正确格式：{"name": "tool_name", "with_secret": ["KEY"], "arguments": {...}}'
        )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_toolcall回调。"""
        lifecycle.register_after_toolcall(self.after_toolcall)


class MissingWithSecretWarningPlugin(Plugin):
    """检查未使用with_secret但包含<$KEY$>的插件"""

    _SECRET_PATTERN = re.compile(r"<\$[A-Z_]+\$>")

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        if not toolcall_arguments:
            return None

        arguments_str = str(toolcall_arguments)
        has_secret_pattern = self._SECRET_PATTERN.search(arguments_str)
        if not has_secret_pattern:
            return None

        if with_secret:
            return None

        agent = self.group_chat.get_member_typechecked("agent", Agent)
        await agent.message_processor.add_new_message(
            RuntimeMessage(
                "警告：检测到工具调用参数中包含`<$KEY$>`占位符，但没有使用`with_secret`字段。\n"
                "请确认：\n"
                "1. 如果确实需要使用secret，请将`with_secret`字段添加到工具调用的顶层（与name、arguments平级）\n"
                "2. 如果只是想写入包含`<$$>`的文本内容，可以忽略此警告"
            )
        )

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content="检测到可能忘记使用with_secret的工具调用"
            ),
        )
        return None

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_toolcall回调。"""
        lifecycle.register_after_toolcall(self.after_toolcall)


class CommandWhitelistPlugin(Plugin):
    """命令白名单插件，检查process_create命令是否在配置的允许列表中。"""

    def __init__(self, group_chat, config):
        super().__init__(group_chat)
        self.config = config
        self.allowed_commands = config.agent.allowed_commands

    def register(self, lifecycle: "Lifecycle"):
        lifecycle.register_before_message_generation(self.before_message_generation)
        lifecycle.register_before_tool_call(self.before_tool_call)

    async def before_message_generation(
        self, enable_compress: bool, disable_waiting_user_warning: bool
    ) -> None:
        from linhai.agent import Agent
        from linhai.agent.base import RuntimeMessage

        agent = self.group_chat.get_member_typechecked("agent", Agent)
        if agent and self.allowed_commands:
            allowed_str = ", ".join([" ".join(cmd) for cmd in self.allowed_commands])
            agent.message_processor.update_notification_message(
                RuntimeMessage(f"允许的命令: {allowed_str}"),
                source="command_whitelist",
                sort_value=10,
            )

    async def before_tool_call(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
    ) -> Union[ToolResultSuccess, ToolResultFailed, dict, None]:
        if tool_name != "process_create":
            return None

        argv = toolcall_arguments.get("argv")
        if argv is None:
            return ToolResultFailed(content="process_create缺少argv参数")

        if not self.allowed_commands:
            return None

        if any(
            len(allowed) <= len(argv)
            and all(
                cmd_elem == allowed_elem
                for cmd_elem, allowed_elem in zip(argv, allowed)
            )
            for allowed in self.allowed_commands
        ):
            return None

        return ToolResultFailed(
            content=f"命令 {' '.join(argv)} 不在白名单中。允许的命令: {self.allowed_commands}"
        )


class ProcessArgvCheckerPlugin(Plugin):
    """检查process_create的argv参数是否包含bash语法操作符的插件。"""

    BASH_OPERATORS = [
        "&&",
        "||",
        "|",
        ">",
        ">>",
        "<",
        "<<",
        "2>&1",
        ";",
        "\n",
        "$(",
        "`",
        "&",
        "${",
    ]

    def __init__(self, group_chat):
        super().__init__(group_chat)

    def register(self, lifecycle):
        lifecycle.register_before_tool_call(self.before_tool_call)

    async def before_tool_call(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
    ) -> Union[ToolResultSuccess, ToolResultFailed, dict, None]:
        if tool_name == "process_create":
            argv = toolcall_arguments.get("argv")
            if argv is None:
                return None

            warnings = [
                f"参数[{i}]: '{arg}' 包含可能的bash操作符"
                for i, arg in enumerate(argv)
                if any(op in arg for op in self.BASH_OPERATORS)
            ]

            if warnings:
                from linhai.agent import Agent
                from linhai.agent.base import RuntimeMessage

                warning_msg = (
                    "警告：process_create的argv参数中包含可能的bash语法操作符:"
                    + repr(warnings)
                    + "注意：这些操作符在直接执行进程时可能不会被解释，但如果执行shell可能会被解释。请确认参数安全性。"
                )
                agent = self.group_chat.get_member_typechecked("agent", Agent)
                await agent.message_processor.add_new_message(
                    RuntimeMessage(warning_msg)
                )

        return None
