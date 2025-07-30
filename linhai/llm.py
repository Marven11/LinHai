from typing import (
    Sequence,
    Protocol,
    TypedDict,
    AsyncIterator,
)
from typing import cast
import asyncio


from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from linhai.type_hints import ChatCompletionMessageParam as LHChatMessage


class Message(Protocol):
    def to_chat_message(self) -> LHChatMessage: ...


class ChatMessage:
    def __init__(self, role: str, message: str, name: str | None = None):
        self.role = role
        self.message = message
        self.name = name

    def to_chat_message(self) -> LHChatMessage:
        msg = {"role": self.role, "content": self.message}
        if self.name is not None:
            msg["name"] = self.name
        return cast(LHChatMessage, msg)


class AnswerToken(TypedDict):
    reasoning_content: str | None
    content: str


class Answer(Protocol):
    """
    LLM的一个回答
    """

    def __aiter__(self) -> AsyncIterator[AnswerToken]:
        """
        流式返回LLM的回答
        iterator中的每个item是一个token
        """
        raise NotImplementedError

    def get_message(self) -> ChatMessage:
        """
        在LLM生成完毕之后读取LLM本次的回答
        返回一个role=assitant的ChatMessage
        """
        raise NotImplementedError

    def get_reasoning_message(self) -> str | None:
        """
        在LLM生成完毕之后读取LLM本次的回答
        返回一个str, 如果LLM不是推理LLM则返回None
        """
        raise NotImplementedError

    def interrupt(self) -> None:
        """
        中断当前回答的生成
        """
        raise NotImplementedError


class LanguageModel(Protocol):
    async def answer_stream(
        self,
        history: Sequence[Message],
    ) -> Answer: ...


class OpenAiAnswer:
    def __init__(self, stream):
        self._tokens = []
        self._reasoning_content = None
        self._content = ""
        self._stream = stream
        self._interrupted = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._interrupted:
            raise StopAsyncIteration

        try:
            # 获取下一个chunk
            chunk = await self._stream.__anext__()
            if self._interrupted:
                raise StopAsyncIteration

            delta = chunk.choices[0].delta
            content = delta.content or ""
            self._content += content
            token: AnswerToken = {
                "reasoning_content": None,
                "content": content,
            }
            return token
        except StopAsyncIteration:
            raise
        except asyncio.CancelledError as exc:
            self._interrupted = True
            raise StopAsyncIteration from exc
        except Exception as exc:
            self._interrupted = True
            raise StopAsyncIteration from exc

    def get_message(self) -> ChatMessage:
        return ChatMessage(role="assistant", message=self._content)

    def get_reasoning_message(self) -> str | None:
        return None

    def interrupt(self):
        """中断当前回答的生成"""
        self._interrupted = True


class OpenAi:
    def __init__(self, *, api_key: str, base_url: str, model: str, openai_config: dict):
        self.model = model
        self.openai = AsyncOpenAI(api_key=api_key, base_url=base_url, **openai_config)

    async def answer_stream(
        self,
        history: Sequence[Message],
    ) -> Answer:
        messages = [
            cast(ChatCompletionMessageParam, msg.to_chat_message()) for msg in history
        ]
        stream = await self.openai.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        )

        return OpenAiAnswer(stream)
