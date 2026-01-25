"""对话管理系统，负责对话历史的保存、恢复和管理。"""

import json
import uuid
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from linhai.group_chat import GroupChat
from linhai.llm import Message


class ConversationManager:
    """对话管理器，负责管理单个对话的文件夹、消息历史和清理归档。"""

    def __init__(self, conversation_id: Optional[str] = None):
        """初始化对话管理器。

        Args:
            conversation_id: 对话ID，如果为None则生成新的UUID
        """
        if conversation_id is None:
            self.conversation_id = str(uuid.uuid4())
        else:
            self.conversation_id = conversation_id

        self.base_dir = Path.home() / ".local" / "share" / "conversation"
        self.conversation_dir = self.base_dir / self.conversation_id
        self.context_file = self.conversation_dir / "context.json"
        self.splited_large_message_dir = self.conversation_dir / "splited_large_message"
        self.cleaned_messages_dir = self.conversation_dir / "cleaned_messages"

        self.conversation_dir.mkdir(parents=True, exist_ok=True)
        self.splited_large_message_dir.mkdir(parents=True, exist_ok=True)
        self.cleaned_messages_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_conversation_dir(cls, conversation_id: str) -> Path:
        """获取对话文件夹路径。

        其他模块通过此方法获取路径，避免硬编码。
        """
        base_dir = Path.home() / ".local" / "share" / "conversation"
        return base_dir / conversation_id

    def save_context(self, messages: List[Message]) -> str:
        """保存消息列表到context.json文件。

        Args:
            messages: 消息列表

        Returns:
            保存的文件路径
        """
        # 使用列表推导式构建数据，更高效
        history_data = [
            {"type": msg.__class__.__name__, "data": msg.to_json()}
            for msg in messages
        ]

        with open(self.context_file, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        return str(self.context_file)

    def load_context(self, group_chat: Optional[GroupChat] = None) -> List[Message]:
        """从context.json文件加载消息列表。

        Args:
            group_chat: GroupChat实例，用于消息反序列化

        Returns:
            消息列表

        Raises:
            FileNotFoundError: 如果context.json文件不存在
            json.JSONDecodeError: 如果JSON解析失败
            RuntimeError: 如果没有提供group_chat参数
        """
        if not self.context_file.exists():
            raise FileNotFoundError(f"Context file not found: {self.context_file}")

        if group_chat is None:
            raise RuntimeError("ConversationManager.load_context需要GroupChat参数")

        with open(self.context_file, "r", encoding="utf-8") as f:
            history_data = json.load(f)

        messages = []
        for wrapped_msg in history_data:
            msg_type = wrapped_msg.get("type")
            json_str = wrapped_msg.get("data", "")
            if msg_type == "RuntimeMessage":
                from linhai.agent.base import RuntimeMessage

                msg = RuntimeMessage.from_json(json_str, group_chat)
            elif msg_type == "UserMessage":
                from linhai.llm import UserMessage

                msg = UserMessage.from_json(json_str, group_chat)
            elif msg_type == "AssistantMessage":
                from linhai.llm import AssistantMessage

                msg = AssistantMessage.from_json(json_str, group_chat)
            elif msg_type == "ToolCallMessage":
                from linhai.llm import ToolCallMessage

                try:
                    data = json.loads(json_str)
                    msg = ToolCallMessage(
                        function_name=data.get("function_name", ""),
                        function_arguments=data.get("function_arguments", {}),
                        assert_success=data.get("assert_success", True),
                        with_secret=data.get("with_secret", None),
                        on_machine=data.get("on_machine", None),
                    )
                except Exception:
                    from linhai.agent.base import RuntimeMessage

                    msg = RuntimeMessage("无法恢复ToolCallMessage消息")
            elif msg_type == "SystemMessage":
                from linhai.llm import SystemMessage

                msg = SystemMessage.from_json(json_str, group_chat)
            elif msg_type == "ToolCallResultMessage":
                from linhai.tool.base import ToolCallResultMessage

                msg = ToolCallResultMessage.from_json(json_str, group_chat)
            elif msg_type == "FileContentMessage":
                from linhai.agent.base import FileContentMessage

                msg = FileContentMessage.from_json(json_str, group_chat)
            elif msg_type == "GlobalMemory":
                from linhai.agent.base import GlobalMemory

                msg = GlobalMemory.from_json(json_str, group_chat)
            elif msg_type == "PathMemory":
                from linhai.agent.base import PathMemory

                msg = PathMemory.from_json(json_str, group_chat)
            elif msg_type == "ChecklistMessage":
                from linhai.agent.base import ChecklistMessage

                msg = ChecklistMessage.from_json(json_str, group_chat)
            elif msg_type == "CompressRangeRequest":
                from linhai.agent.base import CompressRangeRequest

                msg = CompressRangeRequest.from_json(json_str, group_chat)
            else:

                from linhai.agent.base import RuntimeMessage

                msg = RuntimeMessage(f"无法恢复未知类型的消息: {msg_type}")

            messages.append(msg)

        return messages

    def save_cleaned_messages(
        self, messages: List[Message], prefix: str = "cleaned"
    ) -> str:
        """保存被清理的消息到cleaned_messages目录。

        Args:
            messages: 被清理的消息列表
            prefix: 文件名前缀

        Returns:
            保存的文件路径
        """
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.json"
        filepath = self.cleaned_messages_dir / filename

        # 使用列表推导式构建数据，更高效
        history_data = [
            {"type": msg.__class__.__name__, "data": msg.to_json()}
            for msg in messages
        ]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        return str(filepath)

    def save_large_message_chunk(self, content: str, chunk_index: int) -> str:
        """保存大消息分块到splited_large_message目录。

        Args:
            content: 消息内容
            chunk_index: 分块索引

        Returns:
            保存的文件路径
        """
        timestamp = int(time.time())
        filename = f"large_message_{timestamp}_{chunk_index}.txt"
        filepath = self.splited_large_message_dir / filename

        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def get_conversation_id(self) -> str:
        """获取对话ID。"""
        return self.conversation_id


_current_conversation: Optional[ConversationManager] = None


def init_conversation(conversation_id: Optional[str] = None) -> ConversationManager:
    """初始化对话管理器。

    Args:
        conversation_id: 对话ID，如果为None则创建新的对话

    Returns:
        ConversationManager实例
    """
    global _current_conversation
    _current_conversation = ConversationManager(conversation_id)
    return _current_conversation


def get_current_conversation() -> ConversationManager:
    """获取当前对话管理器。

    Returns:
        当前ConversationManager实例linhai/agent/conversation.py

    Raises:
        RuntimeError: 如果对话未初始化
    """
    global _current_conversation
    if _current_conversation is None:
        raise RuntimeError(
            "Conversation not initialized. Call init_conversation first."
        )
    return _current_conversation
