from typing import Tuple, TYPE_CHECKING
import asyncio
from linhai.llm import Answer, Message
from linhai.llm_manager import LlmManager
from linhai.parsed_message import ParsedAnswer
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import RuntimeMessage
from linhai.registry import Registry
from linhai.utils.common import UiNotice
from linhai.llm import UserMessage, AssistantMessage, ToolCallMessage
from linhai.agent.user_message_handler import UserMessageHandler

if TYPE_CHECKING:
    from linhai.agent.toolcall import AgentToolcall
    from linhai.agent.message import AgentMessage
    from linhai.agent.main import Agent


class AgentLlm:
    """AgentLlm类，负责管理LLM调用、Answer解析和打断逻辑。"""

    def __init__(
        self,
        llm_manager: LlmManager,
        registry: Registry,
        toolcall_processor: "AgentToolcall",
        message_processor: "AgentMessage",
    ):
        """初始化AgentLlm。

        Args:
            llm_manager: LlmManager实例
            registry: Registry实例
            toolcall_processor: AgentToolcall实例
            message_processor: AgentMessage实例
        """
        self.llm_manager = llm_manager
        self.registry = registry
        self.toolcall_processor = toolcall_processor
        self.message_processor = message_processor
        self._current_parsed_answer: ParsedAnswer | None = None
        self.current_answer: Answer | None = None

    async def call_and_wait_llm(self) -> Tuple[Answer, ParsedAnswer, bool]:
        """调用LLM并等待解析完成。

        Returns:
            Tuple[Answer, ParsedAnswer, bool]: (Answer, ParsedAnswer, 是否正常完成)
        """
        from .main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        lifecycle = agent.lifecycle

        await lifecycle.trigger_before_message_generation()

        answer: Answer = await self.llm_manager.answer_stream(
            self.message_processor.get_messages()
        )

        self.current_answer = answer

        parsed_answer = ParsedAnswer(
            answer, lifecycle, agent=agent, registry=self.registry
        )
        await parsed_answer.start_parsing()
        await lifecycle.trigger_after_new_parsed_answer(parsed_answer)
        await self.registry.send("parsed_agent_answer", parsed_answer)

        completed_normally = await parsed_answer.wait_parsing()
        return answer, parsed_answer, completed_normally

    async def interrupt(self, agent_message: str, ui_notice: str):
        """打断当前Answer并添加自定义消息。

        Args:
            agent_message: 发送给agent的消息内容，放入RuntimeMessage
            ui_notice: 发送给UI的通知内容，必须提供
        """
        from .main import Agent

        message_processor = self.message_processor
        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        agent = self.registry.get_member_typechecked("agent", Agent)

        if self._current_parsed_answer:
            self._current_parsed_answer.interrupt()

            await message_processor.add_new_message(RuntimeMessage(agent_message))

            if ui_notice is not None:
                interrupt_msg = UiNotice(level="WARNING", content=ui_notice)
            else:
                interrupt_msg = UiNotice(level="WARNING", content="Agent被打断")

            current_content = self._current_parsed_answer._answer.get_current_content()
            if "```json toolcall" in current_content:
                await message_processor.add_new_message(
                    RuntimeMessage("当前所有工具调用全部被忽略，请重新调用")
                )

            self._current_parsed_answer = None

            await self.registry.send_if_exists("ui_log", interrupt_msg)

            agent = self.registry.get_member_typechecked("agent", Agent)
            agent.state = "working"

            user_message_handler = self.registry.get_member_typechecked(
                "user_message_handler", UserMessageHandler
            )
            while user_message_handler.has_message():
                await user_message_handler.receive_and_dispatch()
