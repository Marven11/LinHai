"""Agent核心模块，负责处理消息、调用工具和管理状态。"""

from datetime import datetime
from typing import (
    Sequence,
)

import asyncio

from .messages import (
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
from linhai.registry import Registry
from linhai.type_hints import AgentState, ThresholdInfo
from linhai.tool.base import (
    ToolArgInfo,
    ToolSet,
    ToolResultSuccess,
)
from linhai.tool.mcp_connector import MCPConnector
from linhai.utils.common import UiNotice
from .user_message_handler import UserMessageHandler
from .command_callback import CommandCallback


class Agent:
    """Agent核心类，负责处理消息流、调用工具和管理状态机。"""

    def __init__(
        self,
        llm_manager: LlmManager,
        compress_threshold: int | float,
        registry: Registry,
        pinned_messages: list[Message],
        max_toolcall_token_in_round: int | float = 0.3,
    ):
        self.llm_manager = llm_manager

        self.compress_threshold = compress_threshold
        self.registry = registry

        registry.register_queue("user_message")
        registry.register_member("agent", self)

        self.mcp_connector: MCPConnector | None = None

        self.state: AgentState = "waiting_user"
        self.sleeping_since: datetime | None = None
        self.sleeping_deadline: datetime | None = None

        self.lifecycle = Lifecycle(registry)
        self.message_processor = AgentMessage(registry, pinned_messages)
        self.orchestration = AgentContextOrchestration(registry, self.message_processor)
        self.toolcall_processor = AgentToolcall(self, max_toolcall_token_in_round)

        self.range_clean_manager = RangeCleanManager(registry)

        self.compress_tool_called_in_last_response = False

        from .answer import AgentLlm

        self.agent_llm = AgentLlm(
            llm_manager=llm_manager,
            registry=registry,
            toolcall_processor=self.toolcall_processor,
            message_processor=self.message_processor,
        )

        self.messages = self.message_processor.get_messages()

        self.user_message_handler = UserMessageHandler(registry)
        command_callback = CommandCallback(registry)
        self.lifecycle.register_after_parsed_user_message(command_callback)
        self.lifecycle.register_after_token_generation(self.after_token_generation)

    def interrupt_to_working(self) -> None:
        """打断当前状态，将Agent切换到working状态。

        用于RSS等异步消息源需要在agent处于sleeping/waiting_user时
        打断agent并让其处理新消息。
        """
        if self.state == "sleeping":
            self.sleeping_since = None
            self.sleeping_deadline = None
        self.state = "working"

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

        token_manager = self.registry.get_member_typechecked(
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
        if self.user_message_handler.has_message():
            should_interrupt = await self.user_message_handler.receive_and_dispatch()
            self.state = "working"
            if should_interrupt and agent.agent_llm:
                await agent.agent_llm.interrupt(
                    "用户发来新的消息打断了你的输出", "Agent已被打断"
                )
                return True
        return False

    async def state_waiting_user(self):
        """
        处理等待用户状态。

        在这个状态下，Agent会等待用户输入消息，然后处理这些消息。
        """
        if self.is_last_message_user():
            self.state = "working"
            return

        await self.lifecycle.trigger_before_waiting_user(self)

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="INFO", content="Agent正在等待用户"),
        )
        while (
            not self.user_message_handler.has_message() and self.state == "waiting_user"
        ):
            await asyncio.sleep(0.01)
        if self.state != "waiting_user":
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(level="INFO", content="Agent在等待用户时被切换状态"),
            )
            return
        await self.user_message_handler.receive_and_dispatch()
        self.state = "working"

        await self.generate_response()

    async def state_sleeping(self):
        """处理睡眠状态。

        在这个状态下，Agent每秒检查是否到达截止时间或有新用户消息，
        满足任一条件则退出sleeping状态。
        """
        assert self.sleeping_since is not None
        assert self.sleeping_deadline is not None

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="INFO", content="Agent开始睡眠"),
        )

        while True:
            if self.state != "sleeping":
                return
            if self.user_message_handler.has_message():
                should_interrupt = (
                    await self.user_message_handler.receive_and_dispatch()
                )
                if should_interrupt:
                    self.sleeping_since = None
                    self.sleeping_deadline = None
                    self.state = "working"
                    return
            now = datetime.now()
            if now >= self.sleeping_deadline:
                break
            remaining = (self.sleeping_deadline - now).total_seconds()
            sleep_time = min(1.0, remaining)
            await asyncio.sleep(sleep_time)

        since = self.sleeping_since
        deadline = self.sleeping_deadline
        elapsed = (datetime.now() - since).total_seconds()

        self.sleeping_since = None
        self.sleeping_deadline = None
        self.state = "working"

        result_msg = f"睡眠完成，从 {since.strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        await self.message_processor.add_new_message(RuntimeMessage(result_msg))

    async def state_working(self):
        await self.generate_response()

    def is_last_message_user(self) -> bool:
        if not self.message_processor.get_messages():
            return False
        msg = self.message_processor.get_messages()[-1]
        from linhai.llm import UserMessage

        return isinstance(msg, UserMessage)

    def get_current_model(self) -> LanguageModel:
        """
        根据当前LLM索引选择合适的模型。

        返回:
            LanguageModel: 选择的语言模型实例
        """
        return self.llm_manager.get_current_llm()

    async def generate_response(self) -> ParsedAnswer:
        """
        生成回复并发送给用户。

        参数:
            enable_compress: 是否启用压缩功能
            disable_waiting_user_warning: 是否禁用等待用户警告

        返回:
            Answer: 生成的回答对象
        """
        await self.message_processor.process_queued_messages()

        if self.message_processor.get_message_count() > 0:
            last_msg = self.message_processor.get_messages()[-1]
            from linhai.llm import AssistantMessage

            if isinstance(last_msg, AssistantMessage):
                empty_user_msg = RuntimeMessage("继续")
                await self.message_processor.add_new_message(empty_user_msg)

        answer, parsed_answer, completed_normally = (
            await self.agent_llm.call_and_wait_llm()
        )
        if not completed_normally:
            return parsed_answer

        from linhai.llm import AssistantMessage

        message = answer.get_message()
        if not isinstance(message, AssistantMessage):
            raise TypeError(f"Expected AssistantMessage, got {type(message).__name__}")
        chat_message: AssistantMessage = message

        from linhai.llm import AssistantMessage

        full_response = chat_message.message
        await self.message_processor.add_new_message(chat_message)

        await self.message_processor.process_queued_messages()

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
            parsed_answer, full_response, tool_calls
        )

        if self.toolcall_processor.early_return:
            return await self.generate_response()

        return parsed_answer

    def get_current_llm_info(self) -> tuple[str, LanguageModel]:
        """获取当前LLM的名称和实例。

        返回:
            tuple[str, LanguageModel]: (LLM名称, LLM实例)
        """
        llm_instance = self.llm_manager.get_current_llm()
        current_llm = self.llm_manager.get_current_llm()
        llm_name = current_llm.get_name()
        return llm_name, llm_instance

    def generate_sleep_toolset(self) -> ToolSet:
        from datetime import timedelta

        agent = self
        sleep_toolset = ToolSet()

        @sleep_toolset.register_tool(
            name="sleep",
            desc="睡眠X秒，返回开始和结束时间",
            args={"seconds": ToolArgInfo(desc="睡眠的秒数", type="float")},
            required_args=["seconds"],
        )
        async def sleep_tool(seconds: float) -> ToolResultSuccess:
            start = datetime.now()
            agent.sleeping_since = start
            agent.sleeping_deadline = start + timedelta(seconds=seconds)
            agent.state = "sleeping"
            return ToolResultSuccess(
                content=f"开始睡眠{seconds}秒，从 {start.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        return sleep_toolset

    async def tick(self):
        while self.user_message_handler.has_message():
            await self.user_message_handler.receive_and_dispatch()
            self.state = "working"
        if self.state == "waiting_user":
            return await self.state_waiting_user()
        elif self.state == "working":
            return await self.state_working()
        elif self.state == "sleeping":
            return await self.state_sleeping()

    async def run(self):
        """
        Agent主循环，负责状态机的管理和状态切换。

        根据当前状态调用相应的状态处理函数，
        并处理异常和取消事件。
        """

        await self.lifecycle.trigger_before_agent_loop(self)

        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                break
            await asyncio.sleep(0)
