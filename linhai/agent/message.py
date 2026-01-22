"""基础消息管理模块，负责管理Agent的基础消息队列和处理逻辑。"""

import datetime
import json
from pathlib import Path
from typing import List, Optional, Sequence, TypedDict

from linhai.group_chat import GroupChat
from linhai.input_parser import parse_user_input
from linhai.llm import UserMessage
from linhai.utils import CliRuntimeNotice

from .base import Message, RuntimeMessage


class AppendingMessageEntry(TypedDict):
    """附加消息条目，包含源标识符、消息内容和排序值。"""

    source: str
    message: Message
    sort_value: int


class AgentMessage:
    """基础消息管理器，负责管理基础消息队列和相关操作。"""

    def __init__(
        self, group_chat: GroupChat, init_messages: Sequence[Message]
    ):
        """初始化基础消息管理器。

        Args:
            init_messages: 初始消息列表
        """
        self.group_chat = group_chat
        self.group_chat.register_member("agent_message", self)

        self.messages: List[Message] = list(init_messages)
        self.appending_messages: dict[str, AppendingMessageEntry] = {}
        self.queued_messages: List[Message] = []

        self.cache_invalidate_count = 0

    def handle_user_message(self, msg: UserMessage) -> None:
        """处理用户消息。

        Args:
            msg: 用户消息
        """
        assert isinstance(msg, UserMessage)

        content = msg.message.strip()
        parsed_input = parse_user_input(content)

        if parsed_input.switch_model:
            self.add_new_message(msg)
            return

        self.add_new_message(msg)

    async def count_invalidate_cache(self):
        interrupt_msg = CliRuntimeNotice(level="WARNING", content="消息缓存失效！")
        self.cache_invalidate_count += 1
        await self.group_chat.send_if_exists("ui_log", interrupt_msg)

    def add_new_message(self, msg: Message) -> None:
        """添加消息到队列。

        新消息插入在普通消息后，appending_messages前。

        Args:
            msg: 要添加的消息
        """
        self.messages.append(msg)

    def get_messages(self) -> List[Message]:
        """获取当前所有消息（包括appending_messages）。

        Returns:
            消息列表
        """
        # 按sort_value排序，然后提取message
        sorted_entries = sorted(
            self.appending_messages.values(), key=lambda x: x["sort_value"]
        )
        appending_messages = [entry["message"] for entry in sorted_entries]
        return self.messages + appending_messages

    def get_message_count(self) -> int:
        """获取当前消息数量。

        Returns:
            消息数量
        """
        return len(self.messages)

    def is_last_message_user(self) -> bool:
        """检查最后一条消息是否来自用户。

        Returns:
             如果是用户消息返回True，否则False
        """
        if not self.messages:
            return False
        msg = self.messages[-1]
        return isinstance(msg, UserMessage)

    async def replace_messages(self, messages: List[Message]) -> None:
        """替换整个消息列表。

        Args:
            messages: 新的消息列表（不包含appending_messages）
        """
        await self.count_invalidate_cache()
        self.messages = messages

    async def insert_message(self, index: int, message: Message) -> None:
        """在指定位置插入消息。

        Args:
            index: 插入位置
            message: 要插入的消息
        """
        await self.count_invalidate_cache()
        self.messages.insert(index, message)

    async def delete_message_range(self, start: int, end: int) -> List[Message]:
        """删除指定范围的消息。

        Args:
            start: 起始索引
            end: 结束索引

        Returns:
             被删除的消息列表
        """
        await self.count_invalidate_cache()
        deleted = self.messages[start : end + 1]
        self.messages[start : end + 1] = []
        return deleted

    async def filter_messages(self, condition) -> None:
        """根据条件过滤消息。

        Args:
            condition: 过滤条件函数
        """
        await self.count_invalidate_cache()
        self.messages = [msg for msg in self.messages if condition(msg)]

    async def remove_message(self, message: Message) -> None:
        """从消息列表中移除指定消息。

        Args:
            message: 要移除的消息
        """
        await self.count_invalidate_cache()
        if message in self.messages:
            self.messages.remove(message)

    def update_appending_message(
        self, message: Message | None, source: str, sort_value: int
    ) -> None:
        """更新或移除appending message。

        Args:
            message: 消息内容，如果为None则移除对应source的消息
                  必须是Message实例
            source: 消息来源标识符，用于区分不同的appending messages
            sort_value: 排序权重，必须指定
        """
        if source in self.appending_messages:
            del self.appending_messages[source]

        if message is not None:
            self.appending_messages[source] = {
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

    def process_queued_messages(self) -> None:
        """处理所有排队消息。"""
        if self.queued_messages:
            self.messages.append(
                RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理：")
            )
            self.messages.extend(self.queued_messages)
            self.queued_messages = []

    async def save_conversation_history(self, save_dir: Optional[Path] = None) -> None:
        """保存对话历史到文件。

        Args:
            save_dir: 保存目录，默认为用户home目录下的.linhai/conversations
        """
        if save_dir is None:
            save_dir = Path.home() / ".local" / "share" / "linhai" / "conversations"
        save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"conversation_{timestamp}.json"
        filepath = save_dir / filename

        history_data = []
        for msg in self.messages:
            msg_dict = json.loads(msg.to_json())
            history_data.append(msg_dict)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)

        except (IOError, OSError) as e:
            raise RuntimeError(f"保存对话历史失败: {e}")
