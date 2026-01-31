"""违规检查SubAgent类型实现，包含专用插件。"""

from typing import Any, Literal, Union
import asyncio


from linhai.llm import ToolCallMessage
from linhai.utils import CliRuntimeNotice, generate_id
from linhai.plugin import Plugin
from linhai.agent.base import RuntimeMessage
from linhai.subagent.main import SubAgent
from .prompts import VIOLATION_CHECKER_SYSTEM_PROMPT, VIOLATION_CHECKER_USER_PROMPT

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from linhai.agent import Agent, Lifecycle
    from linhai.plugin import Plugin  # pylint: disable=reimported
    from linhai.subagent import SubAgentManager  # pylint: disable=reimported
    from linhai.subagent.main import SubAgent  # pylint: disable=reimported
    from linhai.utils import CliRuntimeNotice, generate_id  # pylint: disable=reimported


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

    async def on_tool_result(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        result_content: str | None,
        toolcall_arguments: dict | None,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, "RuntimeMessage"]:
        """处理工具调用结果，在工具失败或冲突时启动subagent检查规则违反。"""
        if status == "failed":
            # 工具调用失败情况（包括冲突）
            from linhai.subagent import SubAgentManager
            from linhai.agent import Agent
            
            agent = self.group_chat.get_members("agent", Agent)
            assert agent.current_answer is not None

            full_response = agent.current_answer.get_current_content()
            if full_response.count("```json toolcall") <= 1:
                return None

            if is_tool_failed_duplicated_error:
                # 工具冲突情况
                interrupt_msg = CliRuntimeNotice(
                    level="WARNING", content="启动SubAgent检查工具冲突"
                )
                check_context = f"""**工具冲突详情:**
- 冲突工具名称: {tool_name}
- 工具参数: {toolcall_arguments}
- 错误信息: {result_content}"""
            else:
                # 普通工具失败
                interrupt_msg = CliRuntimeNotice(
                    level="WARNING", content="启动SubAgent检查工具调用"
                )
                check_context = f"""**失败的工具调用详情:**
- 工具名称: {tool_name}
- 工具参数: {toolcall_arguments}
- 错误信息: {result_content}"""
            
            await self.group_chat.send_if_exists("ui_log", interrupt_msg)

            subagent_manager = self.group_chat.get_members(
                "subagent_manager", SubAgentManager
            )

            task_message = VIOLATION_CHECKER_USER_PROMPT.format(
                agent_full_response=full_response, check_context=check_context
            )

            await subagent_manager.create_subagent(
                agent_type="violation_checker",
                name=generate_id("violation_subagent"),
                task_message=task_message,
                max_answer_times=1,
            )
        
        return None

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
        lifecycle.register_on_tool_result(self.on_tool_result)
