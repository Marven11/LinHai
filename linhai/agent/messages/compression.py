import json

import linhai
from linhai.base import LanguageModelMessage, Message

from linhai.prompt import COMPRESS_RANGE_PROMPT


class MessagesListSummerizeMessage(Message):

    def __init__(
        self, messages_summerization: str, message_length: int, range_clean_id: str
    ):
        self.messages_summerization = messages_summerization
        self.message_length = message_length
        self.range_clean_id = range_clean_id
        self._valid = True

    def invalidate(self):
        self._valid = False

    def is_valid(self) -> bool:
        return self._valid

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": self.get_content(),
        }

    def get_content(self) -> str:
        if not self._valid:
            return f"[消息列表已无效，ID: {self.range_clean_id}]"
        prompt = COMPRESS_RANGE_PROMPT.replace(
            "{|SUGGESTED_MESSAGE_COUNT|}", str(int(self.message_length * 0.5))
        ).replace("{|SUMMERIZATION|}", self.messages_summerization)
        return (
            f"<<range_clean_summary>>\n"
            f"<<range_clean_id>>{self.range_clean_id}<<range_clean_id>>\n"
            f"<<message_count>>{self.message_length}<<message_count>>\n"
            f"<<content>>{prompt}<<content>>\n"
            f"<<range_clean_summary>>"
        )

    def to_json(self) -> str:
        data = {
            "messages_summerization": self.messages_summerization,
            "message_length": self.message_length,
            "range_clean_id": self.range_clean_id,
            "_valid": self._valid,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        instance = cls(
            messages_summerization=data["messages_summerization"],
            message_length=data["message_length"],
            range_clean_id=data["range_clean_id"],
        )
        instance._valid = data.get("_valid", True)
        return instance
