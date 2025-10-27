from typing import (
    Callable,
    Awaitable,
    Any,
    TypeAlias,
)
import logging


from linhai.llm import (
    Answer,
    ToolCallMessage,
)


import linhai

logger = logging.getLogger(__name__)


# 生命周期回调类型定义

BeforeMessageGenerationCallback: TypeAlias = Callable[
    ["linhai.agent.Agent", bool, bool],  # agent, enable_compress, disable_waiting_user_warning
    Awaitable[None],
]

AfterMessageGenerationCallback: TypeAlias = Callable[
    ["linhai.agent.Agent", Answer, str, list[dict]],  # agent, answer, full_response, tool_calls
    Awaitable[None],
]

BeforeToolCallCallback: TypeAlias = Callable[
    ["linhai.agent.Agent", ToolCallMessage], Awaitable[None]  # agent, tool_call
]

AfterToolCallCallback: TypeAlias = Callable[
    ["linhai.agent.Agent", ToolCallMessage, Any, bool],  # agent, tool_call, tool_result, success
    Awaitable[None],
]

DuringMessageGenerationCallback: TypeAlias = Callable[
    ["linhai.agent.Agent", Answer, str],  # agent, answer, current_content
    Awaitable[bool],  # 返回True表示中断，False表示继续
]


class Lifecycle:
    """生命周期回调管理器，使用明确的参数传递。"""

    def __init__(self):
        self._before_message_generation_callbacks: list[
            BeforeMessageGenerationCallback
        ] = []
        self._after_message_generation_callbacks: list[
            AfterMessageGenerationCallback
        ] = []
        self._before_tool_call_callbacks: list[BeforeToolCallCallback] = []
        self._after_tool_call_callbacks: list[AfterToolCallCallback] = []
        self._during_message_generation_callbacks: list[
            DuringMessageGenerationCallback
        ] = []

    def register_before_message_generation(
        self, callback: BeforeMessageGenerationCallback
    ):
        """注册消息生成前的回调。"""
        self._before_message_generation_callbacks.append(callback)

    def register_after_message_generation(
        self, callback: AfterMessageGenerationCallback
    ):
        """注册消息生成后的回调。"""
        self._after_message_generation_callbacks.append(callback)

    def register_before_tool_call(self, callback: BeforeToolCallCallback):
        """注册工具调用前的回调。"""
        self._before_tool_call_callbacks.append(callback)

    def register_after_tool_call(self, callback: AfterToolCallCallback):
        """注册工具调用后的回调。"""
        self._after_tool_call_callbacks.append(callback)

    def register_during_message_generation(
        self, callback: DuringMessageGenerationCallback
    ):
        """注册消息生成中的回调。"""
        self._during_message_generation_callbacks.append(callback)

    async def trigger_during_message_generation(
        self, agent: "linhai.agent.Agent", answer: Answer, current_content: str
    ) -> bool:
        """触发消息生成中的事件。"""
        should_interrupt = False
        for callback in self._during_message_generation_callbacks:
            try:
                result = await callback(agent, answer, current_content)
                if result:
                    should_interrupt = True
            except Exception as e:
                logger.error("During message generation callback error: %s", e)
        return should_interrupt

    async def trigger_before_message_generation(
        self, agent: "linhai.agent.Agent", enable_compress: bool, disable_waiting_user_warning: bool
    ):
        """触发消息生成前的事件。"""
        for callback in self._before_message_generation_callbacks:
            try:
                await callback(agent, enable_compress, disable_waiting_user_warning)
            except Exception as e:
                logger.error("Before message generation callback error: %s", e)

    async def trigger_after_message_generation(
        self, agent: "linhai.agent.Agent", answer: Answer, full_response: str, tool_calls: list[dict]
    ):
        """触发消息生成后的事件。"""
        for callback in self._after_message_generation_callbacks:
            try:
                await callback(agent, answer, full_response, tool_calls)
            except Exception as e:
                logger.error("After message generation callback error: %s", e)

    async def trigger_before_tool_call(
        self, agent: "linhai.agent.Agent", tool_call: ToolCallMessage
    ):
        """触发工具调用前的事件。"""
        for callback in self._before_tool_call_callbacks:
            try:
                await callback(agent, tool_call)
            except Exception as e:
                logger.error("Before tool call callback error: %s", e)

    async def trigger_after_tool_call(
        self,
        agent: "linhai.agent.Agent",
        tool_call: ToolCallMessage,
        tool_result: Any,
        success: bool,
    ):
        """触发工具调用后的事件。"""
        for callback in self._after_tool_call_callbacks:
            try:
                await callback(agent, tool_call, tool_result, success)
            except Exception as e:
                logger.error("After tool call callback error: %s", e)
