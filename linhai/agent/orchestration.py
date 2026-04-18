"""
消息编排模块，负责管理大消息、垃圾消息、阈值通知等高级消息管理功能。
"""

from __future__ import annotations
import random
from pathlib import Path
import time
import hashlib
import reprlib
from typing import Optional, Literal, TypedDict, TYPE_CHECKING, Union

from linhai.agent.workflow import (
    context_forget_range_step1,
    context_forget_range_step2,
)
from .lifecycle import Lifecycle
from linhai.base import ToolCallMessage, Answer
from linhai.tool.base import ToolCallResultMessage
from linhai.multimodal import ImageMessage
from linhai.utils.tokenizer import count_tokens
from linhai.registry import Registry
from linhai.tool.base import ToolSet, ToolResultSuccess, ToolResultFailed, ToolArgInfo
from linhai.utils.common import UiNotice
from linhai.utils.i18n import t
from linhai.type_hints import ThresholdInfo
from linhai.token_manager import TokenManager
from linhai.base import Message
from .messages import RuntimeMessage
from .message import AgentMessage
from .conversation import save_cleaned_messages

if TYPE_CHECKING:
    from .main import Agent

r = reprlib.Repr()
r.maxstring = 100

LARGE_MESSAGE_TOKEN_THRESHOLD = 600
MIN_CLEANABLE_LARGE_MESSAGES = 3
MIN_CLEANABLE_TOTAL_TOKENS = 10000
CACHE_RATIO_ABNORMAL_THRESHOLD = 5.0


class ToolBlockDetailsDict(TypedDict):
    blocked_category: str | None
    actual_category: str
    is_dirty: bool
    current_state: str


def get_cleanable_large_messages(
    large_messages: set[Message],
    agent_message: AgentMessage,
    cleaned_messages_dict: dict[str, float],
) -> list[Message]:
    """获取可以清理的大消息列表，只根据最近是否清理过判断。

    Args:
        large_messages: 大消息集合
        agent_message: AgentMessage实例，用于查找消息索引
        cleaned_messages_dict: 已清理消息的哈希到时间戳的字典

    Returns:
        可以清理的大消息列表
    """
    cleanable: list[Message] = []
    current_time = time.time()
    expired_hashes = [
        hash_val
        for hash_val, timestamp in cleaned_messages_dict.items()
        if current_time - timestamp > 180
    ]
    for hash_val in expired_hashes:
        del cleaned_messages_dict[hash_val]

    for msg in large_messages:
        index = agent_message.find_message(msg)
        if index is None:
            continue
        content = msg.get_content()
        if isinstance(content, str):
            content_hash = hashlib.md5(content.encode()).hexdigest()
            if content_hash in cleaned_messages_dict:
                timestamp = cleaned_messages_dict[content_hash]
                if current_time - timestamp < 180:
                    continue
        cleanable.append(msg)
    return cleanable


def check_cleanable_threshold(
    cleanable_messages: list[Message],
) -> tuple[bool, int, int]:
    message_count = len(cleanable_messages)
    if message_count < MIN_CLEANABLE_LARGE_MESSAGES:
        return False, message_count, 0

    total_tokens = 0
    for msg in cleanable_messages:
        content = msg.get_content()
        if isinstance(content, str):
            total_tokens += count_tokens(content)

    if total_tokens < MIN_CLEANABLE_TOTAL_TOKENS:
        return False, message_count, total_tokens

    return True, message_count, total_tokens


