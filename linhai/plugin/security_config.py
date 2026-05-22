"""安全和配置插件。"""

import re

from linhai.type_hints import WithSecret
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal, Union

from linhai.agent.lifecycle import AfterToolcallResult, Lifecycle
from linhai.agent.messages import RuntimeMessage
from linhai.registry import Registry
from linhai.utils.i18n import t
from linhai.tool.base import SuccessfulToolResult, FailedToolResult
from linhai.base import Message

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    def __init__(self, registry: Registry):
        self.registry = registry

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
        with_secret: WithSecret | None,
        is_tool_failed_duplicated_error: bool,
    ) -> AfterToolcallResult | None:
        if status != "failed":
            return None

        if "with_secret" not in toolcall_arguments:
            return None

        return AfterToolcallResult(
            warnings=[
                RuntimeMessage(
                    "错误：with_secret参数应该在工具调用的顶层，与name、arguments平级，而不是在arguments内部！\n"
                    '正确格式：{"name": "tool_name", "with_secret": {"in_arguments": [...], "in_result": [...]}, "arguments": {...}}'
                )
            ],
            user_notices=["检测到with_secret参数位置错误"],
        )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_toolcall回调。"""
        lifecycle.after_toolcall.register(self.after_toolcall)


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
        with_secret: WithSecret | None,
        is_tool_failed_duplicated_error: bool,
    ) -> AfterToolcallResult | None:
        if tool_name == "call_with_secret":
            return None

        if not toolcall_arguments:
            return None

        arguments_str = str(toolcall_arguments)
        has_secret_pattern = self._SECRET_PATTERN.search(arguments_str)
        if not has_secret_pattern:
            return None

        if with_secret:
            return None

        return AfterToolcallResult(
            warnings=[
                RuntimeMessage(
                    f"警告：检测到工具调用参数中包含`<$KEY$>`占位符，但没有使用`with_secret`字段: {has_secret_pattern}。可能在{tool_name}工具调用中...\n"
                    f"你是希望{has_secret_pattern}被替换为实际的值还是将这个字面量填入工具参数中？请确认：\n"
                    "1. 如果确实需要使用secret，请将`with_secret`字段添加到工具调用的顶层（与name、arguments平级）\n"
                    "2. 如果只是想写入包含`<$$>`的文本内容，可以忽略此警告"
                )
            ],
            user_notices=["检测到未使用with_secret但包含secret占位符，已提醒agent"],
        )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_toolcall回调。"""
        lifecycle.after_toolcall.register(self.after_toolcall)


class CommandWhitelistPlugin(Plugin):
    """命令白名单插件，检查process_create命令是否在配置的允许列表中。"""

    def __init__(self, registry, allowed_commands: list[list[str]]):
        super().__init__(registry)
        self.allowed_commands = allowed_commands

    def register(self, lifecycle: "Lifecycle"):
        lifecycle.before_message_generation.register(self.before_message_generation)
        lifecycle.before_tool_call.register(self.before_tool_call)

    async def before_message_generation(self) -> None:
        from linhai.agent import Agent
        from linhai.agent.messages import RuntimeMessage

        agent = self.registry.get_member_typechecked("agent", Agent)
        if agent and self.allowed_commands:
            allowed_str = ", ".join([" ".join(cmd) for cmd in self.allowed_commands])
            agent.message_processor.update_notification_message(
                RuntimeMessage(
                    t(
                        {
                            "zh_CN": f"允许的命令: {allowed_str}",
                            "en": f"Allowed commands: {allowed_str}",
                        }
                    )
                ),
                source="command_whitelist",
                sort_value=10,
            )

    async def before_tool_call(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        with_secret: WithSecret | None,
    ) -> Union[SuccessfulToolResult, FailedToolResult, dict, None]:
        if tool_name != "process_create":
            return None

        argv = toolcall_arguments.get("argv")
        if argv is None:
            return FailedToolResult(content="process_create缺少argv参数")

        if not isinstance(argv, list):
            return FailedToolResult(
                content=f"argv参数必须是列表类型，但收到{type(argv).__name__}"
            )

        for i, arg in enumerate(argv):
            if not isinstance(arg, str):
                return FailedToolResult(
                    content=f"argv参数的第{i}个元素必须是字符串类型，但收到{type(arg).__name__}"
                )

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

        return FailedToolResult(
            content=f"命令 {' '.join(argv)} 不在白名单中。允许的命令: {self.allowed_commands}"
        )


class ProcessArgvCheckerPlugin(Plugin):
    """检查process_create的argv参数是否包含bash语法操作符的插件。"""

    BASH_OPERATOR_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"\$\("),
        re.compile(r"`"),
        re.compile(r"\$\{"),
        re.compile(r"2>&1"),
        re.compile(r"&&"),
        re.compile(r"\|\|"),
        re.compile(r">>"),
        re.compile(r"<<"),
        re.compile(r"(?<!\|)\|(?!\|)"),
        re.compile(r"(?<!&)&(?!&)"),
        re.compile(r"(?<!>)>(?!>)"),
        re.compile(r"(?<!<)<(?!<)"),
        re.compile(r"(?:^|\s);(?:\s|$)"),
        re.compile(r"\n"),
    ]

    def __init__(self, registry):
        super().__init__(registry)

    def register(self, lifecycle):
        lifecycle.before_tool_call.register(self.before_tool_call)
        lifecycle.after_toolcall.register(self.after_toolcall)

    async def before_tool_call(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        with_secret: WithSecret | None,
    ) -> Union[SuccessfulToolResult, FailedToolResult, dict, None]:
        if tool_name == "process_create":
            argv = toolcall_arguments.get("argv")
            if argv is None:
                return None

            if not isinstance(argv, list):
                return FailedToolResult(
                    content=f"argv参数必须是列表类型，但收到{type(argv).__name__}"
                )

            for i, arg in enumerate(argv):
                if not isinstance(arg, str):
                    return FailedToolResult(
                        content=f"argv参数的第{i}个元素必须是字符串类型，但收到{type(arg).__name__}"
                    )

        return None

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: str,
        message,
        toolcall_arguments: dict,
        with_secret: WithSecret | None,
        is_tool_failed_duplicated_error: bool,
    ) -> AfterToolcallResult | None:
        _ = (tool_index, message, with_secret, is_tool_failed_duplicated_error)
        if tool_name != "process_create":
            return None

        argv = toolcall_arguments.get("argv")
        if not argv or not isinstance(argv, list):
            return None

        warnings_list = [
            f"参数[{i}]: '{arg}' 包含可能的bash操作符"
            for i, arg in enumerate(argv)
            if isinstance(arg, str)
            and any(p.search(arg) for p in self.BASH_OPERATOR_PATTERNS)
        ]

        if warnings_list:
            warning_msg = (
                "警告：process_create的argv参数中包含可能的bash语法操作符:"
                + repr(warnings_list)
                + "注意：这些操作符在直接执行进程时可能不会被解释，但如果执行shell可能会被解释。请确认参数安全性。"
            )
            return AfterToolcallResult(
                warnings=[RuntimeMessage(warning_msg)],
                user_notices=["检测到argv参数包含bash操作符，已提醒agent"],
            )

        return None
