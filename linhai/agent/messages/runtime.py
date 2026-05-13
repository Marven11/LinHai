import json

import linhai
from linhai.base import LanguageModelMessage, Message, register_message

WAITING_USER_MARKER = "#LINHAI_WAITING_USER"


@register_message
class RuntimeMessage(Message):

    def __init__(self, message: str):
        self.message = message

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": self.get_content(),
        }

    def get_content(self) -> str:
        return f"<<runtime>>{self.message}<<runtime>>"

    def to_json(self) -> str:
        data = {"role": "user", "message": self.message}
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        return cls(message=data["message"])
