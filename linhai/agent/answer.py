from typing import Tuple, TYPE_CHECKING, cast
import asyncio
from linhai.llm import Answer, Message
from linhai.llm_manager import LlmManager
from linhai.parsed_message import ParsedAnswer
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import RuntimeMessage
from linhai.group_chat import GroupChat
from linhai.utils import CliRuntimeNotice
from linhai.llm import UserMessage, AssistantMessage, ToolCallMessage

if TYPE_CHECKING:
    from linhai.agent.toolcall import AgentToolcall
    from linhai.agent.message import AgentMessage
    from linhai.agent.main import Agent


class AgentLlm:
    """AgentLlm类，负责管理LLM调用、Answer解析和打断逻辑。"""

    def __init__(
        self,
        llm_manager: LlmManager,
        group_chat: GroupChat,
        agent: object,
        toolcall_processor: "AgentToolcall",
        message_processor: "AgentMessage",
    ):
        """初始化AgentLlm。

        Args:
            llm_manager: LlmManager实例
            group_chat: GroupChat实例
            agent: Agent实例（用于访问state）
            toolcall_processor: AgentToolcall实例
            message_processor: AgentMessage实例
        """
        self.llm_manager = llm_manager
        self.group_chat = group_chat
        self.agent = agent
        self.toolcall_processor = toolcall_processor
        self.message_processor = message_processor
        self._current_parsed_answer: ParsedAnswer | None = None
        self._queued_messages: list = []

    async def call_and_wait_llm(self) -> Tuple[Answer, ParsedAnswer, bool]:
        """调用LLM并等待解析完成。

        Returns:
            Tuple[Answer, ParsedAnswer, bool]: (Answer, ParsedAnswer, 是否正常完成)
        """
        agent = cast("Agent", self.agent)
        lifecycle = agent.lifecycle

        await lifecycle.trigger_before_message_generation()

        answer: Answer = await self.llm_manager.answer_stream(
            self.message_processor.get_messages()
        )

        self.current_answer = answer

        parsed_answer = ParsedAnswer(answer, lifecycle, agent=agent)
        await parsed_answer.start_parsing()
        await lifecycle.trigger_after_new_parsed_answer(parsed_answer)
        await self.group_chat.send("parsed_agent_answer", parsed_answer)

        completed_normally = await parsed_answer.wait_parsing()
        return answer, parsed_answer, completed_normally

    async def interrupt(self, agent_message: str, ui_notice: str):
        """打断当前Answer并添加自定义消息。

        Args:
            agent_message: 发送给agent的消息内容，放入RuntimeMessage
            ui_notice: 发送给UI的通知内容，必须提供
        """
        message_processor = self.message_processor
        lifecycle = self.group_chat.get_member_typechecked("lifecycle", Lifecycle)
        agent = cast("Agent", self.agent)

        if self._current_parsed_answer:
            self._current_parsed_answer.interrupt()

            await message_processor.add_new_message(RuntimeMessage(agent_message))

            if ui_notice is not None:
                interrupt_msg = CliRuntimeNotice(level="WARNING", content=ui_notice)
            else:
                interrupt_msg = CliRuntimeNotice(level="WARNING", content="Agent被打断")

            current_content = self._current_parsed_answer._answer.get_current_content()
            if "```json toolcall" in current_content:
                await message_processor.add_new_message(
                    RuntimeMessage("当前所有工具调用全部被忽略，请重新调用")
                )

            self._current_parsed_answer = None

            await self.group_chat.send_if_exists("ui_log", interrupt_msg)
            from .main import Agent

            agent = cast(Agent, self.agent)
            agent.state = "working"

            while not self.group_chat.is_empty("user_message"):
                msg = await self.group_chat.receive("user_message")
                assert isinstance(msg, UserMessage)
                await agent.handle_user_message(msg)