class AgentContextOrchestration:
    """消息编排器，负责管理大消息、垃圾消息、阈值通知等高级消息管理功能。"""

    def __init__(self, registry: Registry, agent_message: AgentMessage):
        """初始化消息编排器。

        Args:
            registry: Registry实例
            agent_message: 基础消息管理器实例
        """
        self.registry = registry
        self.agent_message = agent_message
        self.registry.register_member("agent_context_orchestration", self)

        self.large_messages: set[Message] = set()
        self.cleaned_messages: dict[str, float] = {}
        self.consecutive_red_block_count: int = 0

        self._register_lifecycle_callbacks()

    async def context_forget_large_message(
        self,
    ) -> ToolResultSuccess | ToolResultFailed:
        """清理大消息，但保留最近添加的大消息。

        Returns:
            清理结果消息。如果当前可清理的大消息少于5条则返回失败消息。
        """
        large_count = len(self.large_messages)
        if large_count < MIN_CLEANABLE_LARGE_MESSAGES:
            return ToolResultFailed(
                content=f"需要至少{MIN_CLEANABLE_LARGE_MESSAGES}条大消息，当前只有{large_count}条"
            )

        removed_messages = get_cleanable_large_messages(
            self.large_messages,
            self.agent_message,
            cleaned_messages_dict=self.cleaned_messages,
        )

        meets_threshold, msg_count, total_tokens = check_cleanable_threshold(
            removed_messages
        )
        if not meets_threshold:
            return ToolResultFailed(
                content=f"可清理的大消息不满足阈值（消息数:{msg_count}, token数:{total_tokens}），需要至少{MIN_CLEANABLE_LARGE_MESSAGES}条消息且总token数至少{MIN_CLEANABLE_TOTAL_TOKENS}"
            )

        conversation_dir = self.registry.get_member_typechecked(
            "conversation_folder", Path
        )
        saved_path = save_cleaned_messages(
            conversation_dir, removed_messages, prefix="garbage_clean"
        )

        for message in removed_messages:
            placeholder = RuntimeMessage(f"当前消息已经被遗忘，转储到{saved_path}")
            await self.agent_message.replace_message(message, placeholder)
            content = message.get_content()
            if isinstance(content, str):

                content_hash = hashlib.md5(content.encode()).hexdigest()
                self.cleaned_messages[content_hash] = time.time()

        for msg in removed_messages:
            self.large_messages.discard(msg)

        result = f"清理了{len(removed_messages)}条大消息（约{total_tokens} token），保存到: {saved_path}"
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"已清理{len(removed_messages)}条大消息（约{total_tokens} token）",
            ),
        )
        return ToolResultSuccess(content=result)

    def compute_orchestration_context(
        self, tool_name: str, threshold_info: Optional[ThresholdInfo]
    ) -> dict:
        """计算编排上下文信息，合并多个函数的功能。

        Args:
            tool_name: 工具名称
            threshold_info: 阈值信息，可能为None

        Returns:
            包含以下键的字典：
                threshold_info: 传入的阈值信息
                current_state: 红绿灯状态字符串
                is_dirty: 布尔值，token用量是否已失效（刚清理过）
                notification_message: 提示消息字符串，可能为None
                tool_block_details: ToolBlockDetailsDict
        """
        if threshold_info is None:
            return {
                "threshold_info": None,
                "current_state": "绿灯",
                "is_dirty": False,
                "notification_message": None,
                "tool_block_details": {
                    "blocked_category": None,
                    "actual_category": "other",
                    "is_dirty": False,
                    "current_state": "绿灯",
                },
                "cache_ratio": None,
            }

        usage_ratio = threshold_info["usage_ratio"]
        percentage = usage_ratio * 100
        if percentage < 80:
            current_state = "绿灯"
        elif 80 <= percentage < 90:
            current_state = "黄灯"
        else:
            current_state = "红灯"

        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        is_dirty = token_manager.is_dirty

        actual_category = (
            "cleanup"
            if tool_name
            in {
                "context_forget_range_step1",
                "context_forget_range_step2",
                "context_forget_large_message",
            }
            else "other"
        )
        if current_state == "红灯":
            if is_dirty:
                blocked_category = "cleanup"
            else:
                blocked_category = "other"
        else:
            blocked_category = None

        tool_block_details: ToolBlockDetailsDict = {
            "blocked_category": blocked_category,
            "actual_category": actual_category,
            "is_dirty": is_dirty,
            "current_state": current_state,
        }

        notification_message = None
        cache_ratio: float | None = None
        cache_ratio_text = ""
        if token_manager.cumulative_token_usage is not None:
            input_tokens = token_manager.cumulative_token_usage["input_tokens"]
            cached_input_tokens = token_manager.cumulative_token_usage[
                "cached_input_tokens"
            ]
            if input_tokens > 0:
                cache_ratio = (cached_input_tokens / input_tokens) * 100
                cache_ratio_text = f", 缓存比例: {cache_ratio:.0f}%"

        if current_state != "绿灯" or is_dirty:
            total_large_count = len(self.large_messages)
            cleanable_messages = get_cleanable_large_messages(
                self.large_messages,
                self.agent_message,
                cleaned_messages_dict=self.cleaned_messages,
            )
            cleanable_count = len(cleanable_messages)

            if is_dirty:
                base_info = f"当前上下文占用量失效, 总大消息数: {total_large_count}, 可清理: {cleanable_count}, token用量信息已失效{cache_ratio_text}"
                suggestion = "建议: 继续，在上下文实际长度更新之后runtime会另行通知"
            else:
                base_info = f"当前为{current_state}状态, 上下文占用量为{percentage:.1f}%, 总大消息数: {total_large_count}, 可清理: {cleanable_count}{cache_ratio_text}"
                if current_state == "红灯":
                    if cleanable_count >= MIN_CLEANABLE_LARGE_MESSAGES:
                        suggestion = "建议: 立即暂停当前任务，开始使用context_forget_large_message清理上下文"
                    else:
                        suggestion = "建议: 立即暂停当前任务，开始使用context_forget_range_step1清理上下文"
                elif current_state == "黄灯":
                    if (
                        cache_ratio is not None
                        and cache_ratio >= CACHE_RATIO_ABNORMAL_THRESHOLD
                        and cache_ratio < 80
                    ):
                        suggestion = f"建议: 当前缓存命中率{cache_ratio:.0f}%低于80%，优先保证缓存命中率而不是清理上下文"
                    else:
                        suggestion = (
                            "建议: 根据缓存比例判断是否需要使用context_forget_large_message工具"
                            if cleanable_count >= 5
                            else ""
                        )
                else:
                    suggestion = "建议: 不要担心消息限制，立即工作"
                    if (
                        cache_ratio is not None
                        and cache_ratio >= CACHE_RATIO_ABNORMAL_THRESHOLD
                        and cache_ratio < 90
                    ):
                        suggestion = f"建议: 当前缓存命中率{cache_ratio:.0f}%低于90%，优先保证缓存命中率而不是清理上下文"
            notification_message = f"{base_info}, {suggestion}"

        return {
            "threshold_info": threshold_info,
            "current_state": current_state,
            "is_dirty": is_dirty,
            "notification_message": notification_message,
            "tool_block_details": tool_block_details,
            "cache_ratio": cache_ratio,
        }

    def get_status_display_pieces(self, use_nerd_font: bool = False) -> list[str]:
        """获取状态显示片段列表，用于TUI底栏。

        Args:
            use_nerd_font: 是否使用nerd font符号

        Returns:
            状态显示片段列表，每个片段是一个独立的显示单元
        """
        message_count = len(self.agent_message.get_messages())
        large_count = len(self.large_messages)

        pieces = []
        if use_nerd_font:
            pieces.append(f"\uf27a {message_count}")
            if large_count > 0:
                pieces.append(f"\uf1c0 {large_count}")
        else:
            pieces.append(f"❐ {message_count}")
            if large_count > 0:
                pieces.append(f"■ {large_count}")

        return pieces

    def get_context_cleaning_toolset(self) -> "ToolSet":
        """获取编排工具集，合并消息管理和工作流工具。

        Returns:
            包含编排工具的ToolSet
        """

        toolset = ToolSet()

        @toolset.register_tool(
            name="context_forget_large_message",
            desc=t(
                {
                    "zh_CN": "清理大消息：如果当前有至少{MIN_CLEANABLE_LARGE_MESSAGES}条大消息，全部删除并返回每条被删除的消息的repr。",
                    "en": "Clean large messages: delete all if at least {MIN_CLEANABLE_LARGE_MESSAGES} exist, return repr of each.",
                }
            ),
            args={},
            required_args=[],
            conflict_with=["context_forget_range_step1", "context_forget_range_step2"],
        )
        async def context_forget_large_message_tool() -> (
            ToolResultSuccess | ToolResultFailed
        ):
            result = await self.context_forget_large_message()
            if isinstance(result, ToolResultSuccess):
                token_manager = self.registry.get_member_typechecked(
                    "token_manager", TokenManager
                )
                token_manager.mark_dirty()
            return result

        @toolset.register_tool(
            name="context_forget_range_step1",
            desc=t(
                {
                    "zh_CN": "压缩范围第一步：生成消息列表总结并返回range_clean_id。",
                    "en": "Compress range step 1: generate message list summary and return range_clean_id.",
                }
            ),
            args={},
            required_args=[],
            conflict_with=[
                "context_forget_large_message",
                "context_forget_range_step2",
            ],
        )
        async def context_forget_range_step1_tool() -> (
            ToolResultSuccess | ToolResultFailed
        ):
            result = await context_forget_range_step1(self.registry)
            return result

        @toolset.register_tool(
            name="context_forget_range_step2",
            desc=t(
                {
                    "zh_CN": "压缩范围第二步：使用range_clean_id确认删除范围并执行删除。",
                    "en": "Compress range step 2: use range_clean_id to confirm and execute deletion.",
                }
            ),
            args={
                "range_clean_id": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "range_clean_id，从第一步获取",
                            "en": "range_clean_id from step 1",
                        }
                    ),
                    type="str",
                ),
                "start_id": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "开始删除的消息ID",
                            "en": "Start message ID to delete",
                        }
                    ),
                    type="int",
                ),
                "end_id": ToolArgInfo(
                    desc=t(
                        {"zh_CN": "结束删除的消息ID", "en": "End message ID to delete"}
                    ),
                    type="int",
                ),
                "description": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "描述删除内容，建议包含待办任务",
                            "en": "Description of deletion, suggest including TODO tasks",
                        }
                    ),
                    type="str",
                ),
            },
            required_args=["range_clean_id", "start_id", "end_id", "description"],
            conflict_with=[
                "context_forget_large_message",
                "context_forget_range_step1",
            ],
        )
        async def context_forget_range_step2_tool(
            range_clean_id: str, start_id: int, end_id: int, description: str
        ) -> ToolResultSuccess | ToolResultFailed:
            result = await context_forget_range_step2(
                self.registry, range_clean_id, start_id, end_id, description
            )
            if isinstance(result, ToolResultSuccess):
                token_manager = self.registry.get_member_typechecked(
                    "token_manager", TokenManager
                )
                token_manager.mark_dirty()
            return result

        return toolset

    def _register_lifecycle_callbacks(self) -> None:
        """注册生命周期回调。"""
        from .lifecycle import Lifecycle

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        lifecycle.before_add_new_message.register(self._before_add_new_message)
        lifecycle.before_message_generation.register(self._before_message_generation)

    async def _before_add_new_message(self, message: "Message") -> None:
        """在添加新消息前检查是否为大消息。"""
        from linhai.base import AssistantMessage
        from linhai.multimodal import ImageMessage

        if isinstance(message, AssistantMessage):
            return

        if isinstance(message, ImageMessage):
            self.large_messages.add(message)
        else:
            content = message.get_content()
            if content is not None:
                token_count = count_tokens(content)
                if token_count > LARGE_MESSAGE_TOKEN_THRESHOLD:
                    self.large_messages.add(message)

    async def _before_message_generation(self) -> None:
        """在消息生成前清理无效的大消息引用。"""
        valid_messages = set(self.agent_message.messages)
        self.large_messages = {
            msg for msg in self.large_messages if msg in valid_messages
        }


