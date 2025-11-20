"""Agent lifecycle management module for handling callback events during agent execution."""

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

logger = logging.getLogger(__name__)


# 生命周期回调类型定义

BeforeMessageGenerationCallback: TypeAlias = Callable[
    [
        bool,
        bool,
    ],  # enable_compress, disable_waiting_user_warning
    Awaitable[None],
]

AfterMessageGenerationCallback: TypeAlias = Callable[
    [
        Answer,
        str,
        list[dict],
    ],  # answer, full_response, tool_calls
    Awaitable[None],
]

BeforeToolCallCallback: TypeAlias = Callable[
    [ToolCallMessage], Awaitable[None]  # tool_call
]

AfterToolCallCallback: TypeAlias = Callable[
    [
        ToolCallMessage,
        Any,
        bool,
    ],  # tool_call, tool_result, success
    Awaitable[None],
]

DuringMessageGenerationCallback: TypeAlias = Callable[
    [Answer, str],  # answer, current_content
    Awaitable[bool],  # 返回True表示中断，False表示继续
]


class Lifecycle:
    """生命周期回调管理器，使用明确的参数传递。"""

    def __init__(self, group_chat):
        self.group_chat = group_chat
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

        # 初始化默认插件
        self._plugins = self._register_default_plugins()

    def _register_default_plugins(self):
        """注册默认的Plugin。"""
        from .plugin import (
            WaitingUserPlugin,
            WrongEndPlugin,
            WeirdEndOfSentencePlugin,
            BadMultiToolCall,
            MarkdownSyntaxPlugin,
            EndThinkPlugin,
            PreventToolOutputPlugin,
            SingleToolCallReminderPlugin,
        )

        plugins = [
            WaitingUserPlugin(self.group_chat),
            WrongEndPlugin(self.group_chat),
            WeirdEndOfSentencePlugin(self.group_chat),
            BadMultiToolCall(self.group_chat),
            MarkdownSyntaxPlugin(self.group_chat),
            EndThinkPlugin(self.group_chat),
            PreventToolOutputPlugin(self.group_chat),
            SingleToolCallReminderPlugin(self.group_chat),
        ]

        for plugin in plugins:
            plugin.register(self)

        return plugins

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
        self, answer: Answer, current_content: str
    ) -> bool:
        """触发消息生成中的事件。"""
        should_interrupt = False
        for callback in self._during_message_generation_callbacks:
            result = await callback(answer, current_content)
            if result:
                should_interrupt = True
                break

        return should_interrupt

    async def trigger_before_message_generation(
        self,
        enable_compress: bool,
        disable_waiting_user_warning: bool,
    ):
        """触发消息生成前的事件。"""
        for callback in self._before_message_generation_callbacks:
            await callback(enable_compress, disable_waiting_user_warning)

    async def trigger_after_message_generation(
        self,
        answer: Answer,
        full_response: str,
        tool_calls: list[dict],
    ):
        """触发消息生成后的事件。"""
        for callback in self._after_message_generation_callbacks:
            await callback(answer, full_response, tool_calls)

    async def trigger_before_tool_call(self, tool_call: ToolCallMessage):
        """触发工具调用前的事件。"""
        for callback in self._before_tool_call_callbacks:
            await callback(tool_call)

    async def trigger_after_tool_call(
        self,
        tool_call: ToolCallMessage,
        tool_result: Any,
        success: bool,
    ):
        """触发工具调用后的事件。"""
        for callback in self._after_tool_call_callbacks:
            await callback(tool_call, tool_result, success)
