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

    async def call_llm(
        self, messages: list[Message], queued_messages: list
    ) -> Tuple[ParsedAnswer, bool]:
        """调用LLM并返回解析好的ParsedAnswer。

        Args:
            messages: 消息历史
            queued_messages: 排队的消息

        Returns:
            Tuple[ParsedAnswer, bool]: (ParsedAnswer, 是否被打断)
        """
        lifecycle = self.group_chat.get_member_typechecked("lifecycle", Lifecycle)
        agent = cast("Agent", self.agent)
        self._queued_messages = queued_messages
        if self._queued_messages:
            await self.group_chat.send_if_exists(
                "ui_log", CliRuntimeNotice(level="INFO", content="排队消息被处理")
            )
            await self.message_processor.add_new_message(
                RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理：")
            )
            for msg in self._queued_messages:
                await self.message_processor.add_new_message(msg)
            self._queued_messages = []

        if self.message_processor.get_message_count() > 0:
            last_msg = self.message_processor.get_messages()[-1]
            if isinstance(last_msg, AssistantMessage):
                empty_user_msg = RuntimeMessage("继续")
                await self.message_processor.add_new_message(empty_user_msg)

        await lifecycle.trigger_before_message_generation()

        answer: Answer = await self.llm_manager.answer_stream(
            self.message_processor.get_messages()
        )

        parsed_answer = ParsedAnswer(answer, lifecycle, agent=agent)
        self._current_parsed_answer = parsed_answer
        await parsed_answer.start_parsing()
        await lifecycle.trigger_after_new_parsed_answer(parsed_answer)
        await self.group_chat.send("parsed_agent_answer", parsed_answer)

        completed_normally = await parsed_answer.wait_parsing()
        if not completed_normally:
            return parsed_answer, True

        chat_message = answer.get_message()
        assert isinstance(chat_message, AssistantMessage)
        full_response = chat_message.message
        await self.message_processor.add_new_message(chat_message)

        tool_calls, errors = parsed_answer.get_toolcalls()

        for error in errors:
            await self.message_processor.add_new_message(RuntimeMessage(error))

        self.toolcall_processor.start_new_tool_call_round()

        for i, call in enumerate(tool_calls, start=1):
            if "name" in call and "arguments" in call:
                assert_success = call.get("assert_success", True)
                with_secret = call.get("with_secret", None)
                tool_call = ToolCallMessage(
                    function_name=call["name"],
                    function_arguments=call["arguments"],
                    assert_success=assert_success,
                    with_secret=with_secret,
                )
                await self.toolcall_processor.call_tool(tool_call, tool_index=i)

        await lifecycle.trigger_after_message_generation(
            parsed_answer, full_response, tool_calls
        )

        if self.toolcall_processor.early_return:
            return await self.call_llm(
                self.message_processor.get_messages(), self._queued_messages
            )

        self._current_parsed_answer = None
        return parsed_answer, False

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

    async def check_interrupt(self) -> bool:
        """检查是否需要打断当前回答。

        Returns:
            bool: 如果需要打断则返回True
        """
        if not self.group_chat.is_empty("user_message") and self._current_parsed_answer:
            self._current_parsed_answer.interrupt()
            agent = cast(
                "Agent", self.group_chat.get_member_typechecked("agent", object)
            )
            agent.state = "waiting_user"
            return True
        return False

    def get_current_answer(self) -> Answer | None:
        """获取当前Answer（兼容旧接口）。"""
        if self._current_parsed_answer:
            return self._current_parsed_answer._answer
        return None
