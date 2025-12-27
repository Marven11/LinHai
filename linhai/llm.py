from __future__ import annotations
"""LLM模块，定义语言模型相关的消息类和协议。"""
from typing import (
    Sequence,
    Protocol,
    AsyncIterator,
    cast,
    runtime_checkable,
)
import asyncio
import json
import re

from pydantic import BaseModel
from openai import AsyncOpenAI
from openai import OpenAIError
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionChunk
from linhai.type_hints import LanguageModelMessage
from linhai.utils import CliRuntimeNotice
import linhai


@runtime_checkable
class Message(Protocol):
    """消息协议，定义消息类的接口。"""

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        raise NotImplementedError()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_llm_message()})"

    def to_json(self) -> str:
        """转换为JSON字符串。"""
        raise NotImplementedError()

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ) -> "Message":
        """从JSON字符串创建消息实例。"""
        raise NotImplementedError()


class SystemMessage:
    """系统消息类，用于表示系统角色消息。"""

    def __init__(
        self,
        group_chat: linhai.group_chat.GroupChat,
    ):
        """初始化系统消息。

        完全修改设计：group_chat必须提供，系统提示语通过结构化常量动态构建。
        template参数已移除，不再支持兼容模式。
        """
        self.group_chat = group_chat
        self.group_chat.register_member("system_message", self)

        from linhai.prompt import (
            INTRODUCTION_ITEMS,
            RULES_ITEMS,
            EXAMPLES_ITEMS,
            OVERVIEW,
        )

        self.overview = OVERVIEW
        self.introduction_items = INTRODUCTION_ITEMS.copy()
        self.rules_items = RULES_ITEMS.copy()
        self.examples_items = EXAMPLES_ITEMS.copy()


    def _build_prompt(self) -> str:
        """根据结构化常量构建完整的系统提示语。"""
        sections = []

        sections.append("# OVERVIEW")
        sections.append(self.overview)

        sections.append("# INTRODUCTION")
        for title, content in self.introduction_items:
            sections.append(f"## INTRODUCTION - {title}")
            sections.append(content)

        sections.append("# RULES")
        for title, content in self.rules_items:
            sections.append(f"## RULES - {title}")
            sections.append(content)

        sections.append("# EXAMPLES")
        for title, content in self.examples_items:
            sections.append(f"## EXAMPLES - {title}")
            sections.append(content)

        return "\n\n".join(sections)

    def add_introduction(self, title: str, content: str) -> None:
        """添加一个新的introduction章节。

        Args:
            title: 章节标题（只能包含大写英文字母数字和空格）
            content: 章节内容
        """
        if not re.match(r"^[A-Z0-9\s]+$", title):
            raise ValueError("标题只能包含大写英文字母数字和空格")
        self.introduction_items.append((title, content))

    def remove_introduction(self, title: str) -> None:
        """删除指定标题的introduction章节。

        Args:
            title: 要删除的章节标题
        """
        self.introduction_items = [
            (k, v) for (k, v) in self.introduction_items if k != title
        ]

    def add_rule(self, title: str, content: str) -> None:
        """添加一个新的rule章节。

        Args:
            title: 章节标题（只能包含大写英文字母数字和空格）
            content: 章节内容
        """
        if not re.match(r"^[A-Z0-9\s]+$", title):
            raise ValueError("标题只能包含大写英文字母数字和空格")
        self.rules_items.append((title, content))

    def remove_rule(self, title: str) -> None:
        """删除指定标题的rule章节。

        Args:
            title: 要删除的章节标题
        """
        self.rules_items = [
            (k, v) for (k, v) in self.rules_items if k != title
        ]

    def add_example(self, title: str, content: str) -> None:
        """添加一个新的example章节。

        Args:
            title: 章节标题（只能包含大写英文字母数字和空格）
            content: 章节内容
        """
        if not re.match(r"^[A-Z0-9\s]+$", title):
            raise ValueError("标题只能包含大写英文字母数字和空格")
        self.examples_items.append((title, content))

    def remove_example(self, title: str) -> None:
        """删除指定标题的example章节。

        Args:
            title: 要删除的章节标题
        """
        self.examples_items = [
            (k, v) for (k, v) in self.examples_items if k != title
        ]

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        prompt = self._build_prompt()
        return cast(LanguageModelMessage, {"role": "system", "content": prompt})

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return "SystemMessage()"

    def to_json(self) -> str:
        data = {
            "overview": self.overview,
            "introduction_items": self.introduction_items,
            "rules_items": self.rules_items,
            "examples_items": self.examples_items,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):
        data = json.loads(json_str)
        instance = cls(group_chat=group_chat)

        instance.overview = data["overview"]
        instance.introduction_items = data["introduction_items"]
        instance.rules_items = data["rules_items"]
        instance.examples_items = data["examples_items"]
        return instance


