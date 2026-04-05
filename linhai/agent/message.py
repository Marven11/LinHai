"""基础消息管理模块，负责管理Agent的基础消息队列和处理逻辑。"""

import json
from pathlib import Path
from typing import List, Optional, Sequence, TypedDict

from linhai.registry import Registry
from linhai.agent.conversation import save_context
from linhai.type_hints import ChatCompletionContentPartTextParam


from linhai.llm import Message, LanguageModelMessage
from .messages import RuntimeMessage

from linhai.llm import UserMessage
from linhai.utils.common import UiNotice


class NotificationMessageEntry(TypedDict):
    """通知消息条目，包含源标识符、消息内容和排序值。"""

    source: str
    message: Message
    sort_value: int


class ExplicitCacheMessage(Message):
    def __init__(self, text: str):
        self.text = text

    def to_llm_message(self) -> LanguageModelMessage:
        text_block: ChatCompletionContentPartTextParam = {
            "type": "text",
            "text": self.text,
            "cache_control": {"type": "ephemeral"},
        }
        return {"role": "user", "content": [text_block]}

    def get_content(self) -> str:
        return self.text

    def to_json(self) -> str:
        return json.dumps({"text": self.text})

    @classmethod
    def from_json(cls, json_str: str, registry: Registry):
        _ = registry
        data = json.loads(json_str)
        return cls(text=data["text"])