class RedStateToolBlockPlugin:
    """红灯状态工具调用拦截插件。

    在红灯状态且一分钟内没有调用过消息清理类工具时禁止调用其他工具。
    """

    def __init__(self, registry: Registry):
        self.registry = registry
        self.CLEANUP_TOOLS = {
            "context_forget_range_step1",
            "context_forget_range_step2",
            "context_forget_large_message",
        }

    async def before_toolcall(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
    ) -> Union[ToolResultSuccess, ToolResultFailed, dict, None]:
        """在工具调用前检查是否需要阻止工具调用。

        Returns:
            ToolResultFailed: 阻止工具调用并返回失败结果
            dict: 修改后的工具调用参数
            None: 不做处理
        """
        orchestration = self.registry.get_member_typechecked(
            "agent_context_orchestration", AgentContextOrchestration
        )

        from .main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)

        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return None

        if orchestration is None:
            return None

        context = orchestration.compute_orchestration_context(tool_name, threshold_info)
        details = context["tool_block_details"]
        cache_ratio = context.get("cache_ratio")
        current_state = details["current_state"]

        cache_warning = ""
        should_remind_due_to_cache = False
        if cache_ratio is not None and details["actual_category"] == "cleanup":
            if cache_ratio >= CACHE_RATIO_ABNORMAL_THRESHOLD:
                if current_state == "绿灯" and cache_ratio < 90:
                    should_remind_due_to_cache = True
                    cache_warning = f"当前缓存命中率{cache_ratio:.0f}%低于90%"
                elif current_state == "黄灯" and cache_ratio < 80:
                    should_remind_due_to_cache = True
                    cache_warning = f"当前缓存命中率{cache_ratio:.0f}%低于80%"

        if should_remind_due_to_cache:
            warning_msg = f"你在上下文健康且缓存命中率较低的情况下清理了上下文，这进一步破坏了缓存，为什么不优先保证缓存命中率而是清理上下文？{cache_warning}"
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING",
                    content=f"缓存命中率低时清理上下文：{cache_warning}",
                ),
            )

        if details["blocked_category"] == details["actual_category"]:
            is_dirty = details["is_dirty"]
            current_state = details["current_state"]
            if details["blocked_category"] == "other":
                orchestration.consecutive_red_block_count += 1

            if details["blocked_category"] == "cleanup" and is_dirty:
                error_msg = f"token用量信息已失效，禁止调用{tool_name}工具"
                ui_msg = f"token用量信息已失效，禁止调用清理工具"
            else:
                error_msg = (
                    f"错误：当前处于{current_state}状态（token使用率{threshold_info['usage_ratio']*100:.1f}%），"
                    f"禁止调用{tool_name}工具！"
                    "红灯状态下只允许调用消息管理工具。"
                )
                ui_msg = f"{current_state}状态下阻止调用{tool_name}工具，请先调用消息清理类工具"

            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="ERROR",
                    content=ui_msg,
                ),
            )
            return ToolResultFailed(content=error_msg)

        orchestration.consecutive_red_block_count = 0
        agent.message_processor.update_notification_message(
            None, source="consecutive_red_block", sort_value=0
        )
        return None

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.before_tool_call.register(self.before_toolcall)