class SubagentSystemMessage:
    """系统消息类，用于表示系统角色消息。"""

    def __init__(
        self,
        msg: str,
    ):
        """初始化系统消息。"""
        self.msg = msg

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        return cast(LanguageModelMessage, {"role": "system", "content": self.msg})

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return "SubagentSystemMessage()"

    def to_json(self) -> str:

        return json.dumps({"msg": self.msg})

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        data = json.loads(json_str)

        return cls(
            msg=data["msg"],
        )


class UserMessage:
    """用户消息类，用于表示用户角色消息。"""

    def __init__(self, message: str, name: str | None = None):
        """初始化用户消息。"""
        self.message = message
        self.name = name

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        content = f"<<user>>{self.message}<<user>>"
        msg = {"role": "user", "name": "user", "content": content}
        if self.name is not None:
            msg["name"] = self.name
        return cast(LanguageModelMessage, msg)

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return f"UserMessage(message={self.message!r}, name={self.name!r})"

    def to_json(self) -> str:
        data = {
            "role": "user",
            "message": self.message,
            "name": self.name,
        }
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        _ = group_chat  # 使用参数以消除警告
        data = json.loads(json_str)
        return cls(message=data["message"], name=data.get("name"))


class AssistantMessage:
    """助理消息类，用于表示助理角色消息，支持reasoning content。"""

    def __init__(
        self,
        message: str,
        reasoning_message: str | None = None,
        name: str | None = None,
    ):
        """初始化助理消息。"""
        self.message = message
        self.reasoning_message = reasoning_message
        self.name = name

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        msg = {"role": "assistant", "name": "assistant", "content": self.message}
        if self.name is not None:
            msg["name"] = self.name
        return cast(LanguageModelMessage, msg)

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return f"AssistantMessage(message={self.message!r}, reasoning_message={self.reasoning_message!r}, name={self.name!r})"

    def to_json(self) -> str:
        data = {
            "role": "assistant",
            "message": self.message,
            "reasoning_message": self.reasoning_message,
            "name": self.name,
        }
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        _ = group_chat  # 使用参数以消除警告
        data = json.loads(json_str)
        return cls(
            message=data["message"],
            reasoning_message=data.get("reasoning_message"),
            name=data.get("name"),
        )


class ToolCallMessage:
    """工具调用消息类，用于表示助理调用工具的消息。"""

    def __init__(
        self,
        function_name: str,
        function_arguments: dict,
        assert_success: bool = True,
    ):
        """初始化工具调用消息。"""
        self.function_name = function_name
        self.assert_success = assert_success
        self.function_arguments = function_arguments

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return (
            f"ToolCallMessage(function_name={self.function_name!r}, "
            f"function_arguments={self.function_arguments!r}, "
            f"assert_success={self.assert_success!r})"
        )


class AnswerToken(BaseModel):
    """LLM回答的token表示，包含推理内容和普通内容。"""

    reasoning_content: str | None = None
    content: str


class AnswerTokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int | None = None


@runtime_checkable
class Answer(Protocol):
    """
    LLM的一个回答
    """

    def __aiter__(self) -> AsyncIterator[AnswerToken | AnswerTokenUsage]:
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

    def truncate(self) -> None:
        """
        截断当前回答的生成，相当于提前帮LLM结束输出
        与interrupt的区别：
        - interrupt是中断输出，本次输出失败，其中的工具调用等信息都不会被处理
        - truncate是提前结束输出，流程继续，就像LLM正常停止输出一样
        """
        raise NotImplementedError

    def get_current_content(self) -> str:
        """
        获取当前累积的回答内容
        """
        raise NotImplementedError

    def get_token_usage(self) -> AnswerTokenUsage | None:
        """获取token使用情况，返回包含'input_tokens', 'output_tokens', 'total_tokens'的字典，如果不可用返回None。"""
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
        raise NotImplementedError()

    def get_token_limit(self) -> int | None:
        """获取当前LLM的token限制。

        返回:
            int | None: token限制数量，如果没有配置则返回None
        """
        raise NotImplementedError()


