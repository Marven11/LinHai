from typing import Sequence, Protocol, TypedDict, AsyncIterator, Optional, Literal
from typing import cast
import asyncio


from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionChunk
from linhai.type_hints import LanguageModelMessage, ToolMessage


class Message(Protocol):
    def to_chat_message(self) -> LanguageModelMessage: ...


    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_chat_message()})"


class ChatMessage:
    def __init__(self, role: str, message: str, name: str | None = None):
        self.role = role
        self.message = message
        self.name = name

    def to_chat_message(self) -> LanguageModelMessage:
        msg = {"role": self.role, "content": self.message}
        if self.name is not None:
            msg["name"] = self.name
        return cast(LanguageModelMessage, msg)

    def __repr__(self) -> str:
        return f"ChatMessage(role={self.role!r}, message={self.message!r}, name={self.name!r})"

class ToolCallMessage:
    def __init__(
        self,
        index: int = 0,
        id: Optional[str] = None,
        function_name: str = "",
        function_arguments: str = "",
        type: Optional[Literal["function"]] = None,
    ):
        self.index = index
        self.id = id
        self.function_name = function_name
        self.function_arguments = function_arguments
        self.type = type

    def to_chat_message(self) -> LanguageModelMessage:
        msg = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "index": self.index,
                    "id": self.id,
                    "function": {
                        "name": self.function_name,
                        "arguments": self.function_arguments,
                    },
                    "type": self.type,
                }
            ],
        }
        return cast(ToolMessage, msg)


class AnswerToken(TypedDict):
    reasoning_content: str | None
    content: str


class Answer(Protocol):
    """
    LLM的一个回答
    """

    def get_tool_call(self) -> ToolCallMessage | None:
        """
        在LLM生成完毕之后读取工具调用
        """
        raise NotImplementedError

    def __aiter__(self) -> AsyncIterator[AnswerToken]:
        """
        流式返回LLM的回答
        iterator中的每个item是一个token
        """
        raise NotImplementedError

    def get_message(self) -> Message:
        """
        在LLM生成完毕之后读取LLM本次的回答
        返回一个role=assitant的Message
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
        # 生成时会慢慢构造ToolCallMessage的每一个属性，除了argument
        self._tool_call: ToolCallMessage | None = None
        # 函数参数会以token形式一个个传过来
        self._tool_call_argument_json: str = ""

    def get_tool_call(self) -> ToolCallMessage | None:
        """在LLM生成完毕之后读取工具调用"""
        return self._tool_call

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._interrupted:
            raise StopAsyncIteration

        try:
            # 获取下一个chunk
            chunk = cast(ChatCompletionChunk, await self._stream.__anext__())

            if self._interrupted:
                raise StopAsyncIteration

            delta = chunk.choices[0].delta
            content = delta.content or ""
            self._content += content

            # 检查是否有工具调用
            if delta.tool_calls:
                tool_call = delta.tool_calls[0]
                if not self._tool_call:
                    self._tool_call = ToolCallMessage()
                if tool_call.index:
                    self._tool_call.index = tool_call.index
                if tool_call.id:
                    self._tool_call.id = tool_call.id
                if tool_call.type:
                    self._tool_call.type = tool_call.type
                if tool_call.function and tool_call.function.name:
                    self._tool_call.function_name = tool_call.function.name

                if tool_call.function and tool_call.function.arguments:
                    self._tool_call.function_arguments += tool_call.function.arguments

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

    def get_message(self) -> Message:
        if self._tool_call:
            return self._tool_call
        return ChatMessage(role="assistant", message=self._content)

    def get_reasoning_message(self) -> str | None:
        return None

    def interrupt(self):
        """中断当前回答的生成"""
        self._interrupted = True


class OpenAi:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        openai_config: dict,
        tools: list[dict] | None = None
    ):
        self.model = model
        self.openai = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=10, **openai_config
        )
        self.tools = tools

    async def answer_stream(
        self,
        history: Sequence[Message],
    ) -> Answer:
        if not history:
            raise ValueError("history is empty")
        messages = [
            cast(ChatCompletionMessageParam, msg.to_chat_message()) for msg in history
        ]

        params = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        if self.tools:
            params["tools"] = self.tools

        stream = await self.openai.chat.completions.create(**params)
        return OpenAiAnswer(stream)
