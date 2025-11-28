"""SubAgent通用插件实现。"""

from typing import TYPE_CHECKING
import logging
import shlex
import os

from linhai.llm import ToolCallMessage, Answer
from linhai.utils import CliRuntimeNotice
from linhai.agent.plugin import Plugin
from linhai.agent.base import RuntimeMessage, WAITING_USER_MARKER

if TYPE_CHECKING:
    import linhai.agent

logger = logging.getLogger(__name__)


class GitBlockingPlugin(Plugin):
    """阻止Agent在有未解答澄清时使用git命令的Plugin。"""

    async def before_tool_call(self, tool_call: ToolCallMessage) -> bool:
        """检查是否有未解答的澄清，如果有则阻止使用git命令。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        from linhai.subagent.clarification import ClarificationManager

        clarification_manager = self.group_chat.get_members(
            "clarification_manager", ClarificationManager
        )
        if (
            clarification_manager
            and clarification_manager.has_unanswered_clarifications()
        ):

            tool_name = tool_call.function_name
            arguments = tool_call.function_arguments

            if tool_name in ["run_command"]:
                command = arguments.get("command", "")

                if self._is_git_command(command):
                    agent.message_processor.append_message(
                        RuntimeMessage(
                            f"错误：有未解答的澄清问题，禁止使用git命令。"
                            f"命令 '{command}' 被识别为git命令，请先回复所有SubAgent的澄清问题。"
                        )
                    )

                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="ERROR", content=f"Git命令被阻止: {command}"
                        ),
                    )

                    return True
        return False

    def _is_git_command(self, command: str) -> bool:
        """精确检测是否为git命令"""

        try:
            parts = shlex.split(command.strip())
            if not parts:
                return False

            cmd = parts[0]

            if cmd == "git":
                return True

            if cmd.startswith("git-"):
                return True

            basename = os.path.basename(cmd)
            if basename == "git" or basename == "git.exe":
                return True

            return False
        except (ValueError, OSError):
            return False

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到before_tool_call回调。"""
        lifecycle.register_before_tool_call(self.before_tool_call)


class ClarificationWaitingUserPlugin(Plugin):
    """阻止Agent在有未解答澄清时进入等待用户状态的Plugin。"""

    async def before_waiting_user(self, agent: "linhai.agent.Agent"):
        """检查是否有未解答的澄清，如果有则阻止进入等待用户状态。"""

        from linhai.subagent.clarification import ClarificationManager

        clarification_manager = self.group_chat.get_members(
            "clarification_manager", ClarificationManager
        )
        if (
            clarification_manager
            and clarification_manager.has_unanswered_clarifications()
        ):
            agent.message_processor.append_message(
                RuntimeMessage(
                    "错误：有未解答的澄清问题，禁止进入等待用户状态。"
                    "请先回复所有SubAgent的澄清问题。"
                )
            )
            agent.state = "working"

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到before_waiting_user回调。"""
        lifecycle.register_before_waiting_user(self.before_waiting_user)


class ClarificationBlockingPlugin(Plugin):
    """阻止Agent在有未解答澄清时停下等待用户的Plugin。"""

    async def after_message_generation(
        self, _answer: Answer, full_response: str, _tool_calls
    ):
        """检查是否有未解答的澄清，如果有则阻止使用等待用户标记。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        from linhai.subagent.clarification import ClarificationManager

        clarification_manager = self.group_chat.get_members(
            "clarification_manager", ClarificationManager
        )
        if (
            clarification_manager
            and clarification_manager.has_unanswered_clarifications()
        ):

            if WAITING_USER_MARKER in full_response:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"错误：有未解答的澄清问题，禁止使用{WAITING_USER_MARKER!r}等待用户。"
                        "请先使用工具回复所有SubAgent的澄清问题。"
                    )
                )
                agent.state = "working"

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)
