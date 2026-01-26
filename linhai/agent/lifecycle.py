"""Agent lifecycle management module for handling callback events during agent execution."""

from typing import (
    Callable,
    Awaitable,
    TypeAlias,
    Literal,
    Union,
    TYPE_CHECKING,
)
from linhai.agent.base import RuntimeMessage


if TYPE_CHECKING:
    from linhai.agent.main import Agent
    from linhai.parsed_message import ParsedAnswer, Segment

from linhai.llm import (
    Answer,
)


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

OnToolResultCallback: TypeAlias = Callable[
    [
        str,
        int,
        Literal["skipped", "success", "failed"],
        str | None,
        dict | None,
        list[str] | None,
        bool,
    ],
    Awaitable[Union[None, bool, "RuntimeMessage"]],
]

AfterTokenGenerationCallback: TypeAlias = Callable[
    ["Agent", Answer, str],
    Awaitable[bool],
]

BeforeParsingCallback: TypeAlias = Callable[
    ["ParsedAnswer"],
    Awaitable[None],
]

AfterSegmentCallback: TypeAlias = Callable[
    ["ParsedAnswer", "Segment"],
    Awaitable[None],
]

AfterParsingCallback: TypeAlias = Callable[
    ["ParsedAnswer"],
    Awaitable[None],
]

ParsingErrorCallback: TypeAlias = Callable[
    ["ParsedAnswer", Exception],
    Awaitable[None],
]

BeforeWaitingUserCallback: TypeAlias = Callable[
    ["Agent"],
    Awaitable[None],
]

BeforeAgentLoopCallback: TypeAlias = Callable[["Agent"], Awaitable[None]]


