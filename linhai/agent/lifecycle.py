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

if TYPE_CHECKING:
    from linhai.agent.messages import RuntimeMessage
    from linhai.base import LanguageModel
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.agent.callback_slot import (
    BroadcastSlot,
    ShortCircuitSlot,
    InterruptSlot,
    ChainSlot,
)

if TYPE_CHECKING:
    from linhai.agent.main import Agent
    from linhai.parsed_message import ParsedAnswer, Segment as Segment
    from linhai.agent.user_message_handler import ParsedUserMessage
    from linhai.machine_control.process import ProcessCreateInfo

BeforeMessageGenerationCallback: TypeAlias = Callable[[], Awaitable[None]]

AfterMessageGenerationCallback: TypeAlias = Callable[
    ["ParsedAnswer", str, list[dict]],
    Awaitable[None],
]

AfterToolcallCallback: TypeAlias = Callable[
    [
        str,
        int,
        Literal["skipped", "success", "failed"],
        Message | None,
        dict,
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
    [str, dict, list[str] | None],
    Awaitable[Union[ToolResultSuccess, ToolResultFailed, dict, None]],
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


def _is_tool_result(value: ToolResultSuccess | ToolResultFailed | dict) -> bool:
    return isinstance(value, (ToolResultSuccess, ToolResultFailed))


class Lifecycle:
    """生命周期回调管理器，使用CallbackSlot子类管理回调。"""

    def __init__(self, registry):
        self.registry = registry
        self.registry.register_member("lifecycle", self)

        self.before_message_generation = BroadcastSlot()
        self.after_message_generation = BroadcastSlot()
        self.after_toolcall = ShortCircuitSlot()
        self.after_token_generation = InterruptSlot()
        self.before_parsing = BroadcastSlot()
        self.after_segment = BroadcastSlot()
        self.after_segment_update = BroadcastSlot()
        self.after_parsing = BroadcastSlot()
        self.after_new_parsed_answer = BroadcastSlot()
        self.after_segment_finished = BroadcastSlot()
        self.parsing_error = BroadcastSlot()
        self.before_waiting_user = BroadcastSlot()
        self.before_agent_loop = BroadcastSlot()
        self.before_tool_call = ChainSlot(
            chain_arg=1,
            should_stop=_is_tool_result,
        )
        self.before_add_new_message = ChainSlot()
        self.before_cache_invalidate = BroadcastSlot()
        self.after_cache_invalidate = BroadcastSlot()
        self.after_parsed_user_message = ShortCircuitSlot()
        self.after_process_create = BroadcastSlot()
        self.on_llm_error = BroadcastSlot()
        self.after_selecting_llm = BroadcastSlot()
        self.after_conversation_restore = BroadcastSlot()

    def serialize(self) -> dict:
        return {}

    def restore_from(self, data: dict) -> None:
        pass
