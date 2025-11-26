"""SubAgent相关插件实现。"""

from typing import Any, TYPE_CHECKING
import asyncio
import logging
import shlex
import os

from linhai.llm import ToolCallMessage, Answer
from linhai.utils import CliRuntimeNotice, generate_id
from linhai.agent.plugin import Plugin
from linhai.agent.base import RuntimeMessage, WAITING_USER_MARKER
from linhai.prompt import get_subagent_prompt

if TYPE_CHECKING:
    import linhai.agent
    import linhai.subagent

logger = logging.getLogger(__name__)


class SubAgentCollaborationPlugin(Plugin):
    """基于lifecycle事件驱动subagent协作的Plugin。

    在工具失败、工具冲突时启动subagent，检查agent是否违反了多个工具的调用规则。
    """

    async def tool_failure(
        self,
        agent: "linhai.agent.Agent",
        tool_call: ToolCallMessage,
        error: Any,
    ) -> None:
        """在工具调用失败时启动subagent检查规则违反。"""
        assert agent.current_answer is not None

        full_response = agent.current_answer.get_current_content()
        if full_response.count("```json toolcall") <= 1:
            return

        interrupt_msg = CliRuntimeNotice(
            level="WARNING", content="启动SubAgent检查工具调用"
        )
        await self.group_chat.send_if_exists("ui_log", interrupt_msg)

        from linhai.subagent import SubAgentManager

        subagent_manager = self.group_chat.get_members(
            "subagent_manager", SubAgentManager
        )

        asyncio.create_task(
            self._check_violations(subagent_manager, full_response, tool_call, error)
        )

    async def tool_conflict(
        self,
        agent: "linhai.agent.Agent",
        tool_call: ToolCallMessage,
        conflicting_tools: list[str],
    ) -> None:
        """在工具调用冲突时启动subagent检查规则违反。"""
        interrupt_msg = CliRuntimeNotice(
            level="WARNING", content="启动SubAgent检查工具冲突"
        )
        await self.group_chat.send_if_exists("ui_log", interrupt_msg)

        from linhai.subagent import SubAgentManager

        subagent_manager = self.group_chat.get_members(
            "subagent_manager", SubAgentManager
        )
        assert agent.current_answer is not None

        full_response = agent.current_answer.get_current_content()

        asyncio.create_task(
            self._check_conflict_violations(
                subagent_manager, full_response, tool_call, conflicting_tools
            )
        )

    async def _check_violations(
        self,
        subagent_manager: "linhai.subagent.SubAgentManager",
        full_response: str,
        tool_call: ToolCallMessage,
        error: Any,
    ) -> None:
        """在后台任务中检查agent是否违反规则。"""
        check_context = f"""**失败的工具调用详情:**
- 工具名称: {tool_call.function_name}
- 工具参数: {tool_call.function_arguments}
- 错误信息: {error}"""

        task_message = get_subagent_prompt("violation_checker").format(
            agent_full_response=full_response, check_context=check_context
        )

        await subagent_manager.create_subagent(
            agent_type="violation_checker",
            name=generate_id("violation_subagent"),
            task_message=task_message,
            max_answer_times=1,
        )

    async def _check_conflict_violations(
        self,
        subagent_manager: "linhai.subagent.SubAgentManager",
        full_response: str,
        tool_call: ToolCallMessage,
        conflicting_tools: list[str],
    ) -> None:
        """在后台任务中检查agent是否违反规则（工具冲突情况）。"""
        check_context = f"""**工具冲突详情:**
- 冲突工具名称: {tool_call.function_name}
- 工具参数: {tool_call.function_arguments}
- 与以下工具冲突: {', '.join(conflicting_tools)}"""

        task_message = get_subagent_prompt("violation_checker").format(
            agent_full_response=full_response, check_context=check_context
        )

        await subagent_manager.create_subagent(
            agent_type="violation_checker",
            name=generate_id("violation_subagent"),
            task_message=task_message,
            max_answer_times=1,
        )

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到lifecycle回调。"""
        lifecycle.register_tool_failure(self.tool_failure)
        lifecycle.register_tool_conflict(self.tool_conflict)


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

            if tool_name in ["run_simple_command", "run_complex_command"]:
                command = arguments.get("command", "")

                if self._is_git_command(command):
                    agent.message_processor.append_message(
                        RuntimeMessage(
                            f"错误：有未解答的澄清问题，禁止使用git命令。"
                            f"命令 '{command}' 被识别为git命令，请先回复所有SubAgent的澄清问题。"
                        )
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
        except Exception:
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