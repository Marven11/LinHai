import json

import linhai
from linhai.base import LanguageModelMessage, Message, register_message


@register_message
class PreviousReasoningMessage(Message):

    def __init__(self, reasoning_contents: list[str]):
        self.reasoning_contents = reasoning_contents

    def to_llm_message(self) -> LanguageModelMessage:
        return {"role": "user", "content": self.get_content()}

    def get_content(self) -> str:
        if not self.reasoning_contents:
            return ""
        content_parts = []
        for reasoning_content in self.reasoning_contents:
            content_parts.append(f"<<content>>{reasoning_content}<<content>>")
        return (
            "<<previous_reasoning>><<message>>这是你之前的思考内容，仅做参考<<message>>"
            + "".join(content_parts)
            + "<<previous_reasoning>>"
        )

    def to_json(self) -> str:
        data = {"reasoning_contents": self.reasoning_contents}
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        return cls(reasoning_contents=data["reasoning_contents"])


@register_message
class SpoofedReasoningMessage(Message):

    def __init__(self, reasoning_contents: list[str]):
        self.reasoning_contents = reasoning_contents

    def to_llm_message(self) -> LanguageModelMessage:
        reasoning_content = "\n".join(self.reasoning_contents)

        return {
            "role": "assistant",
            "content": "",
            "reasoning_content": reasoning_content,
        }

    def get_content(self) -> str:
        return ""

    def to_json(self) -> str:
        data = {"reasoning_contents": self.reasoning_contents}
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        return cls(reasoning_contents=data["reasoning_contents"])
