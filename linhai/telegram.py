"""Telegram消息模块，包含TelegramMessage类。"""

from typing import TYPE_CHECKING
import json

from linhai.llm import LanguageModelMessage, Message

if TYPE_CHECKING:
    from linhai.group_chat import GroupChat


class TelegramMessage(Message):
    """Telegram消息，用于表示来自telegram的消息。"""

    def __init__(self, chat_id: str, content: str, message_id: int = 0):
        self.chat_id = chat_id
        self.content = content
        self.message_id = message_id

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": self.get_content(),
        }

    def get_content(self) -> str:
        return f"<<telegram>>\n{self.content}\n<<telegram>>"

    def to_json(self) -> str:
        data = {
            "chat_id": self.chat_id,
            "content": self.content,
            "message_id": self.message_id,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, group_chat):
        data = json.loads(json_str)
        return cls(
            chat_id=data["chat_id"],
            content=data["content"],
            message_id=data["message_id"],
        )

    def __eq__(self, other: object) -> bool:
        """比较两个TelegramMessage是否相同。"""
        if not isinstance(other, TelegramMessage):
            return False
        return (
            self.chat_id == other.chat_id
            and self.content == other.content
            and self.message_id == other.message_id
        )

    def __hash__(self) -> int:
        """哈希支持，用于set比较。"""
        return hash((self.chat_id, self.content, self.message_id))

    def __str__(self) -> str:
        return f"TelegramMessage(chat_id={self.chat_id}, message_id={self.message_id})"