class AgentMessage:
    """基础消息管理器，负责管理基础消息队列和相关操作。"""

    def __init__(
        self,
        registry: Registry,
        pinned_messages: Sequence[Message],
    ):
        """初始化基础消息管理器。

        Args:
            pinned_messages: 固化的置顶消息列表，不会被历史压缩删除
        """
        self.registry = registry
        self.registry.register_member("agent_message", self)

        self.pinned_messages: List[Message] = list(pinned_messages)
        self.messages: List[Message] = []
        self.notification_messages: dict[str, NotificationMessageEntry] = {}
        self.queued_messages: List[Message] = []
        self.explicit_cache_anchors: list[int] = []
        self.registry.add_postinit(self.postinit)
        self.is_anchor_updated = False

    def postinit(self):
        from .lifecycle import Lifecycle

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        lifecycle.register_after_message_generation(self.after_message_generation)

    async def after_message_generation(self, parsed_answer, full_response, tool_calls):
        is_anchor_updated = self.is_anchor_updated
        self.is_anchor_updated = False
        token_usage = parsed_answer._answer.get_token_usage()
        if token_usage is None:
            return

        from ..llm_manager import LlmManager

        llm_manager = self.registry.get_member_typechecked("llm_manager", LlmManager)
        cache_info = llm_manager.get_current_llm().get_explicit_cache_info()
        if cache_info is None:
            return

        from ..token_manager import TokenManager

        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        if (
            token_manager.cumulative_token_usage
            and token_manager.cumulative_token_usage["cache_creation_input_tokens"]
        ):
            estimated_cache_refresh_factor = (
                token_manager.cumulative_token_usage["cached_input_tokens"] + 50_0000
            ) / (
                token_manager.cumulative_token_usage["cache_creation_input_tokens"]
                + 10_0000
            )
        else:
            estimated_cache_refresh_factor = 5
        cached_input_tokens = (
            token_usage.cached_input_tokens if token_usage.cached_input_tokens else 0
        )
        spending_with_old_cache = (
            cached_input_tokens * cache_info.cache_hit_price_ratio
            + (token_usage.input_tokens - cached_input_tokens) * 1.0
        )
        spending_with_new_cache = (
            token_usage.input_tokens * cache_info.cache_hit_price_ratio
        )
        if (
            spending_with_old_cache * estimated_cache_refresh_factor
            > spending_with_new_cache * estimated_cache_refresh_factor
            + token_usage.input_tokens * cache_info.cache_write_price_ratio
        ) and not is_anchor_updated:
            self.is_anchor_updated = True
            anchor = self.calculate_explicit_cache_anchor()
            if anchor is not None and anchor not in self.explicit_cache_anchors:
                self.explicit_cache_anchors.append(anchor)
                self.explicit_cache_anchors.sort(reverse=True)
                self.explicit_cache_anchors = self.explicit_cache_anchors[-4:]
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="INFO",
                    content="新增显式缓存",
                ),
            )

    async def count_invalidate_cache(self):
        """标记当前缓存失效

        在使用隐式缓存时什么都不做，在使用显式缓存时清除缓存点并提醒用户"""
        from .lifecycle import Lifecycle

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        await lifecycle.trigger_before_cache_invalidate()
        if self.explicit_cache_anchors:
            await self.registry.send_if_exists(
                "ui_log", UiNotice(level="WARNING", content="上下文缓存失效！")
            )
            self.explicit_cache_anchors = []

    async def add_pinned_message(self, msg: Message) -> None:
        """添加置顶消息。

        Args:
            msg: 要添加的置顶消息
        """
        from .lifecycle import Lifecycle

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        processed_message = await lifecycle.trigger_before_add_new_message(msg)
        if processed_message is None:
            processed_message = msg
        self.pinned_messages.append(processed_message)

    async def add_new_message(self, msg: Message) -> None:
        """添加普通消息到队列。

        新消息插入在普通消息后，通知消息（notification_messages）前。

        Args:
            msg: 要添加的普通消息
        """
        from .lifecycle import Lifecycle

        if not self.explicit_cache_anchors and self.is_explicit_cache_enabled():
            anchor = self.calculate_explicit_cache_anchor()
            if anchor is not None:
                self.explicit_cache_anchors.append(anchor)
                await self.registry.send_if_exists(
                    "ui_log", UiNotice(level="INFO", content="刷新显式缓存")
                )

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        processed_message = await lifecycle.trigger_before_add_new_message(msg)
        if processed_message is None:
            processed_message = msg
        self.messages.append(processed_message)

    def is_explicit_cache_enabled(self) -> bool:
        from ..llm_manager import LlmManager

        llm_manager = self.registry.get_member_typechecked("llm_manager", LlmManager)
        return llm_manager.get_current_llm().get_explicit_cache_info() is not None

    def calculate_explicit_cache_anchor(self) -> Optional[int]:
        msgs = self.pinned_messages + self.messages
        for explicit_cache_anchor in range(len(msgs) - 1, -1, -1):
            msg = msgs[explicit_cache_anchor]
            if msg.get_content() is not None:
                return explicit_cache_anchor
        return None

    def mark_explicit_cache_savepoint(self, msgs: list[Message]) -> list[Message]:
        if not self.explicit_cache_anchors:
            return msgs
        msgs = msgs.copy()
        for anchor in self.explicit_cache_anchors:
            content = msgs[anchor].get_content()
            assert content is not None
            msgs[anchor] = ExplicitCacheMessage(content)
        return msgs

    def get_messages(self) -> List[Message]:
        """获取当前所有消息（包括pinned_messages和notification_messages）。

        Returns:
            消息列表，顺序为：pinned_messages + messages + notification_messages
        """
        sorted_entries = sorted(
            self.notification_messages.values(), key=lambda x: x["sort_value"]
        )
        notification_messages = [entry["message"] for entry in sorted_entries]
        messages = self.pinned_messages + self.messages + notification_messages
        if self.is_explicit_cache_enabled():
            messages = self.mark_explicit_cache_savepoint(messages)
        return messages

    def get_message_count(self) -> int:
        """获取当前普通消息数量（不包括pinned_messages和notification_messages）。

        Returns:
            普通消息数量
        """
        return len(self.messages)

    def is_last_message_user(self) -> bool:
        """检查最后一条消息是否来自用户。

        Returns:
             如果是用户消息返回True，否则False
        """
        all_messages = self.get_messages()
        if not all_messages:
            return False
        msg = all_messages[-1]
        return isinstance(msg, UserMessage)

    async def replace_messages(self, messages: List[Message]) -> None:
        """替换整个普通消息列表。

        Args:
            messages: 新的普通消息列表（不包含pinned_messages和notification_messages）
        """
        await self.count_invalidate_cache()
        self.messages = messages
        await self._trigger_after_cache_invalidate()

    async def insert_message(self, index: int, message: Message) -> None:
        """在指定位置插入消息。

        Args:
            index: 插入位置（相对于普通消息列表）
            message: 要插入的消息
        """
        await self.count_invalidate_cache()
        self.messages.insert(index, message)
        await self._trigger_after_cache_invalidate()

    async def delete_message_range(self, start: int, end: int) -> List[Message]:
        """删除指定范围的消息。

        Args:
            start: 起始索引（相对于普通消息列表）
            end: 结束索引（相对于普通消息列表）

        Returns:
             被删除的消息列表
        """
        await self.count_invalidate_cache()
        deleted = self.messages[start : end + 1]
        self.messages[start : end + 1] = []
        await self._trigger_after_cache_invalidate()
        return deleted

    async def filter_messages(self, condition) -> None:
        """根据条件过滤普通消息。

        Args:
            condition: 过滤条件函数
        """
        await self.count_invalidate_cache()
        self.messages = [msg for msg in self.messages if condition(msg)]
        await self._trigger_after_cache_invalidate()

    async def replace_message(self, old_message: Message, new_message: Message) -> None:
        """将普通消息列表中的指定消息替换为新消息。

        Args:
            old_message: 要替换的旧消息
            new_message: 替换后的新消息
        """
        await self.count_invalidate_cache()
        if old_message in self.messages:
            index = self.messages.index(old_message)
            from .lifecycle import Lifecycle

            lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
            processed_message = await lifecycle.trigger_before_add_new_message(
                new_message
            )
            self.messages[index] = processed_message
            await self._trigger_after_cache_invalidate()

    def update_notification_message(
        self, message: Message | None, source: str, sort_value: int
    ) -> None:
        """更新或移除通知消息（notification message）。

        Args:
            message: 消息内容，如果为None则移除对应source的消息
                  必须是Message实例
            source: 消息来源标识符，用于区分不同的notification messages
            sort_value: 排序权重，必须指定
        """
        if source in self.notification_messages:
            del self.notification_messages[source]

        if message is not None:
            self.notification_messages[source] = {
                "source": source,
                "message": message,
                "sort_value": sort_value,
            }

    def add_queued_message(self, msg: Message) -> None:
        """添加排队消息。

        Args:
            msg: 排队消息
        """
        self.queued_messages.append(msg)

    async def _trigger_after_cache_invalidate(self) -> None:
        from .lifecycle import Lifecycle
        from .main import Agent

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        agent = self.registry.get_member_typechecked("agent", Agent)
        await lifecycle.trigger_after_cache_invalidate(agent, self.messages)

    def _save_context(self) -> None:
        """保存当前上下文到文件。"""
        conversation_dir = self.registry.get_member_typechecked(
            "conversation_folder", Path
        )
        save_context(conversation_dir, self.get_messages())

    async def process_queued_messages(self) -> None:
        """处理所有排队消息。"""
        if not self.queued_messages:
            return
        await self.registry.send_if_exists(
            "ui_log", UiNotice(level="INFO", content="排队消息被处理")
        )
        await self.add_new_message(
            RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理：")
        )
        for msg in self.queued_messages:
            await self.add_new_message(msg)
        self.queued_messages = []

    def find_message(self, message: Message) -> int | None:
        """查找消息在messages列表中的索引。

        Args:
            message: 要查找的消息

        Returns:
            消息的索引，如果不存在则返回None
        """
        if message in self.messages:
            return self.messages.index(message)
        return None
