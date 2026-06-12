"""LLM基础数据类定义，包含消息类、Token模型和协议。"""

from __future__ import annotations

from typing import (
    Any,
    Sequence,
    Protocol,
    AsyncIterator,
    runtime_checkable,
)

import json
import re

from pydantic import BaseModel

from linhai.type_hints import (
    LanguageModelMessage,
    OpenAiToolCall,
    OpenAiToolCallResult,
    UserMessage as UserMsgType,
    AssistantMessage as AsstMsgType,
    ToolResultMsg,
    WithSecret,
)

import linhai


class ExplicitCacheInfo(BaseModel):
    cache_write_price_ratio: float
    cache_hit_price_ratio: float


@runtime_checkable
class Message(Protocol):
    """消息协议，定义消息类的接口。"""

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        raise NotImplementedError()

    def get_content(self) -> str | None:
        """获取消息的文本内容。

        返回str或None：如果消息的content是简单的字符串则返回该字符串；
        如果content不是简单字符串（如图片内容）则返回None。
        """
        raise NotImplementedError()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_llm_message()})"

    def to_json(self) -> str:
        """转换为JSON字符串。"""
        raise NotImplementedError()

    @classmethod
    def from_json(
        cls, json_str: str, registry: "linhai.registry.Registry"
    ) -> "Message":
        """从JSON字符串创建消息实例。"""
        raise NotImplementedError()


@runtime_checkable
class EstimateToken(Protocol):
    """可估算token数量的消息协议。"""

    def estimated_tokens(self) -> int:
        raise NotImplementedError()


MESSAGE_CLASS_REGISTRY: dict[str, type] = {}


def register_message(cls):
    MESSAGE_CLASS_REGISTRY[cls.__name__] = cls
    return cls


@register_message
class SystemMessage:
    """系统消息类，用于表示系统角色消息。"""

    def __init__(
        self,
        registry: linhai.registry.Registry,
    ):
        """初始化系统消息。

        完全修改设计：registry必须提供，系统提示语通过结构化常量动态构建。
        template参数已移除，不再支持兼容模式。
        """
        self.registry = registry
        self.registry.register_member("system_message", self)

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

    def get_content(self) -> str:
        """获取消息的文本内容。"""
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
        self.rules_items = [(k, v) for (k, v) in self.rules_items if k != title]

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
        self.examples_items = [(k, v) for (k, v) in self.examples_items if k != title]

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        prompt = self.get_content()
        return {"role": "system", "content": prompt}

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
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        instance = cls(registry=registry)

        instance.overview = data["overview"]
        instance.introduction_items = data["introduction_items"]
        instance.rules_items = data["rules_items"]
        instance.examples_items = data["examples_items"]
        return instance

    def serialize(self) -> dict:
        return {
            "overview": self.overview,
            "introduction_items": self.introduction_items,
            "rules_items": self.rules_items,
            "examples_items": self.examples_items,
        }

    def restore_from(self, data: dict) -> None:
        self.overview = data["overview"]
        self.introduction_items = data["introduction_items"]
        self.rules_items = data["rules_items"]
        self.examples_items = data["examples_items"]


@register_message
class UserMessage:
    """用户消息类，用于表示用户角色消息。"""

    def __init__(self, message: str, name: str | None = None):
        """初始化用户消息。"""
        self.message = message
        self.name = name

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        return UserMsgType(role="user", content=self.get_content())

    def get_content(self) -> str:
        """获取消息的文本内容。"""
        return f"<<user>>{self.message}<<user>>"

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return f"UserMessage(message={self.message!r}, name={self.name!r})"

    def to_json(self) -> str:
        data = {
            "role": "user",
            "message": self.message,
        }
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        return cls(message=data["message"], name=data.get("name"))


@register_message
class AssistantMessage:
    """助理消息类，用于表示助理角色消息，支持reasoning content。"""

    def __init__(
        self,
        message: str | None,
        reasoning_message: str | None = None,
        name: str | None = None,
    ):
        """初始化助理消息。

        Args:
            message: 助理消息文本内容，None表示API未返回content字段
            reasoning_message: 推理内容
            name: 消息来源名称
        """
        self.message = message
        self.reasoning_message = reasoning_message
        self.name = name
        self.tool_calls: list[OpenAiToolCall] | None = None

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        result: AsstMsgType = AsstMsgType(role="assistant")
        if self.message is not None:
            result["content"] = self.message
        if self.reasoning_message:
            result["reasoning_content"] = self.reasoning_message
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        return result

    def get_content(self) -> str | None:
        """获取消息的文本内容。

        返回str或None：None表示API未返回content字段。
        """
        return self.message

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return f"AssistantMessage(message={self.message!r}, reasoning_message={self.reasoning_message!r}, name={self.name!r}, tool_calls={self.tool_calls!r})"

    def to_json(self) -> str:
        data: dict[str, Any] = {
            "role": "assistant",
            "message": self.message,
            "reasoning_message": self.reasoning_message,
        }
        if self.tool_calls:
            data["tool_calls"] = self.tool_calls
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        msg = cls(
            message=data["message"],
            reasoning_message=data.get("reasoning_message"),
            name=data.get("name"),
        )
        msg.tool_calls = data.get("tool_calls")
        return msg


