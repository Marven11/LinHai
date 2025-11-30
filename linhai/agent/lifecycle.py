"""Agent lifecycle management module for handling callback events during agent execution."""

from typing import (
    Callable,
    Awaitable,
    Any,
    TypeAlias,
)
import logging
import typing

from linhai.llm import (
    Answer,
    ToolCallMessage,
)

if typing.TYPE_CHECKING:
    from linhai.agent import Agent

logger = logging.getLogger(__name__)


# 生命周期回调类型定义

BeforeMessageGenerationCallback: TypeAlias = Callable[
    [
        bool,
        bool,
    ],
    Awaitable[None],
]

AfterMessageGenerationCallback: TypeAlias = Callable[
    [
        Answer,
        str,
        list[dict],
    ],
    Awaitable[None],
]

BeforeToolCallCallback: TypeAlias = Callable[[ToolCallMessage], Awaitable[bool]]

AfterToolCallCallback: TypeAlias = Callable[
    [
        "Agent",
        ToolCallMessage,
        Any,
        bool,
    ],
    Awaitable[None],
]

DuringMessageGenerationCallback: TypeAlias = Callable[
    [Answer, str],
    Awaitable[bool],
]

BeforeUserMessageCallback: TypeAlias = Callable[
    ["Agent"],
    Awaitable[bool],
]

BeforeWaitingUserCallback: TypeAlias = Callable[
    ["Agent"],
    Awaitable[None],
]

ToolSuccessCallback: TypeAlias = Callable[
    ["Agent", ToolCallMessage, Any],
    Awaitable[None],
]

ToolFailureCallback: TypeAlias = Callable[
    ["Agent", ToolCallMessage, Any],
    Awaitable[None],
]

ToolParseErrorCallback: TypeAlias = Callable[
    ["Agent", str],
    Awaitable[None],
]

ToolConflictCallback: TypeAlias = Callable[
    ["Agent", ToolCallMessage, list[str]],
    Awaitable[None],
]


class Lifecycle:
    """生命周期回调管理器，使用明确的参数传递。"""

    def __init__(self, group_chat):
        self.group_chat = group_chat
        # 在初始化时注册自己到group_chat
        self.group_chat.register_member("lifecycle", self)

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
        self._before_waiting_user_callbacks: list[BeforeWaitingUserCallback] = []
        self._tool_success_callbacks: list[ToolSuccessCallback] = []
        self._tool_failure_callbacks: list[ToolFailureCallback] = []
        self._tool_parse_error_callbacks: list[ToolParseErrorCallback] = []
        self._tool_conflict_callbacks: list[ToolConflictCallback] = []

        self._plugins = self._register_default_plugins()

    def _register_default_plugins(self):
        """注册默认的Plugin。"""
        from .plugin import (
            WaitingUserPlugin,
            WrongEndPlugin,
            PromptFastAgentPlugin,
            WeirdTokenPlugin,
            BadMultiToolCall,
            EndThinkPlugin,
            ToolCallInReasoningPlugin,
            PreventToolOutputPlugin,
            SingleToolCallReminderPlugin,
            ClarificationCheckPlugin,
            JsonCodeBlockPlugin,
        )

        plugins = [
            WaitingUserPlugin(self.group_chat),
            WrongEndPlugin(self.group_chat),
            PromptFastAgentPlugin(self.group_chat),
            WeirdTokenPlugin(self.group_chat),
            BadMultiToolCall(self.group_chat),
            EndThinkPlugin(self.group_chat),
            ToolCallInReasoningPlugin(self.group_chat),
            PreventToolOutputPlugin(self.group_chat),
            SingleToolCallReminderPlugin(self.group_chat),
            ClarificationCheckPlugin(self.group_chat),
            JsonCodeBlockPlugin(self.group_chat),
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

    def register_before_waiting_user(self, callback: BeforeWaitingUserCallback):
        """注册等待用户前的回调。"""
        self._before_waiting_user_callbacks.append(callback)

    def register_tool_success(self, callback: ToolSuccessCallback):
        """注册工具成功回调。"""
        self._tool_success_callbacks.append(callback)

    def register_tool_failure(self, callback: ToolFailureCallback):
        """注册工具失败回调。"""
        self._tool_failure_callbacks.append(callback)

    def register_tool_parse_error(self, callback: ToolParseErrorCallback):
        """注册工具解析错误回调。"""
        self._tool_parse_error_callbacks.append(callback)

    def register_tool_conflict(self, callback: ToolConflictCallback):
        """注册工具冲突回调。"""
        self._tool_conflict_callbacks.append(callback)

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

    async def trigger_before_tool_call(self, tool_call: ToolCallMessage) -> bool:
        """触发工具调用前的事件。"""
        should_block = False
        for callback in self._before_tool_call_callbacks:
            result = await callback(tool_call)
            if result:
                should_block = True
        return should_block

    async def trigger_after_tool_call(
        self,
        agent: "Agent",
        tool_call: ToolCallMessage,
        tool_result: Any,
        success: bool,
    ):
        """触发工具调用后的事件。"""
        for callback in self._after_tool_call_callbacks:
            await callback(agent, tool_call, tool_result, success)

    async def trigger_before_waiting_user(self, agent: "Agent"):
        """触发等待用户前的事件。"""
        for callback in self._before_waiting_user_callbacks:
            await callback(agent)

    async def trigger_tool_success(
        self, agent: "Agent", tool_call: ToolCallMessage, tool_result: Any
    ):
        """触发工具成功事件。"""
        for callback in self._tool_success_callbacks:
            await callback(agent, tool_call, tool_result)

    async def trigger_tool_failure(
        self, agent: "Agent", tool_call: ToolCallMessage, error: Any
    ):
        """触发工具失败事件。"""
        for callback in self._tool_failure_callbacks:
            await callback(agent, tool_call, error)

    async def trigger_tool_parse_error(self, agent: "Agent", error_message: str):
        """触发工具解析错误事件。"""
        for callback in self._tool_parse_error_callbacks:
            await callback(agent, error_message)

    async def trigger_tool_conflict(
        self, agent: "Agent", tool_call: ToolCallMessage, conflicting_tools: list[str]
    ):
        """触发工具冲突事件。"""
        for callback in self._tool_conflict_callbacks:
            await callback(agent, tool_call, conflicting_tools)
