"""Python注释检查插件，检测agent自发添加的注释并提醒。"""

import io
import tokenize
from typing import TYPE_CHECKING, Literal, Union

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import (
    FileContentMessage,
    GlobalPrompt,
    PathPrompt,
    RuntimeMessage,
)
from linhai.llm import Message, SystemMessage, UserMessage
from linhai.machine_control import MachineControl
from linhai.registry import Registry

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


def _extract_comments(source: str) -> list[str]:
    """使用tokenize提取Python源代码中的#注释。"""
    comments = []
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            comments.append(tok.string)
    return comments


def _get_context_contents(agent: "linhai_agent") -> list[str]:
    """从上下文消息中获取文本内容，用于过滤外部指定的注释。"""
    checked_types = (
        UserMessage,
        FileContentMessage,
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
    return contents


class PythonCommentCheckerPlugin:
    """检查Python文件中agent自发添加的注释。"""

    def __init__(self, registry: Registry):
        self.registry = registry

    def register(self, lifecycle: "Lifecycle") -> None:
        lifecycle.register_after_toolcall(self.after_toolcall)

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
            old_comments = set(_extract_comments(old))
            new_comments = [c for c in _extract_comments(new) if c not in old_comments]

        if not new_comments:
            return None

        context_contents = _get_context_contents(agent)
        agent_comments = [
            c for c in new_comments if not any(c in ctx for ctx in context_contents)
        ]

        if not agent_comments:
            return None

        comment_list = ", ".join(f"`{c}`" for c in agent_comments)
        await agent.message_processor.add_new_message(
            RuntimeMessage(f"你添加了注释{comment_list}? 有注释相关的要求吗？")
        )
        return None
