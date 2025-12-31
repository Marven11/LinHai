"""违规检查SubAgent类型实现，包含专用插件。"""

from typing import Any
import asyncio


from linhai.llm import ToolCallMessage
from linhai.utils import CliRuntimeNotice, generate_id
from linhai.agent.plugin import Plugin
from linhai.subagent.main import SubAgent
from .prompts import VIOLATION_CHECKER_SYSTEM_PROMPT, VIOLATION_CHECKER_USER_PROMPT

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from linhai.agent import Agent, Lifecycle
    from linhai.agent.plugin import Plugin
    from linhai.subagent import SubAgentManager
    from linhai.subagent.main import SubAgent
    from linhai.utils import CliRuntimeNotice, generate_id


class ViolationCheckerSubAgent(SubAgent):
    """违规检查SubAgent。"""

    def __init__(
        self,
        name: str,
        task_message: str,
        llm,
        group_chat,
        max_answer_times: int | None,
        initial_messages=None,
    ):
        super().__init__(
            agent_type="violation_checker",
            name=name,
            task_message=task_message,
            llm=llm,
            group_chat=group_chat,
            max_answer_times=max_answer_times,
            initial_messages=initial_messages,
        )

    def get_system_message_prompt(self) -> str:
        """返回违规检查专用的系统消息prompt。"""
        import json
        from linhai.tool.base import to_tools_info

        tools_json = json.dumps(
            to_tools_info(self.toolset.get_tools()),
            ensure_ascii=False,
        )
        return VIOLATION_CHECKER_SYSTEM_PROMPT.replace("{|TOOLS|}", tools_json)


class ViolationCheckerPlugin(Plugin):
    """基于lifecycle事件驱动violation checker subagent协作的Plugin。"""

    async def tool_failure(
        self,
        agent: "Agent",
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
        agent: "Agent",
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
        subagent_manager: "SubAgentManager",
        full_response: str,
        tool_call: ToolCallMessage,
        error: Any,
    ) -> None:
        """在后台任务中检查agent是否违反规则。"""
        check_context = f"""**失败的工具调用详情:**
- 工具名称: {tool_call.function_name}
- 工具参数: {tool_call.function_arguments}
- 错误信息: {error}"""

        task_message = VIOLATION_CHECKER_USER_PROMPT.format(
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
        subagent_manager: "SubAgentManager",
        full_response: str,
        tool_call: ToolCallMessage,
        conflicting_tools: list[str],
    ) -> None:
        """在后台任务中检查agent是否违反规则（工具冲突情况）。"""
        check_context = f"""**工具冲突详情:**
- 冲突工具名称: {tool_call.function_name}
- 工具参数: {tool_call.function_arguments}
- 与以下工具冲突: {', '.join(conflicting_tools)}"""

        task_message = VIOLATION_CHECKER_USER_PROMPT.format(
            agent_full_response=full_response, check_context=check_context
        )

        await subagent_manager.create_subagent(
            agent_type="violation_checker",
            name=generate_id("violation_subagent"),
            task_message=task_message,
            max_answer_times=1,
        )

    def register(self, lifecycle: "Lifecycle"):
        """注册到lifecycle回调。"""
        lifecycle.register_tool_failure(self.tool_failure)
        lifecycle.register_tool_conflict(self.tool_conflict)
