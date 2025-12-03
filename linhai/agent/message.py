"""消息处理模块，负责管理Agent的消息队列和处理逻辑。"""

import datetime
import json
import random
from pathlib import Path
from typing import List, Optional, Sequence

from linhai.group_chat import GroupChat
from linhai.input_parser import parse_user_input
from linhai.llm import UserMessage
from linhai.utils import CliRuntimeNotice, generate_id

from .base import Message, RuntimeMessage


class AgentMessage:
    """消息处理器，负责管理消息队列和相关操作。"""

    def __init__(
        self, group_chat: GroupChat, init_messages: Optional[Sequence[Message]] = None
    ):
        """初始化消息处理器。

        Args:
            init_messages: 初始消息列表
        """
        self.group_chat = group_chat
        self.group_chat.register_member("agent_message", self)

        self.messages: List[Message] = list(init_messages) if init_messages else []
        self.appending_messages: set[RuntimeMessage] = set()
        self.large_messages: dict[str, Message] = {}
        self.queued_messages: List[Message] = []
        self.garbage_message_ids: set[str] = set()
        self.last_threshold_state: Optional[str] = None

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
            self.append_message(msg)
            return

        self.append_message(msg)

    async def count_invalidate_cache(self):
        interrupt_msg = CliRuntimeNotice(level="WARNING", content="消息缓存失效！")
        self.cache_invalidate_count += 1
        await self.group_chat.send_if_exists("ui_log", interrupt_msg)

    def append_message(self, msg: Message) -> None:
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
        return self.messages + list(self.appending_messages)

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

    def mark_messages_as_garbage(self, message_ids: list[str]) -> str:
        """将多个消息标记为垃圾消息。

        Args:
            message_ids: 要标记为垃圾的消息ID列表

        Returns:
            标记结果消息
        """
        marked_ids = []
        not_found_ids = []
        already_marked_ids = []

        for message_id in message_ids:
            if message_id not in self.large_messages:
                not_found_ids.append(message_id)
                continue

            if message_id in self.garbage_message_ids:
                already_marked_ids.append(message_id)
                continue

            self.garbage_message_ids.add(message_id)
            marked_ids.append(message_id)

        result_parts = []
        if marked_ids:
            result_parts.append(f"已成功标记 {len(marked_ids)} 条消息为垃圾消息")
            result_parts.append(f"ID为{', '.join(marked_ids)}的消息已被标记为垃圾")
        if not_found_ids:
            result_parts.append(f"以下ID不存在: {', '.join(not_found_ids)}")
        if already_marked_ids:
            result_parts.append(f"以下ID已被重复标记: {', '.join(already_marked_ids)}")

        return "; ".join(result_parts) if result_parts else "没有消息被标记"

    async def message_garbage_clean(self) -> str:
        """清理所有已标记为垃圾的消息。

        Returns:
            清理结果消息
        """
        await self.count_invalidate_cache()
        if not self.garbage_message_ids:
            return "没有垃圾消息需要清理"

        for message_id in self.garbage_message_ids:
            if message_id in self.large_messages:
                msg = self.large_messages.pop(message_id)
                self.messages.remove(msg)

        self.garbage_message_ids.clear()

        return "已清理所有消息"

    def update_appending_message(self, message: str | None, source: str) -> None:
        """更新或移除appending message。

        Args:
            message: 消息内容，如果为None则移除对应source的消息
            source: 消息来源标识符，用于区分不同的appending messages
        """
        self.appending_messages = {
            msg for msg in self.appending_messages if msg.source != source
        }

        if message is not None:
            runtime_message = RuntimeMessage(message=message, source=source)
            self.appending_messages.add(runtime_message)

    def record_large_message(self, message: Message, _: str) -> str:
        """记录大消息并返回ID。

        Args:
            message: 大消息对象
            content: 消息内容

        Returns:
            分配的消息ID
        """
        message_id = generate_id("largemessage")
        self.large_messages[message_id] = message
        return message_id

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

    async def thanox_history(self) -> str:
        """随机删除一半消息（不包括前5条系统消息）。

        Returns:
            str: 删除结果消息
        """
        if len(self.messages) <= 10:
            return "消息数量不足，无需删除"

        await self.count_invalidate_cache()
        indices_to_delete = random.sample(
            range(5, len(self.messages)), len(self.messages) // 2
        )

        self.messages = [
            msg for idx, msg in enumerate(self.messages) if idx not in indices_to_delete
        ]

        return f"thanox_history: 随机删除了{len(indices_to_delete)}条消息"

    def add_soft_threshold_notification(
        self, threshold_info: tuple, large_messages: dict, compress_tool_called: bool
    ) -> None:
        """添加软限制消息提示。

        Args:
            threshold_info: 阈值信息元组 (soft, hard, used, remaining, taken)
            large_messages: 大消息字典
            compress_tool_called: 是否最近调用了压缩工具
        """
        if compress_tool_called:
            return

        if threshold_info:
            _soft, hard, used, _remaining, taken = threshold_info

            current_state = None
            if taken < 0.4:
                current_state = "绿灯"
            elif taken < 0.6:
                current_state = "绿灯闪烁"
            elif taken < 0.8:
                current_state = "黄灯"
            else:
                current_state = "红灯"

            if current_state == "绿灯" and self.last_threshold_state == "绿灯":
                return

            self.last_threshold_state = current_state

            if current_state == "绿灯":
                message_content = f"当前Token用量为{used}，硬限制为{hard}，当前使用{taken*100:.1f}%（绿灯状态）。当前已有{len(self.messages)}条消息。可以顺手标记大消息，无需担心token限制。"
            elif current_state == "绿灯闪烁":
                message_content = f"当前Token用量为{used}，硬限制为{hard}，当前使用{taken*100:.1f}%（绿灯闪烁状态）。当前已有{len(self.messages)}条消息。应该积极标记大消息，可以顺手删除一些实在和当前任务无关的消息。"
            elif current_state == "黄灯":
                message_content = f"当前Token用量为{used}，硬限制为{hard}，当前使用{taken*100:.1f}%（黄灯状态）。当前已有{len(self.messages)}条消息。积极考虑删除和当前任务无关的消息，也可以使用历史压缩删除之前任务的消息。"
            else:

                large_messages_info = ""
                if large_messages:
                    large_message_ids = list(large_messages.keys())[:3]
                    large_messages_info = f"当前已有{len(large_messages)}条大消息。前3个大消息ID: {', '.join(large_message_ids)}。"

                garbage_count = len(self.garbage_message_ids)
                if garbage_count >= 5:
                    action_guide = "当前有至少5条垃圾消息，建议调用message_garbage_clean清理垃圾消息。"
                else:
                    action_guide = "建议调用compress_history_range删除大约一半消息！"

                message_content = f"当前Token用量为{used}，硬限制为{hard}，当前使用{taken*100:.1f}%（红灯状态）。当前已有{len(self.messages)}条消息。{large_messages_info}{action_guide}"

            self.append_message(RuntimeMessage(message_content))

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