class Lifecycle:
    """生命周期回调管理器，使用明确的参数传递。"""

    def __init__(self, group_chat):
        self.group_chat = group_chat
        self.group_chat.register_member("lifecycle", self)

        self._before_message_generation_callbacks: list[
            BeforeMessageGenerationCallback
        ] = []
        self._after_message_generation_callbacks: list[
            AfterMessageGenerationCallback
        ] = []
        self._on_tool_result_callbacks: list[OnToolResultCallback] = []
        self._after_token_generation_callbacks: list[AfterTokenGenerationCallback] = []
        self._before_parsing_callbacks: list[BeforeParsingCallback] = []
        self._after_segment_callbacks: list[AfterSegmentCallback] = []
        self._after_parsing_callbacks: list[AfterParsingCallback] = []
        self._parsing_error_callbacks: list[ParsingErrorCallback] = []
        self._before_waiting_user_callbacks: list[BeforeWaitingUserCallback] = []
        self._before_agent_loop_callbacks: list[BeforeAgentLoopCallback] = []

        self._plugins = self._register_default_plugins()

    def _register_default_plugins(self):
        """注册默认的Plugin。"""
        from .plugin import (
            WaitingUserPlugin,
            WrongEndPlugin,
            PromptFastAgentPlugin,
            SlowStartPlugin,
            WeirdTokenPlugin,
            EndThinkPlugin,
            OnlyReasoningPlugin,
            ToolCallInReasoningPlugin,
            SingleToolCallReminderPlugin,
            JsonCodeBlockPlugin,
            RuntimeImitationPlugin,
            UnnecessarySedReadPlugin,
            UnnecessaryRunCommandPlugin,
            FileReadWriteConflictPlugin,
        )
        from .orchestration import RedStateToolBlockPlugin, AppendingMessagePlugin

        plugins = [
            WaitingUserPlugin(self.group_chat),
            WrongEndPlugin(self.group_chat),
            PromptFastAgentPlugin(self.group_chat),
            SlowStartPlugin(self.group_chat),
            WeirdTokenPlugin(self.group_chat),
            EndThinkPlugin(self.group_chat),
            OnlyReasoningPlugin(self.group_chat),
            # 不兼容deepseek api，可能因为最后一个消息是assistant消息
            # PreviousReasoningPlugin(self.group_chat),
            ToolCallInReasoningPlugin(self.group_chat),
            SingleToolCallReminderPlugin(self.group_chat),
            JsonCodeBlockPlugin(self.group_chat),
            RuntimeImitationPlugin(self.group_chat),
            # 貌似会影响模型性能，我们可能不需要这么严格的上下文控制
            # DuplicateFileReadPlugin(self.group_chat),
            UnnecessarySedReadPlugin(self.group_chat),
            UnnecessaryRunCommandPlugin(self.group_chat),
            RedStateToolBlockPlugin(self.group_chat),
            AppendingMessagePlugin(self.group_chat),
            FileReadWriteConflictPlugin(self.group_chat),
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

    def register_on_tool_result(self, callback: OnToolResultCallback):
        """注册工具结果回调。"""
        self._on_tool_result_callbacks.append(callback)

    def register_after_token_generation(self, callback: AfterTokenGenerationCallback):
        """注册token生成后的回调。"""
        self._after_token_generation_callbacks.append(callback)

    def register_before_waiting_user(self, callback: BeforeWaitingUserCallback):
        """注册等待用户前的回调。"""
        self._before_waiting_user_callbacks.append(callback)

    def register_before_parsing(self, callback: BeforeParsingCallback):
        """注册解析开始前的回调。"""
        self._before_parsing_callbacks.append(callback)

    def register_after_segment(self, callback: AfterSegmentCallback):
        """注册segment生成后的回调。"""
        self._after_segment_callbacks.append(callback)

    def register_after_parsing(self, callback: AfterParsingCallback):
        """注册解析完成后的回调。"""
        self._after_parsing_callbacks.append(callback)

    def register_parsing_error(self, callback: ParsingErrorCallback):
        """注册解析错误的回调。"""
        self._parsing_error_callbacks.append(callback)

    def register_before_agent_loop(self, callback: BeforeAgentLoopCallback):
        """注册Agent循环开始前的回调。"""
        self._before_agent_loop_callbacks.append(callback)

    async def trigger_after_token_generation(
        self, agent: "Agent", answer: Answer, current_content: str
    ) -> bool:
        """触发token生成后的事件。"""
        should_interrupt = False
        for callback in self._after_token_generation_callbacks:
            result = await callback(agent, answer, current_content)
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

    async def trigger_on_tool_result(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        result_content: str | None,
        toolcall_arguments: dict | None,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, "RuntimeMessage"]:
        """触发工具结果事件。

        返回:
            None: 没有特殊处理
            bool: 仅当status为"skipped"时有效，True表示跳过工具调用
            RuntimeMessage: 替换工具结果
        """
        for callback in self._on_tool_result_callbacks:
            result = await callback(
                tool_name,
                tool_index,
                status,
                result_content,
                toolcall_arguments,
                with_secret,
                is_tool_failed_duplicated_error,
            )
            if result is not None:
                return result
        return None

    async def trigger_before_waiting_user(self, agent: "Agent"):
        """触发等待用户前的事件。"""
        for callback in self._before_waiting_user_callbacks:
            await callback(agent)

    async def trigger_before_parsing(self, parsed_answer: "ParsedAnswer"):
        """触发解析开始前的事件。"""
        for callback in self._before_parsing_callbacks:
            await callback(parsed_answer)

    async def trigger_after_segment(
        self, parsed_answer: "ParsedAnswer", segment: "Segment"
    ):
        """触发segment生成后的事件。"""
        for callback in self._after_segment_callbacks:
            await callback(parsed_answer, segment)

    async def trigger_after_parsing(self, parsed_answer: "ParsedAnswer"):
        """触发解析完成后的事件。"""
        for callback in self._after_parsing_callbacks:
            await callback(parsed_answer)

    async def trigger_parsing_error(
        self, parsed_answer: "ParsedAnswer", error: Exception
    ):
        """触发解析错误事件。"""
        for callback in self._parsing_error_callbacks:
            await callback(parsed_answer, error)

    async def trigger_before_agent_loop(self, agent: "Agent"):
        """触发Agent循环开始前事件。"""
        for callback in self._before_agent_loop_callbacks:
            await callback(agent)
