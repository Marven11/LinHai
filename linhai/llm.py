"""LLM模块，定义语言模型相关的消息类和协议。"""

from typing import Sequence, Protocol, TypedDict, AsyncIterator, cast, runtime_checkable
import asyncio
import json

from openai import AsyncOpenAI
from openai import OpenAIError
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionChunk
from linhai.type_hints import LanguageModelMessage, ToolMessage


@runtime_checkable
class Message(Protocol):
    """消息协议，定义消息类的接口。"""

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_llm_message()})"


class SystemMessage:
    """系统消息类，用于表示系统角色消息。"""

    def __init__(self, message: str):
        """初始化系统消息。"""
        self.message = message

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        return cast(LanguageModelMessage, {"role": "system", "content": self.message})

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return f"SystemMessage(message={self.message!r})"


class ChatMessage:
    """聊天消息类，用于表示用户或助理角色消息。"""

    def __init__(self, role: str, message: str, name: str | None = None):
        """初始化聊天消息。"""
        if role == "system":
            raise ValueError(
                "System role is not supported in ChatMessage. Use SystemMessage instead."
            )
        self.role = role
        self.message = message
        self.name = name

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        content = self.message
        if self.role == "user":
            content = f"<user>{content}</user>"
        msg = {"role": self.role, "content": content}
        if self.name is not None:
            msg["name"] = self.name
        return cast(LanguageModelMessage, msg)

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return f"ChatMessage(role={self.role!r}, message={self.message!r}, name={self.name!r})"


class ToolCallMessage:
    """工具调用消息类，用于表示助理调用工具的消息。"""

    def __init__(
        self,
        function_name: str = "",
        function_arguments: str | dict = "",
    ):
        """初始化工具调用消息。"""
        self.function_name = function_name
        if isinstance(function_arguments, dict):
            self.function_arguments = json.dumps(function_arguments)
        else:
            self.function_arguments = function_arguments

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        msg = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": self.function_name,
                        "arguments": self.function_arguments,
                    },
                }
            ],
        }
        return cast(ToolMessage, msg)

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return (
            f"ToolCallMessage(function_name={self.function_name!r}, "
            f"function_arguments={self.function_arguments!r})"
        )


class ToolConfirmationMessage:
    """工具确认消息类，用于表示用户对工具调用的确认消息。"""

    def __init__(
        self,
        tool_call: ToolCallMessage,
        confirmed: bool,
    ):
        """初始化工具确认消息。"""
        self.tool_call = tool_call
        self.confirmed = confirmed

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        return cast(
            LanguageModelMessage,
            {
                "role": "user",
                "content": f"<tool_confirmation>tool_call={self.tool_call.function_name}, "
                f"confirmed={self.confirmed}</tool_confirmation>",
            },
        )

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return (
            f"ToolConfirmationMessage(tool_call={self.tool_call!r}, "
            f"confirmed={self.confirmed!r})"
        )


class AnswerToken(TypedDict):
    """LLM回答的token表示，包含推理内容和普通内容。"""

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

    def get_current_content(self) -> str:
        """
        获取当前累积的回答内容
        """
        raise NotImplementedError


class LanguageModel(Protocol):
    """语言模型协议，定义语言模型的基本接口。"""

    async def answer_stream(
        self,
        history: Sequence[Message],
    ) -> Answer:
        """异步流式生成回答。

        参数:
            history: 消息历史序列

        返回:
            Answer: 回答对象
        """


class OpenAiAnswer:
    """OpenAI回答类，用于处理OpenAI API的流式响应。"""

    def __init__(self, stream):
        """初始化OpenAI回答。"""
        self._tokens = []
        self._reasoning_content = None
        self._content = ""
        self._stream = stream
        self._interrupted = False
        self.total_tokens = 0
        # 生成时会慢慢构造ToolCallMessage的每一个属性，除了argument
        self._tool_call: ToolCallMessage | None = None
        # 函数参数会以token形式一个个传过来
        self._tool_call_argument_json: str = ""

    def get_tool_call(self) -> ToolCallMessage | None:
        """在LLM生成完毕之后读取工具调用。"""
        return self._tool_call

    def __aiter__(self):
        """返回异步迭代器。"""
        return self

    async def __anext__(self):
        """获取下一个token。"""
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
                if tool_call.function and tool_call.function.name:
                    self._tool_call.function_name = tool_call.function.name
                if tool_call.function and tool_call.function.arguments:
                    self._tool_call.function_arguments += tool_call.function.arguments

            # 从chunk中提取token计数（如果API返回）
            if hasattr(chunk, "usage") and chunk.usage:
                self.total_tokens = chunk.usage.total_tokens

            token: AnswerToken = {
                "reasoning_content": getattr(delta, "reasoning_content", None),
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
        """获取完整的消息对象。"""
        if self._tool_call:
            return self._tool_call
        return ChatMessage(role="assistant", message=self._content)

    def get_reasoning_message(self) -> str | None:
        """获取推理消息（如果存在）。"""
        return None

    def interrupt(self):
        """中断当前回答的生成。"""
        self._interrupted = True

    def get_current_content(self) -> str:
        """获取当前累积的回答内容。"""
        return self._content

    def get_token_count(self) -> int:
        """获取当前回答的token总数。"""
        return self.total_tokens


class OpenAi:
    """OpenAI语言模型实现，用于与OpenAI API交互。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        openai_config: dict,
        tools: list[dict] | None = None,
    ):
        """初始化OpenAI语言模型。

        参数:
            api_key: OpenAI API密钥
            base_url: API基础URL
            model: 模型名称
            openai_config: 额外的OpenAI配置
            tools: 可用工具列表
        """
        self.model = model
        self.openai = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=10, **openai_config
        )
        self.tools = tools

    async def answer_stream(
        self,
        history: Sequence[Message],
    ) -> Answer:
        """异步流式生成回答。

        参数:
            history: 消息历史序列

        返回:
            Answer: 回答对象

        异常:
            ValueError: 如果history为空
            TimeoutError: 如果请求超时
            RuntimeError: 如果重试后仍失败
        """
        if not history:
            raise ValueError("history is empty")
        messages = [
            cast(ChatCompletionMessageParam, msg.to_llm_message()) for msg in history
        ]

        params = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.1,
        }

        if self.tools:
            params["tools"] = self.tools

        # 超时时间（秒）
        timeout_seconds = 30
        # 重试次数
        max_retries = 3
        retry_delay = 1  # 重试延迟，秒

        for attempt in range(max_retries):
            try:
                # 使用asyncio.wait_for添加超时
                stream = await asyncio.wait_for(
                    self.openai.chat.completions.create(**params),  # type: ignore
                    timeout=timeout_seconds,
                )
                return OpenAiAnswer(stream)
            except asyncio.TimeoutError:
                if attempt == max_retries - 1:
                    raise TimeoutError(
                        f"Request timed out after {timeout_seconds} seconds"
                    ) from None
                await asyncio.sleep(retry_delay)
            except OpenAIError:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(retry_delay)
        # 添加明确的返回语句
        raise RuntimeError("Failed to create OpenAI answer after retries")