class OpenAiAnswer:
    """OpenAI回答类，用于处理OpenAI API的流式响应。"""

    def __init__(
        self,
        stream,
        group_chat: linhai.group_chat.GroupChat,
        compatibility: str | None = None,
        cached_input_tokens: int = 0,
    ):
        """初始化OpenAI回答。"""
        self.tokens = []
        self.reasoning_content = None
        self.content = ""
        self.stream = stream
        self.interrupted = False
        self.truncated = False
        self.compatibility = compatibility
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.group_chat = group_chat
        self.cached_input_tokens = cached_input_tokens
        self.toyield: list[AnswerToken | AnswerTokenUsage] = []

    def __aiter__(self):
        """返回异步迭代器。"""
        return self

    async def update_toyield(self):
        """获取下一个token。"""
        if self.interrupted or self.truncated:
            raise StopAsyncIteration

        try:

            chunk = cast(ChatCompletionChunk, await self.stream.__anext__())

            if self.interrupted:
                await self.stream.close()

                raise StopAsyncIteration

            if hasattr(chunk, "usage") and chunk.usage:
                usage = chunk.usage

                self.input_tokens = (
                    usage.prompt_tokens if hasattr(usage, "prompt_tokens") else 0
                )

                self.output_tokens = (
                    usage.completion_tokens
                    if hasattr(usage, "completion_tokens")
                    else 0
                )
                self.total_tokens = (
                    usage.total_tokens if hasattr(usage, "total_tokens") else 0
                )
                # Send token usage directly to CLI queue instead of through agent
                await self.group_chat.send(
                    "token_usage",
                    AnswerTokenUsage(
                        input_tokens=self.input_tokens,
                        output_tokens=self.output_tokens,
                        total_tokens=self.total_tokens,
                        cached_input_tokens=self.cached_input_tokens,
                    ),
                )
            if len(chunk.choices) == 0:
                return
            delta = chunk.choices[0].delta
            content = delta.content or ""
            self.content += content

            reasoning_content = getattr(delta, "reasoning_content", None)
            if reasoning_content:
                assert isinstance(reasoning_content, str)
                self.reasoning_content = (
                    self.reasoning_content + reasoning_content
                    if self.reasoning_content
                    else reasoning_content
                )

            reasoning_details = (
                getattr(delta, "reasoning_details", None)
                if self.compatibility == "minimax"
                else None
            )
            if reasoning_details and isinstance(reasoning_details, list):
                for detail in reasoning_details:
                    if "text" in detail and isinstance(detail["text"], str):
                        reasoning_content = detail["text"]
                        self.reasoning_content = (
                            reasoning_content
                            if self.reasoning_content is None
                            else self.reasoning_content + reasoning_content
                        )

            token = AnswerToken(
                reasoning_content=reasoning_content,
                content=content,
            )
            self.toyield.append(token)
        except StopAsyncIteration:
            raise
        except asyncio.CancelledError as exc:
            self.interrupted = True
            raise StopAsyncIteration from exc
        except Exception as exc:
            self.interrupted = True
            raise StopAsyncIteration from exc

    async def __anext__(self) -> AnswerToken | AnswerTokenUsage:
        if not self.toyield:
            await self.update_toyield()
        return self.toyield.pop(0)

    def get_message(self) -> Message:
        """获取完整的消息对象。"""
        return AssistantMessage(
            message=self.content, reasoning_message=self.reasoning_content
        )

    def get_reasoning_message(self) -> str | None:
        """获取推理消息（如果存在）。"""
        return self.reasoning_content

    def interrupt(self):
        """中断当前回答的生成。"""
        self.interrupted = True
        self.toyield.clear()

    def truncate(self):
        """截断当前回答的生成。"""
        self.truncated = True
        self.toyield.clear()

    def get_current_content(self) -> str:
        """获取当前累积的回答内容。"""
        return self.content

    def get_token_count(self) -> int:
        """获取当前回答的token总数。"""
        return self.total_tokens

    def get_token_usage(self) -> AnswerTokenUsage | None:
        """获取token使用情况，返回包含'input_tokens', 'output_tokens', 'total_tokens'的字典，如果不可用返回None。"""
        if self.total_tokens == 0:
            return None
        return AnswerTokenUsage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.total_tokens,
            cached_input_tokens=self.cached_input_tokens,
        )


