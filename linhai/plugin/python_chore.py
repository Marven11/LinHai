"""Python注释检查插件，检测agent自发添加的注释并提醒。"""

import io
import tokenize
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from linhai.agent import Agent
from linhai.agent.lifecycle import AfterToolcallResult, Lifecycle
from linhai.agent.messages import (
    GlobalPrompt,
    PathPrompt,
    RuntimeMessage,
)
from linhai.tool.base import ToolCallResultMessage, FileContentToolResult
from linhai.base import Message, SystemMessage, UserMessage
from linhai.machine_control import MachineControl
from linhai.registry import Registry

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


def _extract_comments(source: str) -> list[str] | None:
    """使用tokenize提取Python源代码中的#注释。在语法错误时返回None"""
    comments = []
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    try:
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                comments.append(tok.string)
        return comments
    except (tokenize.TokenError, IndentationError):
        return None


def _read_file_content(filepath: str) -> str | None:
    file_path = Path(filepath)
    if not file_path.exists() or not file_path.is_file():
        return None
    return file_path.read_text(encoding="utf-8")


def _get_context_contents(agent: "linhai_agent") -> list[str]:
    checked_types = (
        UserMessage,
        GlobalPrompt,
        PathPrompt,
        SystemMessage,
    )
    contents = []
    for msg in agent.message_processor.get_messages():
        if isinstance(msg, checked_types):
            content = msg.get_content()
            if content is not None:
                contents.append(content)
        elif isinstance(msg, ToolCallResultMessage) and isinstance(
            msg.result, FileContentToolResult
        ):
            contents.append(msg.result.content)
    return contents


class PythonCommentCheckerPlugin:
    """检查Python文件中agent自发添加的注释。"""

    def __init__(self, registry: Registry):
        self.registry = registry

    def register(self, lifecycle: "Lifecycle") -> None:
        lifecycle.after_toolcall.register(self.after_toolcall)

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> AfterToolcallResult | None:
        machine_control = self.registry.get_member_typechecked(
            "machine_control", MachineControl
        )
        if machine_control.target_machine != "master_host":
            return None

        if status != "success":
            return None

        if tool_name not in ("write_file", "replace_file_content"):
            return None

        filepath = toolcall_arguments.get("filepath", "")
        if not str(filepath).endswith(".py"):
            return None

        agent = self.registry.get_member_typechecked("agent", Agent)

        if tool_name == "write_file":
            content = toolcall_arguments.get("content", "")
            new_comments = _extract_comments(content)
        else:
            old = toolcall_arguments.get("old", "")
            new = toolcall_arguments.get("new", "")
            file_content = _read_file_content(filepath)
            if file_content is None:
                return None
            file_comments = _extract_comments(file_content)
            if not file_comments:
                return None
            new_comments = [c for c in file_comments if c not in old and c in new]

        if not new_comments:
            return None

        context_contents = _get_context_contents(agent)
        agent_comments = [
            c for c in new_comments if not any(c in ctx for ctx in context_contents)
        ]

        if not agent_comments:
            return None

        comment_list = ", ".join(f"`{c}`" for c in agent_comments)
        return AfterToolcallResult(
            warnings=[
                RuntimeMessage(f"你添加了注释{comment_list}? 有注释相关的要求吗？")
            ]
        )
