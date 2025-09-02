from reprlib import Repr

from linhai.llm import (
    Message,
    LanguageModelMessage,
)

from linhai.prompt import COMPRESS_RANGE_PROMPT

repr_obj = Repr(maxstring=100)


WAITING_USER_MARKER = "#LINHAI_WAITING_USER"


class CompressRangeRequest(Message):

    def __init__(self, messages_summerization: str, message_length: int):
        self.messages_summerization = messages_summerization
        self.message_length = message_length

    def to_llm_message(self) -> LanguageModelMessage:

        prompt = COMPRESS_RANGE_PROMPT.replace(
            "{|SUMMERIZATION|}", self.messages_summerization
        ).replace("{|SUGGESTED_MESSAGE_COUNT|}", str(int(self.message_length * 0.8)))
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
