"""消息处理模块，负责管理Agent的消息队列和处理逻辑。"""

import logging
from typing import List, Optional, Sequence
from pathlib import Path
import json
import datetime
import random

from .base import Message, RuntimeMessage, DestroyedRuntimeMessage
from linhai.llm import ChatMessage
from linhai.input_parser import parse_user_input
from linhai.utils import generate_id

logger = logging.getLogger(__name__)


class AgentMessage:
    """消息处理器，负责管理消息队列和相关操作。"""

    def __init__(self, init_messages: Optional[Sequence[Message]] = None):
        """初始化消息处理器。
        
        Args:
            init_messages: 初始消息列表
        """
        self.messages: List[Message] = list(init_messages) if init_messages else []
        self.large_messages: dict[str, Message] = {}
        self.queued_messages: List[Message] = []

    def handle_user_message(self, msg: ChatMessage) -> None:
        """处理用户消息。
        
        Args:
            msg: 用户消息
        """
        assert isinstance(msg, ChatMessage) and msg.role == "user"

        content = msg.message.strip()
        parsed_input = parse_user_input(content)

        # 处理以@开头的消息（用于切换LLM）
        if parsed_input.switch_model:
            # 这个逻辑需要Agent上下文，所以这里只记录消息，具体处理在Agent中
            self.messages.append(msg)
            return

        self.messages.append(msg)

    def append_message(self, msg: Message) -> None:
        """添加消息到队列。
        
        Args:
            msg: 要添加的消息
        """
        self.messages.append(msg)

    def get_messages(self) -> List[Message]:
        """获取当前所有消息。
        
        Returns:
            消息列表
        """
        return self.messages

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
        return isinstance(msg, ChatMessage) and msg.role == "user"

    def erase_message_by_id(self, message_id: str) -> str:
        """擦除大消息。
        
        Args:
            message_id: 要擦除的消息ID
            
        Returns:
            擦除结果消息
        """
        if message_id not in self.large_messages:
            return f"错误：ID '{message_id}' 不存在，无法擦除消息。"

        message_to_delete = self.large_messages[message_id]
        del self.large_messages[message_id]

        if message_to_delete in self.messages:
            index = self.messages.index(message_to_delete)
            self.messages[index] = RuntimeMessage(f"本条ID为{message_id}的消息已被擦除")

        return f"已成功擦除ID为 '{message_id}' 的大消息"

    def record_large_message(self, message: Message, content: str) -> str:
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

    def thanox_history(self) -> str:
        """随机删除一半消息（不包括前5条系统消息）。
        
        Returns:
            str: 删除结果消息
        """
        if len(self.messages) <= 10:
            return "消息数量不足，无需删除"

        indices_to_delete = random.sample(
            range(5, len(self.messages)), len(self.messages) // 2
        )

        # 删除指定索引的消息
        self.messages = [
            msg for idx, msg in enumerate(self.messages)
            if idx not in indices_to_delete
        ]

        return f"thanox_history: 随机删除了{len(indices_to_delete)}条消息"

    def add_soft_threshold_notification(self, threshold_info: tuple, large_messages: dict, compress_tool_called: bool) -> None:
        """添加软限制消息提示。
        
        Args:
            threshold_info: 阈值信息元组 (soft, hard, used, remaining, taken)
            large_messages: 大消息字典
            compress_tool_called: 是否最近调用了压缩工具
        """
        if compress_tool_called:
            return
            
        if threshold_info:
            soft, hard, used, remaining, taken = threshold_info
            if used > soft:
                # 获取前3个大消息（按照插入顺序）
                large_messages_info = ""
                if large_messages:
                    large_message_ids = list(large_messages.keys())[:3]
                    large_messages_info = f"当前已有{len(large_messages)}条大消息。前3个大消息ID: {', '.join(large_message_ids)}。"
                
                self.messages.append(
                    RuntimeMessage(
                        f"当前Token用量为{used}，已达到软限制。硬限制为{hard}，当前使用{taken*100:.1f}%，还有{remaining} token直到强制压缩。"
                        f"当前已有{len(self.messages)}条消息。{large_messages_info}建议在消息条数少于200条时优先使用 erase_message_by_id. "
                    )
                )

    async def save_conversation_history(self, save_dir: Optional[Path] = None) -> None:
        """保存对话历史到文件。
        
        Args:
            save_dir: 保存目录，默认为用户home目录下的.linhai/history
        """
        if save_dir is None:
            save_dir = Path.home() / ".local" / "share" / "linhai" / "history"
        save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().isoformat().replace(":", "-")
        filename = f"conversation_{timestamp}.json"
        filepath = save_dir / filename

        history_data = []
        for msg in self.messages:
            if hasattr(msg, "to_json"):
                try:
                    to_json_result = msg.to_json()
                    import asyncio
                    if asyncio.iscoroutine(to_json_result):
                        to_json_result = await to_json_result
                    msg_dict = json.loads(to_json_result)
                    history_data.append(msg_dict)
                except (TypeError, ValueError, AttributeError):
                    continue

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            logger.info("对话历史已保存到: %s", filepath)
        except (IOError, OSError) as e:
            logger.error("保存对话历史失败: %s", str(e))