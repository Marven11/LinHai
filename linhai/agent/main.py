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
from linhai.base import Message, LanguageModel, Answer, ToolCallMessage
from linhai.llm import OpenAiAnswer
from linhai.llm_manager import LlmManager
from linhai.registry import Registry
from linhai.type_hints import ThresholdInfo
from linhai.tool.mcp_connector import MCPConnector
from linhai.utils.common import UiNotice
from .user_message_handler import UserMessageHandler
from .command_callback import CommandCallback
from .state_machine import AgentStateMachine


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

        self.state_machine = AgentStateMachine(registry)

        self.lifecycle = Lifecycle(registry)

        self.message_processor = AgentMessage(registry, pinned_messages)
        self.orchestration = AgentContextOrchestration(registry, self.message_processor)
        self.toolcall_processor = AgentToolcall(registry, max_toolcall_token_in_round)

        self.range_clean_manager = RangeCleanManager(registry)

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
        self.lifecycle.after_parsed_user_message.register(command_callback)
        self.lifecycle.after_token_generation.register(self.after_token_generation)
        self.lifecycle.on_llm_error.register(self._on_llm_error)

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

        llm_threshold = current_llm.get_compress_threshold()
        if llm_threshold is not None:
            threshold_config = llm_threshold
        else:
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

    async def _on_llm_error(
        self, llm_name: str, error: Exception, retry_count: int
    ) -> None:
        if self.user_message_handler.has_message():
            await self.user_message_handler.receive_and_dispatch()

    async def after_token_generation(
        self, agent: "Agent", answer, current_content
    ) -> bool:
        """after_token_generation回调，检查是否有用户消息需要打断当前回答。"""
        if self.user_message_handler.has_message():
            should_interrupt = await self.user_message_handler.receive_and_dispatch()
            self.state_machine.transition_to_working()
            if should_interrupt and agent.agent_llm:
                await agent.agent_llm.interrupt(
                    "用户发来新的消息打断了你的输出", "Agent已被打断"
                )
                return True
        return False

    async def state_waiting_user(self):
        """处理等待用户状态。"""
        if self.is_last_message_user():
            self.state_machine.transition_to_working()
            return

        await self.lifecycle.before_waiting_user.trigger(self)

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="INFO", content="Agent正在等待用户"),
        )
        while (
            not self.user_message_handler.has_message()
            and self.state_machine.state == "waiting_user"
        ):
            await asyncio.sleep(0.01)
        if self.state_machine.state != "waiting_user":
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(level="INFO", content="Agent在等待用户时被切换状态"),
            )
            return
        await self.user_message_handler.receive_and_dispatch()
        self.state_machine.transition_to_working()

        await self.generate_response()

    async def state_sleeping(self):
        """处理睡眠状态。"""
        assert self.state_machine.sleeping_since is not None
        assert self.state_machine.sleeping_deadline is not None

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="INFO", content="Agent开始睡眠"),
        )

        while True:
            if self.state_machine.state != "sleeping":
                return
            if self.user_message_handler.has_message():
                should_interrupt = (
                    await self.user_message_handler.receive_and_dispatch()
                )
                if should_interrupt:
                    self.state_machine.finish_sleeping()
                    return
            now = datetime.now()
            if now >= self.state_machine.sleeping_deadline:
                break
            remaining = (self.state_machine.sleeping_deadline - now).total_seconds()
            sleep_time = min(1.0, remaining)
            await asyncio.sleep(sleep_time)

        since = self.state_machine.sleeping_since
        elapsed = (datetime.now() - since).total_seconds()

        self.state_machine.finish_sleeping()

        result_msg = f"睡眠完成，从 {since.strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        await self.message_processor.add_new_message(RuntimeMessage(result_msg))

    async def state_working(self):
        await self.generate_response()

    def is_last_message_user(self) -> bool:
        if not self.message_processor.get_messages():
            return False
        msg = self.message_processor.get_messages()[-1]
        from linhai.base import UserMessage

        return isinstance(msg, UserMessage)

    def get_current_model(self) -> LanguageModel:
        return self.llm_manager.get_current_llm()

    async def generate_response(self) -> ParsedAnswer:
        await self.message_processor.process_queued_messages()

        if self.message_processor.get_message_count() > 0:
            last_msg = self.message_processor.get_messages()[-1]
            from linhai.base import AssistantMessage

            if isinstance(last_msg, AssistantMessage):
                empty_user_msg = RuntimeMessage("继续")
                await self.message_processor.add_new_message(empty_user_msg)

        _, parsed_answer, completed_normally = await self.agent_llm.call_and_wait_llm()
        if not completed_normally:
            return parsed_answer

        message = parsed_answer.get_message()
        await self.message_processor.add_new_message(message)

        current_llm = self.llm_manager.get_current_llm()
        if not current_llm.get_custom_toolcall_format():
            openai_toolcalls = parsed_answer.get_openai_toolcalls()
            if openai_toolcalls:
                self.toolcall_processor.start_new_tool_call_round()
                await self.toolcall_processor.call_openai_tools(openai_toolcalls)
            await self.lifecycle.after_message_generation.trigger(parsed_answer, [])
        else:
            tool_calls, errors = parsed_answer.extract_tool_calls_with_errors()

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

            await self.lifecycle.after_message_generation.trigger(
                parsed_answer, tool_calls
            )

        if self.toolcall_processor.early_return:
            return await self.generate_response()

        return parsed_answer

    def get_current_llm_info(
        self, rotate_invalid_llm: bool = True
    ) -> tuple[str, LanguageModel]:
        llm_instance = self.llm_manager.get_current_llm(
            rotate_invalid_llm=rotate_invalid_llm
        )
        current_llm = self.llm_manager.get_current_llm(
            rotate_invalid_llm=rotate_invalid_llm
        )
        llm_name = current_llm.get_name()
        return llm_name, llm_instance

    async def tick(self):
        while self.user_message_handler.has_message():
            await self.user_message_handler.receive_and_dispatch()
            self.state_machine.transition_to_working()
        if self.state_machine.state == "waiting_user":
            return await self.state_waiting_user()
        elif self.state_machine.state == "working":
            return await self.state_working()
        elif self.state_machine.state == "sleeping":
            return await self.state_sleeping()

    async def run(self):
        """Agent主循环，负责状态机的管理和状态切换。"""
        await self.lifecycle.before_agent_loop.trigger(self)

        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                break
            await asyncio.to_thread(self.message_processor._save_context)
            await asyncio.sleep(0)

    def serialize(self) -> dict:
        return {}

    def restore_from(self, data: dict) -> None:
        pass
