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
    [ToolCallMessage], Awaitable[bool]  # tool_call, 返回True表示阻止工具调用
]

AfterToolCallCallback: TypeAlias = Callable[
    [
        "Agent",
        ToolCallMessage,
        Any,
        bool,
    ],  # agent, tool_call, tool_result, success
    Awaitable[None],
]

DuringMessageGenerationCallback: TypeAlias = Callable[
    [Answer, str],  # answer, current_content
    Awaitable[bool],  # 返回True表示中断，False表示继续
]

BeforeUserMessageCallback: TypeAlias = Callable[
    ["Agent"],  # agent
    Awaitable[bool],  # 返回True表示中断消息处理，False表示继续
]

BeforeWaitingUserCallback: TypeAlias = Callable[
    ["Agent"],  # agent
    Awaitable[None],  # 无返回值，仅用于执行前置操作
]

ToolSuccessCallback: TypeAlias = Callable[
    ["Agent", ToolCallMessage, Any],  # agent, tool_call, tool_result
    Awaitable[None],
]

ToolFailureCallback: TypeAlias = Callable[
    ["Agent", ToolCallMessage, Any],  # agent, tool_call, error
    Awaitable[None],
]

ToolParseErrorCallback: TypeAlias = Callable[
    ["Agent", str],  # agent, error_message
    Awaitable[None],
]

ToolConflictCallback: TypeAlias = Callable[
    ["Agent", ToolCallMessage, list[str]],  # agent, tool_call, conflicting_tools
    Awaitable[None],
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
        self._before_waiting_user_callbacks: list[BeforeWaitingUserCallback] = []
        self._tool_success_callbacks: list[ToolSuccessCallback] = []
        self._tool_failure_callbacks: list[ToolFailureCallback] = []
        self._tool_parse_error_callbacks: list[ToolParseErrorCallback] = []
        self._tool_conflict_callbacks: list[ToolConflictCallback] = []

        # 初始化默认插件
        self._plugins = self._register_default_plugins()

    def _register_default_plugins(self):
        """注册默认的Plugin。"""
        from .plugin import (
            WaitingUserPlugin,
            WrongEndPlugin,
            StopFastAgentPlugin,
            WeirdEndOfSentencePlugin,
            BadMultiToolCall,
            EndThinkPlugin,
            PreventToolOutputPlugin,
            SingleToolCallReminderPlugin,
            ClarificationBlockingPlugin,
            SubAgentCollaborationPlugin,
            ClarificationCheckPlugin,
            GitBlockingPlugin,
            ClarificationWaitingUserPlugin,
        )

        plugins = [
            WaitingUserPlugin(self.group_chat),
            WrongEndPlugin(self.group_chat),
            StopFastAgentPlugin(self.group_chat),
            WeirdEndOfSentencePlugin(self.group_chat),
            BadMultiToolCall(self.group_chat),
            EndThinkPlugin(self.group_chat),
            PreventToolOutputPlugin(self.group_chat),
            SingleToolCallReminderPlugin(self.group_chat),
            ClarificationBlockingPlugin(self.group_chat),
            SubAgentCollaborationPlugin(self.group_chat),
            ClarificationCheckPlugin(self.group_chat),
            GitBlockingPlugin(self.group_chat),
            ClarificationWaitingUserPlugin(self.group_chat),
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