class NotificationMessagePlugin:
    """添加notification message的插件。

    将添加notification message的实现拆分成一个新的plugin类。
    """

    def __init__(self, registry: Registry):
        self.registry = registry

    async def before_message_generation(self) -> None:
        """在消息生成前添加notification message。"""
        from .main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        orchestration = self.registry.get_member_typechecked(
            "agent_context_orchestration", AgentContextOrchestration
        )

        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return

        if orchestration is None:
            return

        context = orchestration.compute_orchestration_context("", threshold_info)
        notification_message = context["notification_message"]
        if notification_message is not None:
            agent.message_processor.update_notification_message(
                RuntimeMessage(notification_message),
                source="threshold_notification",
                sort_value=0,
            )

        if orchestration.consecutive_red_block_count >= 3:
            cleanable_messages = get_cleanable_large_messages(
                orchestration.large_messages,
                orchestration.agent_message,
                cleaned_messages_dict=orchestration.cleaned_messages,
            )
            cleanable_count = len(cleanable_messages)

            if cleanable_count >= MIN_CLEANABLE_LARGE_MESSAGES:
                example_call = (
                    '{"name": "context_forget_large_message", "arguments": {}}'
                )
            else:
                example_call = '{"name": "context_forget_range_step1", "arguments": {}}'

            message_content = f"""【注意】你应该立即开始使用正确的工具调用清理上下文，而不是继续工作或者使用错误的工具调用，例如：

```json toolcall
{example_call}
```
"""
            agent.message_processor.update_notification_message(
                RuntimeMessage(message_content),
                source="consecutive_red_block",
                sort_value=0,
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.before_message_generation.register(self.before_message_generation)


class LargeMessageCountPlugin:
    """大消息数量通知插件。

    根据大消息数量动态管理notification_message：
    - 大消息少于3条时：提示不能调用context_forget_large_message
    - 大消息至少3条时：删除提示（不添加notification_message）
    """

    def __init__(self, registry: Registry):
        self.registry = registry

    async def before_message_generation(self) -> None:
        """在消息生成前根据大消息数量管理notification_message。"""
        from .main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        orchestration = self.registry.get_member_typechecked(
            "agent_context_orchestration", AgentContextOrchestration
        )

        if orchestration is None:
            return

        large_count = len(orchestration.large_messages)

        if large_count < MIN_CLEANABLE_LARGE_MESSAGES:

            message_content = f"当前只有{large_count}条大消息，需要至少{MIN_CLEANABLE_LARGE_MESSAGES}条大消息且总token数超过{MIN_CLEANABLE_TOTAL_TOKENS}才能调用context_forget_large_message"
            agent.message_processor.update_notification_message(
                RuntimeMessage(message_content),
                source="large_message_count",
                sort_value=0,
            )
        else:

            agent.message_processor.update_notification_message(
                None, source="large_message_count", sort_value=0
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.before_message_generation.register(self.before_message_generation)
