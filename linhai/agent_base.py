from linhai.llm import (
    Message,
    LanguageModelMessage,
)

from linhai.prompt import COMPRESS_HISTORY_PROMPT


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
            "content": prompt,
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
