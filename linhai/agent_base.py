from reprlib import Repr

from linhai.llm import (
    Message,
    LanguageModelMessage,
)

from linhai.prompt import COMPRESS_HISTORY_PROMPT, COMPRESS_RANGE_PROMPT

repr_obj = Repr(maxstring=100)


WAITING_USER_MARKER = "#LINHAI_WAITING_USER"


class CompressRequest(Message):
    """压缩请求消息，用于请求压缩历史消息。"""

    # pylint: disable=too-few-public-methods

    def __init__(self, messages_summerization: str):
        self.messages_summerization = messages_summerization

    def to_llm_message(self) -> LanguageModelMessage:
        prompt = COMPRESS_HISTORY_PROMPT.replace(
            "{|SUMMERIZATION|}", "\n".join(self.messages_summerization)
        )
        return {
            "role": "user",
            "content": f"<runtime>{prompt}</runtime>",
        }


class CompressRangeRequest(Message):

    # pylint: disable=too-few-public-methods

    def __init__(self, agent_messages: list):
        self.agent_messages = agent_messages

    def to_llm_message(self) -> LanguageModelMessage:
        if self.agent_messages[-1] is not self:
            return {
                "role": "user",
                "content": "<runtime>已经失效的compress_range_request prompt</runtime>",
            }
        messages = [msg.to_llm_message() for msg in self.agent_messages]
        messages_summerization = "\n".join(
            f"- id: {i} role: {msg["role"]!r} content: {repr_obj.repr(msg.get('content', None))}"
            for i, msg in enumerate(messages)
        )
        prompt = COMPRESS_RANGE_PROMPT.replace(
            "{|SUMMERIZATION|}", messages_summerization
        ).replace(
            "{|SUGGESTED_MESSAGE_COUNT|}", str(int(len(self.agent_messages) * 0.8))
        )
        return {
            "role": "user",
            "content": f"<runtime>{prompt}</runtime>",
        }


class RuntimeMessage(Message):
    """运行时消息，用于向LLM传递运行时信息。"""

    # pylint: disable=too-few-public-methods

    def __init__(self, message: str):
        self.message = message

    def to_llm_message(self) -> LanguageModelMessage:
        return {"role": "user", "content": f"<runtime>{self.message}</runtime>"}


class DestroyedRuntimeMessage(Message):
    """被截断的运行时消息，表示消息已被截断。"""

    # pylint: disable=too-few-public-methods

    def __init__(self):
        pass

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": "<destroyed><runtime>本条消息已被截断</runtime></destroyed>",
        }