class OpenAi:
    """OpenAI语言模型实现，用于与OpenAI API交互。"""

    def __init__(
        self,
        *,
        group_chat: linhai.group_chat.GroupChat,
        api_key: str,
        base_url: str,
        model: str,
        openai_config: dict,
        chat_completion_kwargs: dict,
        tools: list[dict] | None = None,
        token_limit: int | None = None,
        compatibility: str | None = None,
    ):
        """初始化OpenAI语言模型。

        参数:
            group_chat: GroupChat实例，用于发送通知和协调组件
            api_key: OpenAI API密钥
            base_url: API基础URL
            model: 模型名称
            openai_config: 额外的OpenAI配置
            chat_completion_kwargs: 聊天补全额外参数
            tools: 可用工具列表
            token_limit: token限制数量
            compatibility: API兼容性模式，支持minimax、kimi等
        """
        self.group_chat = group_chat
        self.model = model
        self.openai = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=10, **openai_config
        )
        self.tools = tools
        self.chat_completion_kwargs = chat_completion_kwargs
        self.token_limit = token_limit
        self.compatibility = compatibility
        self.previous_history: Sequence[Message] | None = None
        self.previous_input_tokens: int | None = None



    def get_token_limit(self) -> int | None:
        """获取当前LLM的token限制。

        返回:
            int | None: token限制数量，如果没有配置则返回None
        """
        return self.token_limit

    def _estimate_cached_input_tokens(self, current_history: Sequence[Message]) -> int:
        """估算缓存的输入token数量。

        将上一个history和当前history的所有内容拼接成字符串，
        然后按64字符块对比相同前缀，计算缓存比例。
        """
        if self.previous_history is None or self.previous_input_tokens is None:
            return 0

        previous_content = "".join(
            msg.to_llm_message().get("content", "") for msg in self.previous_history
        )
        current_content = "".join(
            msg.to_llm_message().get("content", "") for msg in current_history
        )

        same_prefix_chars = 0
        block_size = 64

        for i in range(0, min(len(previous_content), len(current_content)), block_size):

            if (
                previous_content[i : i + block_size]
                == current_content[i : i + block_size]
            ):
                same_prefix_chars += block_size
            else:
                break

        if len(previous_content) > 0:
            cached_ratio = same_prefix_chars / len(previous_content)
            cached_tokens = int(self.previous_input_tokens * cached_ratio)
            return max(0, cached_tokens)

        return 0

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

        cached_input_tokens = 0
        if self.previous_input_tokens is not None:
            cached_input_tokens = self._estimate_cached_input_tokens(history)

        params = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.1,
            "timeout": 30,
            **self.chat_completion_kwargs,
        }

        if self.compatibility == "minimax":
            params["extra_body"] = {"reasoning_split": True}

        if self.compatibility == "kimi":
            params["stream_options"] = {"include_usage": True}

        if self.tools:
            params["tools"] = self.tools

        retry_delay = 5

        answer = None
        while True:
            try:
                stream = await self.openai.chat.completions.create(**params)

                
                answer = OpenAiAnswer(
                    stream,
                    group_chat=self.group_chat,
                    compatibility=self.compatibility,
                    cached_input_tokens=cached_input_tokens,

                )
                break
            except (asyncio.TimeoutError, OpenAIError):

                await self.group_chat.send(
                    "ui_log",
                    CliRuntimeNotice(
                        "WARNING",
                        f"API调用失败，将在约{retry_delay:.1f}秒后重试",
                    ),
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 1.5
                retry_delay = min(retry_delay, 300)

        if answer is not None:
            self.previous_history = history
            return answer
        else:
            raise RuntimeError("Failed to create OpenAI answer after retries")