@register_message
class OpenAiToolResultMessage:
    """OpenAI原生工具调用结果消息，用于在多轮对话中传递工具执行结果。"""

    def __init__(self, tool_call_id: str, content: str, tool_name: str):
        self.tool_call_id = tool_call_id
        self.content = content
        self.tool_name = tool_name

    def to_llm_message(self) -> LanguageModelMessage:
        return ToolResultMsg(
            role="tool",
            tool_call_id=self.tool_call_id,
            content=self.content,
        )

    def get_content(self) -> str:
        return self.content

    def __repr__(self) -> str:
        return f"OpenAiToolResultMessage(tool_call_id={self.tool_call_id!r}, content={self.content!r})"

    def to_json(self) -> str:
        return json.dumps(
            {
                "role": "tool",
                "tool_call_id": self.tool_call_id,
                "content": self.content,
                "tool_name": self.tool_name,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        return cls(
            tool_call_id=data["tool_call_id"],
            content=data["content"],
            tool_name=data["tool_name"],
        )


class ToolCallMessage:
    """工具调用消息类，用于表示助理调用工具的消息。"""

    def __init__(
        self,
        function_name: str,
        function_arguments: dict,
        assert_success: bool,
        with_secret: WithSecret | None,
    ):
        """初始化工具调用消息。"""
        self.function_name = function_name
        self.assert_success = assert_success
        self.function_arguments = function_arguments
        self.with_secret = with_secret

    def __repr__(self) -> str:
        """返回消息的字符串表示。"""
        return (
            f"ToolCallMessage(function_name={self.function_name!r}, "
            f"function_arguments={self.function_arguments!r}, "
            f"assert_success={self.assert_success!r}, "
            f"with_secret={self.with_secret!r})"
        )


class AnswerToken(BaseModel):
    """LLM回答的token表示，包含推理内容和普通内容。"""

    reasoning_content: str | None = None
    content: str | None


class OpenAiToolCallToken(BaseModel):
    """OpenAI原生工具调用的token表示。"""

    idx: int
    id: str | None = None
    name: str | None = None
    args: str | None = None


class AnswerTokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    estimated_cached_input_tokens: int | None = None


def extract_usage(usage_dict: dict[str, Any]) -> AnswerTokenUsage | None:
    prompt_tokens = usage_dict.get("prompt_tokens")
    completion_tokens = usage_dict.get("completion_tokens")
    total_tokens = usage_dict.get("total_tokens")
    if prompt_tokens is None or completion_tokens is None or total_tokens is None:
        return None
    if "prompt_cache_hit_tokens" in usage_dict:
        return AnswerTokenUsage(
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_input_tokens=usage_dict["prompt_cache_hit_tokens"],
            cache_creation_input_tokens=None,
        )
    if "cached_tokens" in usage_dict:
        return AnswerTokenUsage(
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_input_tokens=usage_dict["cached_tokens"],
            cache_creation_input_tokens=None,
        )
    prompt_tokens_details = usage_dict.get("prompt_tokens_details")
    if prompt_tokens_details is not None:
        details_dict = (
            prompt_tokens_details
            if isinstance(prompt_tokens_details, dict)
            else prompt_tokens_details.__dict__
        )
        if "cached_tokens" in details_dict:
            cache_creation = details_dict.get("cache_creation_input_tokens")
            if cache_creation is None:
                cache_creation = details_dict.get("cache_write_tokens")
            return AnswerTokenUsage(
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                total_tokens=total_tokens,
                cached_input_tokens=details_dict["cached_tokens"],
                cache_creation_input_tokens=cache_creation,
            )
    return AnswerTokenUsage(
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=None,
        cache_creation_input_tokens=None,
    )


@runtime_checkable
class Answer(Protocol):
    """LLM的一个回答"""

    def __aiter__(self) -> AsyncIterator[AnswerToken | OpenAiToolCallToken]:
        """流式返回LLM的回答，iterator中的每个item是一个token"""
        raise NotImplementedError

    def get_message(self) -> Message:
        """在LLM生成完毕之后读取LLM本次的回答，返回一个role=assistant的Message"""
        raise NotImplementedError

    def get_reasoning_message(self) -> str | None:
        """在LLM生成完毕之后读取LLM本次的回答，返回一个str，如果LLM不是推理LLM则返回None"""
        raise NotImplementedError

    def interrupt(self) -> None:
        """中断当前回答的生成"""
        raise NotImplementedError

    def truncate(self) -> None:
        """截断当前回答的生成，相当于提前帮LLM结束输出"""
        raise NotImplementedError

    def get_current_content(self) -> str | None:
        """获取当前累积的回答内容"""
        raise NotImplementedError

    def get_token_usage(self) -> AnswerTokenUsage | None:
        """获取token使用情况"""
        raise NotImplementedError

    async def get_openai_toolcalls(self) -> list[OpenAiToolCallResult] | None:
        """获取解析后的OpenAI工具调用列表，参数已解析为dict"""
        raise NotImplementedError


class LanguageModel(Protocol):
    """语言模型协议，定义语言模型的基本接口。"""

    async def answer_stream(
        self,
        history: Sequence[Message],
    ) -> Answer:
        """异步流式生成回答。"""
        raise NotImplementedError()

    def get_token_limit(self) -> int | None:
        """获取当前LLM的token限制。"""
        raise NotImplementedError()

    def get_name(self) -> str:
        """获取当前LLM的名称。"""
        raise NotImplementedError()

    def get_explicit_cache_info(self) -> ExplicitCacheInfo | None:
        raise NotImplementedError()

    def support_image(self) -> bool:
        raise NotImplementedError()

    def get_compress_threshold(self) -> int | float | None:
        """获取LLM级别的compress_threshold覆盖。"""
        raise NotImplementedError()

    def get_description(self) -> str:
        """获取LLM的描述信息。"""
        raise NotImplementedError()

    def get_compatibility(self) -> str | None:
        """获取兼容性标识（如deepseek/glm/minimax/kimi/None）。"""
        raise NotImplementedError()

    def get_custom_toolcall_format(self) -> bool:
        """获取是否使用自定义json toolcall代码块格式。"""
        raise NotImplementedError()

    async def reconnect(self) -> None:
        """重置底层客户端连接。"""
        raise NotImplementedError()
