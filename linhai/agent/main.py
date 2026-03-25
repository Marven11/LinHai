"""Agent核心模块，负责处理消息、调用工具和管理状态。"""

from typing import (
    cast,
    Sequence,
)

import asyncio

from .base import (
    RuntimeMessage,
)
from linhai.parsed_message import ParsedAnswer
from .workflow import RangeCleanManager
from .lifecycle import Lifecycle
from .message import AgentMessage
from .orchestration import AgentContextOrchestration
from .toolcall import AgentToolcall
from linhai.markdown_parser import extract_tool_calls_with_errors
from linhai.llm import (
    Message,
    LanguageModel,
    Answer,
    OpenAiAnswer,
    ToolCallMessage,
)
from linhai.llm_manager import LlmManager
from linhai.group_chat import GroupChat
from linhai.type_hints import AgentState, ThresholdInfo
from linhai.tool.mcp_connector import MCPConnector
from linhai.utils import CliRuntimeNotice
from linhai.input_parser import parse_user_input


class Agent:
    """Agent核心类，负责处理消息流、调用工具和管理状态机。"""

    def __init__(
        self,
        llm_manager: LlmManager,
        compress_threshold: int | float,
        group_chat: GroupChat,
        pinned_messages: list[Message],
        max_toolcall_token_in_round: int = 30000,
    ):
        self.llm_manager = llm_manager

        self.compress_threshold = compress_threshold
        self.group_chat = group_chat

        group_chat.register_queue("user_message")
        group_chat.register_member("agent", self)

        self.mcp_connector: MCPConnector | None = None

        self.state: AgentState = "waiting_user"

        self.lifecycle = Lifecycle(group_chat)
        self.message_processor = AgentMessage(group_chat, pinned_messages)
        self.orchestration = AgentContextOrchestration(
            group_chat, self.message_processor
        )
        self.toolcall_processor = AgentToolcall(self, max_toolcall_token_in_round)

        self.range_clean_manager = RangeCleanManager(group_chat)

        self.compress_tool_called_in_last_response = False

        self.current_answer: Answer | None = None

        from .answer import AgentLlm

        self.agent_llm = AgentLlm(
            llm_manager=llm_manager,
            group_chat=group_chat,
            agent=self,
            toolcall_processor=self.toolcall_processor,
            message_processor=self.message_processor,
        )

        self.messages = self.message_processor.get_messages()

        self.queued_messages: list = []

        self.lifecycle.register_after_token_generation(self.after_token_generation)

    def get_threshold_info(self) -> ThresholdInfo | None:
        """获取阈值信息。

        返回:
            ThresholdInfo | None: 阈值信息字典，包含以下字段：
                hard_limit: 压缩阈值
                used_tokens: 已使用token数
                remaining_tokens: 剩余token数
                usage_ratio: 使用比例
        """
        from ..token_manager import TokenManager

        token_manager = self.group_chat.get_member_typechecked(
            "token_manager", TokenManager
        )
        if token_manager.current_token_usage is None:
            return None

        current_llm = self.llm_manager.get_current_llm()
        token_limit = current_llm.get_token_limit()

        if token_limit is None:
            token_limit = 65536

        threshold_config = self.compress_threshold
        hard_limit = (
            int(threshold_config * token_limit)
            if isinstance(threshold_config, float)
            else threshold_config
        )

        used_tokens = token_manager.current_token_usage.total_tokens
        usage_ratio = min(used_tokens / hard_limit, 1.0) if hard_limit > 0 else 0.0
        remaining_tokens = max(hard_limit - used_tokens, 0)

        return {
            "hard_limit": hard_limit,
            "used_tokens": used_tokens,
            "remaining_tokens": remaining_tokens,
            "usage_ratio": usage_ratio,
        }

    async def after_token_generation(
        self, agent: "Agent", answer, current_content
    ) -> bool:
        """after_token_generation回调，检查是否有用户消息需要打断当前回答。"""
        if not agent.group_chat.is_empty("user_message") and agent.current_answer:
            agent.current_answer.interrupt()
            return True
        return False

    async def receive_one_user_message(self):
        msg = await self.group_chat.receive("user_message")
        from linhai.llm import UserMessage

        assert isinstance(msg, UserMessage)
        await self.handle_user_message(msg)
        self.state = "working"
        return msg

    async def state_waiting_user(self):
        """
        处理等待用户状态。

        在这个状态下，Agent会等待用户输入消息，然后处理这些消息。
        """
        if self.is_last_message_user():
            self.state = "working"
            return

        await self.lifecycle.trigger_before_waiting_user(self)

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(level="INFO", content="Agent正在等待用户"),
        )
        while self.group_chat.is_empty("user_message") and self.state == "waiting_user":
            await asyncio.sleep(0.01)
        if self.state != "waiting_user":
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(level="INFO", content="Agent在等待用户时被切换状态"),
            )
            return
        await self.receive_one_user_message()

        await self.generate_response()

    async def state_working(self):
        """
        处理自动运行状态。

        在这个状态下，Agent会自动处理消息并生成响应，
        同时监控token使用量并在需要时触发压缩。
        """

        if not self.group_chat.is_empty("user_message"):
            try:
                await self.receive_one_user_message()
                await self.generate_response()
            except RuntimeError as e:
                raise RuntimeError("处理消息时出错") from e
        else:
            await self.generate_response()

    def is_last_message_user(self) -> bool:
        if not self.message_processor.get_messages():
            return False
        msg = self.message_processor.get_messages()[-1]
        from linhai.llm import UserMessage

        return isinstance(msg, UserMessage)

    async def handle_user_message(self, msg: "Message"):
        """处理并加入用户的消息，首先尝试通过CommandHandler处理命令"""
        from linhai.llm import UserMessage

        assert isinstance(msg, UserMessage)

        content = msg.message.strip()

        from linhai.cli.command_handler import CommandHandler

        handler = CommandHandler(self.group_chat)
        handled = await handler.handle_command(content)

        if not handled:
            await self.message_processor.add_new_message(msg)

    def get_current_model(self) -> LanguageModel:
        """
        根据当前LLM索引选择合适的模型。

        返回:
            LanguageModel: 选择的语言模型实例
        """
        return self.llm_manager.get_current_llm()

    async def generate_response(self) -> Answer:
        """
        生成回复并发送给用户。

        参数:
            enable_compress: 是否启用压缩功能
            disable_waiting_user_warning: 是否禁用等待用户警告

        返回:
            Answer: 生成的回答对象
        """
        if self.queued_messages:
            await self.group_chat.send_if_exists(
                "ui_log", CliRuntimeNotice(level="INFO", content="排队消息被处理")
            )
            await self.message_processor.add_new_message(
                RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理：")
            )
            for msg in self.queued_messages:
                await self.message_processor.add_new_message(msg)
            self.queued_messages = []

        if self.message_processor.get_message_count() > 0:
            last_msg = self.message_processor.get_messages()[-1]
            from linhai.llm import AssistantMessage

            if isinstance(last_msg, AssistantMessage):
                empty_user_msg = RuntimeMessage("继续")
                await self.message_processor.add_new_message(empty_user_msg)

        await self.lifecycle.trigger_before_message_generation()

        answer: Answer = await self.llm_manager.answer_stream(
            self.message_processor.get_messages()
        )

        self.current_answer = answer

        parsed_answer = ParsedAnswer(answer, self.lifecycle, agent=self)
        await parsed_answer.start_parsing()
        await self.lifecycle.trigger_after_new_parsed_answer(parsed_answer)
        await self.group_chat.send("parsed_agent_answer", parsed_answer)

        completed_normally = await parsed_answer.wait_parsing()
        if not completed_normally:
            return answer

        from linhai.llm import AssistantMessage

        chat_message = cast(AssistantMessage, answer.get_message())

        from linhai.llm import AssistantMessage

        chat_message = cast(AssistantMessage, answer.get_message())
        full_response = chat_message.message
        await self.message_processor.add_new_message(chat_message)

        if self.queued_messages:
            await self.group_chat.send_if_exists(
                "ui_log", CliRuntimeNotice(level="INFO", content="排队消息被处理")
            )
            await self.message_processor.add_new_message(
                RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理：")
            )
            for msg in self.queued_messages:
                await self.message_processor.add_new_message(msg)
            self.queued_messages = []

        tool_calls, errors = extract_tool_calls_with_errors(full_response)

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

        await self.lifecycle.trigger_after_message_generation(
            answer, full_response, tool_calls
        )

        if self.toolcall_processor.early_return:
            return await self.generate_response()

        self.current_answer = None
        return answer

    def get_current_llm_info(self) -> tuple[str, LanguageModel]:
        """获取当前LLM的名称和实例。

        返回:
            tuple[str, LanguageModel]: (LLM名称, LLM实例)
        """
        llm_instance = self.llm_manager.get_current_llm()
        current_llm = self.llm_manager.get_current_llm()
        llm_name = current_llm.get_name()
        return llm_name, llm_instance

    async def run(self):
        """
        Agent主循环，负责状态机的管理和状态切换。

        根据当前状态调用相应的状态处理函数，
        并处理异常和取消事件。
        """

        user_input_found = False
        await self.toolcall_processor.ensure_mcp_connector()
        await self.lifecycle.trigger_before_agent_loop(self)

        while not self.group_chat.is_empty("user_message"):
            await self.receive_one_user_message()
            user_input_found = True
        if user_input_found:
            await self.generate_response()

        while True:
            try:
                if self.state == "waiting_user":
                    await self.state_waiting_user()
                elif self.state == "working":
                    await self.state_working()
                else:

                    break

            except asyncio.CancelledError:
                break
            await asyncio.sleep(0)
