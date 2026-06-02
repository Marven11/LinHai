from dataclasses import dataclass, field
from typing import (
    Callable,
    Awaitable,
    List,
    TypeAlias,
    Literal,
    Union,
    TYPE_CHECKING,
)
from linhai.base import Answer, Message
from linhai.type_hints import WithSecret

if TYPE_CHECKING:
    from linhai.agent.messages import RuntimeMessage
    from linhai.base import LanguageModel
from linhai.tool.base import SuccessfulToolResult, FailedToolResult
from linhai.agent.callback_slot import (
    BroadcastSlot,
    ShortCircuitSlot,
    InterruptSlot,
    ChainSlot,
    AfterToolcallSlot,
)

if TYPE_CHECKING:
    from linhai.agent.main import Agent
    from linhai.parsed_message import ParsedAnswer, Segment as Segment
    from linhai.agent.user_message_handler import ParsedUserMessage
    from linhai.machine_control.process import ProcessCreateInfo


@dataclass
class AfterToolcallResult:
    replacement: Message | None = None
    warnings: list["RuntimeMessage"] = field(default_factory=list)
    user_notices: list[str] = field(default_factory=list)


BeforeMessageGenerationCallback: TypeAlias = Callable[[], Awaitable[None]]

AfterMessageGenerationCallback: TypeAlias = Callable[
    ["ParsedAnswer", list[dict]],
    Awaitable[None],
]

AfterToolcallCallback: TypeAlias = Callable[
    [
        str,
        int,
        Literal["skipped", "success", "failed"],
        Message | None,
        dict,
        WithSecret | None,
        bool,
    ],
    Awaitable[Union[None, AfterToolcallResult]],
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

AfterSegmentUpdateCallback: TypeAlias = Callable[
    ["ParsedAnswer", "Segment"],
    Awaitable[None],
]

AfterParsingCallback: TypeAlias = Callable[
    ["ParsedAnswer"],
    Awaitable[None],
]

AfterNewParsedAnswerCallback: TypeAlias = Callable[
    ["ParsedAnswer"],
    Awaitable[None],
]

AfterSegmentFinishedCallback: TypeAlias = Callable[
    ["ParsedAnswer", "Segment"],
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

BeforeToolCallCallback: TypeAlias = Callable[
    [str, dict, WithSecret | None],
    Awaitable[Union[SuccessfulToolResult, FailedToolResult, dict, None]],
]

BeforeAddNewMessageCallback: TypeAlias = Callable[
    ["Message"],
    Awaitable[Union[None, "Message"]],
]

BeforeCacheInvalidateCallback: TypeAlias = Callable[[], Awaitable[None]]

AfterCacheInvalidateCallback: TypeAlias = Callable[
    ["Agent", List["Message"]],
    Awaitable[None],
]

AfterParsedUserMessageCallback: TypeAlias = Callable[
    ["ParsedUserMessage"],
    Awaitable[bool | None],
]

AfterProcessCreateCallback: TypeAlias = Callable[
    ["ProcessCreateInfo"],
    Awaitable[None],
]

OnLlmErrorCallback: TypeAlias = Callable[
    [str, Exception, int],
    Awaitable[None],
]

AfterSelectingLlmCallback: TypeAlias = Callable[
    ["LanguageModel"],
    Awaitable[None],
]

AfterConversationRestoreCallback: TypeAlias = Callable[[], Awaitable[None]]


def _is_tool_result(value: SuccessfulToolResult | FailedToolResult | dict) -> bool:
    return isinstance(value, (SuccessfulToolResult, FailedToolResult))


class Lifecycle:
    """生命周期回调管理器，使用CallbackSlot子类管理回调。"""

    def __init__(self, registry):
        self.registry = registry
        self.registry.register_member("lifecycle", self)

        self.before_message_generation: BroadcastSlot[
            BeforeMessageGenerationCallback
        ] = BroadcastSlot()
        self.after_message_generation: BroadcastSlot[AfterMessageGenerationCallback] = (
            BroadcastSlot()
        )
        self.after_toolcall: AfterToolcallSlot[AfterToolcallCallback] = (
            AfterToolcallSlot()
        )
        self.after_token_generation: InterruptSlot[AfterTokenGenerationCallback] = (
            InterruptSlot()
        )
        self.before_parsing: BroadcastSlot[BeforeParsingCallback] = BroadcastSlot()
        self.after_segment: BroadcastSlot[AfterSegmentCallback] = BroadcastSlot()
        self.after_segment_update: BroadcastSlot[AfterSegmentUpdateCallback] = (
            BroadcastSlot()
        )
        self.after_parsing: BroadcastSlot[AfterParsingCallback] = BroadcastSlot()
        self.after_new_parsed_answer: BroadcastSlot[AfterNewParsedAnswerCallback] = (
            BroadcastSlot()
        )
        self.after_segment_finished: BroadcastSlot[AfterSegmentFinishedCallback] = (
            BroadcastSlot()
        )
        self.parsing_error: BroadcastSlot[ParsingErrorCallback] = BroadcastSlot()
        self.before_waiting_user: BroadcastSlot[BeforeWaitingUserCallback] = (
            BroadcastSlot()
        )
        self.before_agent_loop: BroadcastSlot[BeforeAgentLoopCallback] = BroadcastSlot()
        self.before_tool_call: ChainSlot[
            BeforeToolCallCallback,
            SuccessfulToolResult | FailedToolResult | dict | None,
        ] = ChainSlot(
            chain_arg=1,
            should_stop=_is_tool_result,
        )
        self.before_add_new_message: ChainSlot[BeforeAddNewMessageCallback, Message] = (
            ChainSlot()
        )
        self.before_cache_invalidate: BroadcastSlot[BeforeCacheInvalidateCallback] = (
            BroadcastSlot()
        )
        self.after_cache_invalidate: BroadcastSlot[AfterCacheInvalidateCallback] = (
            BroadcastSlot()
        )
        self.after_parsed_user_message: ShortCircuitSlot[
            AfterParsedUserMessageCallback, bool | None
        ] = ShortCircuitSlot()
        self.after_process_create: BroadcastSlot[AfterProcessCreateCallback] = (
            BroadcastSlot()
        )
        self.on_llm_error: BroadcastSlot[OnLlmErrorCallback] = BroadcastSlot()
        self.after_selecting_llm: BroadcastSlot[AfterSelectingLlmCallback] = (
            BroadcastSlot()
        )
        self.after_conversation_restore: BroadcastSlot[
            AfterConversationRestoreCallback
        ] = BroadcastSlot()
        self.before_exit: BroadcastSlot[Callable[[], Awaitable[None]]] = BroadcastSlot()

    def serialize(self) -> dict:
        return {}

    def restore_from(self, data: dict) -> None:
        pass
