"""LLM模块，定义语言模型API调用实现。"""

from __future__ import annotations

import json
from typing import Sequence
import asyncio

from openai import AsyncOpenAI, OpenAIError
from linhai.base import (
    Answer,
    AnswerToken,
    AnswerTokenUsage,
    AssistantMessage,
    ExplicitCacheInfo,
    Message,
    OpenAiToolCallToken,
    extract_usage,
)
from linhai.type_hints import (
    FunctionCall,
    OpenAiToolCall,
    OpenAiToolCallResult,
    ParsedOpenAiToolCall,
    FailedOpenAiToolCall,
)
from linhai.utils.common import UiNotice
import linhai


class OpenAiAnswer:
    """OpenAI回答类，用于处理OpenAI API的流式响应。"""

    def __init__(
        self,
        stream,
        registry: linhai.registry.Registry,
        compatibility: str | None = None,
        estimated_cached_input_tokens: int = 0,
        llm_instance=None,
    ):
        """初始化OpenAI回答。"""
        self.reasoning_content = None
        self.content: str | None = None
        self.stream = stream
        self.interrupted = False
        self.truncated = False
        self.compatibility = compatibility
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.registry = registry
        self.estimated_cached_input_tokens = estimated_cached_input_tokens
        self.cached_input_tokens: int | None = None
        self.cache_creation_input_tokens: int | None = None
        self.llm_instance = llm_instance
        self.toyield: list[AnswerToken | OpenAiToolCallToken] = []
        self._openai_toolcall_parts: dict[int, dict[str, str | None]] = {}

    def __aiter__(self):
        """返回异步迭代器。"""
        return self

    async def update_toyield(self):
        """获取下一个token。"""
        if self.interrupted or self.truncated:
            raise StopAsyncIteration

        try:

            chunk = await self.stream.__anext__()

            if self.interrupted:
                await self.stream.close()

                raise StopAsyncIteration

            if hasattr(chunk, "usage") and chunk.usage:
                usage_result = extract_usage(chunk.usage.__dict__)
                if usage_result is not None:
                    self.input_tokens = usage_result.input_tokens
                    self.output_tokens = usage_result.output_tokens
                    self.total_tokens = usage_result.total_tokens
                    if usage_result.cached_input_tokens is not None:
                        self.cached_input_tokens = usage_result.cached_input_tokens
                    self.cache_creation_input_tokens = (
                        usage_result.cache_creation_input_tokens
                    )
                    if self.llm_instance is not None and self.input_tokens > 0:
                        self.llm_instance.previous_input_tokens = self.input_tokens
            if len(chunk.choices) == 0:
                return
            delta = chunk.choices[0].delta
            content = delta.content
            if content is not None:
                if self.content is None:
                    self.content = content
                else:
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

            tool_calls = delta.tool_calls
            if tool_calls:
                for tc in tool_calls:
                    idx = tc.index
                    if idx not in self._openai_toolcall_parts:
                        self._openai_toolcall_parts[idx] = {
                            "id": None,
                            "name": None,
                            "args": "",
                        }
                    tc_id = tc.id
                    tc_name = tc.function.name
                    tc_args = tc.function.arguments
                    if tc_id is not None:
                        self._openai_toolcall_parts[idx]["id"] = tc_id
                    if tc_name is not None:
                        self._openai_toolcall_parts[idx]["name"] = tc_name
                    if tc_args is not None:
                        self._openai_toolcall_parts[idx]["args"] += tc_args
                    self.toyield.append(
                        OpenAiToolCallToken(
                            idx=idx,
                            id=tc_id,
                            name=tc_name,
                            args=tc_args,
                        )
                    )
        except StopAsyncIteration:
            raise
        except asyncio.CancelledError as exc:
            self.interrupted = True
            raise StopAsyncIteration from exc
        except Exception as exc:
            self.interrupted = True
            raise StopAsyncIteration from exc

    async def __anext__(self) -> AnswerToken | OpenAiToolCallToken:
        if not self.toyield:
            await self.update_toyield()
        if not self.toyield:
            raise StopAsyncIteration
        return self.toyield.pop(0)

    def get_message(self) -> Message:
        """获取完整的消息对象。"""
        msg = AssistantMessage(
            message=self.content,
            reasoning_message=self.reasoning_content,
        )
        msg.tool_calls = self._get_raw_toolcalls()
        return msg

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

    def get_current_content(self) -> str | None:
        """获取当前累积的回答内容。"""
        return self.content

    def get_token_count(self) -> int:
        """获取当前回答的token总数。"""
        return self.total_tokens

    def get_token_usage(self) -> AnswerTokenUsage | None:
        """获取token使用情况。"""
        if self.total_tokens == 0:
            return None
        return AnswerTokenUsage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.total_tokens,
            cached_input_tokens=self.cached_input_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens,
            estimated_cached_input_tokens=self.estimated_cached_input_tokens,
        )

    def _get_raw_toolcalls(self) -> list[OpenAiToolCall] | None:
        if not self._openai_toolcall_parts:
            return None
        result: list[OpenAiToolCall] = []
        for idx in sorted(self._openai_toolcall_parts):
            part = self._openai_toolcall_parts[idx]
            if part["id"] is None or part["name"] is None:
                continue
            result.append(
                OpenAiToolCall(
                    id=part["id"],
                    function=FunctionCall(
                        name=part["name"],
                        arguments=part["args"] or "",
                    ),
                    type="function",
                )
            )
        return result or None

    async def get_openai_toolcalls(self) -> list[OpenAiToolCallResult] | None:
        toolcalls = self._get_raw_toolcalls()
        if not toolcalls:
            return None

        async def _parse_args(args_str: str) -> dict:
            return json.loads(args_str)

        parse_coros = [_parse_args(tc["function"]["arguments"]) for tc in toolcalls]
        results = await asyncio.gather(*parse_coros, return_exceptions=True)

        parsed: list[OpenAiToolCallResult] = []
        for tc, result in zip(toolcalls, results):
            if isinstance(result, dict):
                parsed.append(
                    ParsedOpenAiToolCall(
                        type="success",
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=result,
                    )
                )
            else:
                parsed.append(
                    FailedOpenAiToolCall(
                        type="error",
                        id=tc["id"],
                        name=tc["function"]["name"],
                        raw_arguments=tc["function"]["arguments"],
                        error=str(result),
                    )
                )
        return parsed or None


class MinimaxAnswer:
    """处理minimax非流式响应的Answer类。"""

    def __init__(
        self,
        response,  # ChatCompletion对象
        registry: linhai.registry.Registry,
        cached_input_tokens: int = 0,
        llm_instance=None,
    ):
        """初始化Minimax回答。

        注意：使用__dict__读取字段是因为各个API提供商返回的字段不一致，
        这样可以及时发现配置问题而不是静默返回None。"""
        # 解析响应
        message = response.choices[0].message
        message_dict = message.__dict__
        response_dict = response.__dict__

        reasoning_details = message_dict.get("reasoning_details")
        if reasoning_details:
            self.reasoning_content = reasoning_details.__dict__.get("text")
        else:
            self.reasoning_content = None
        self.content = message_dict.get("content")
        usage = response_dict.get("usage")

        self.interrupted = False
        self.truncated = False
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.registry = registry
        self.estimated_cached_input_tokens = cached_input_tokens
        self.cached_input_tokens: int | None = None
        self.cache_creation_input_tokens: int | None = None
        self.llm_instance = llm_instance
        if usage:
            usage_result = extract_usage(usage.__dict__)
            if usage_result is not None:
                self.total_tokens = usage_result.total_tokens
                self.input_tokens = usage_result.input_tokens
                self.output_tokens = usage_result.output_tokens
                if usage_result.cached_input_tokens is not None:
                    self.cached_input_tokens = usage_result.cached_input_tokens
                self.cache_creation_input_tokens = (
                    usage_result.cache_creation_input_tokens
                )
        self.toyield: list[AnswerToken] = []

        self._openai_toolcalls: list[OpenAiToolCall] | None = None
        tool_calls = message.tool_calls
        if tool_calls:
            self._openai_toolcalls = []
            for tc in tool_calls:
                self._openai_toolcalls.append(
                    OpenAiToolCall(
                        id=tc.id,
                        function=FunctionCall(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        ),
                        type="function",
                    )
                )

        # 如果llm_instance存在，更新previous_input_tokens
        if self.llm_instance is not None and self.input_tokens > 0:
            self.llm_instance.previous_input_tokens = self.input_tokens

        # 注意：token_usage现在在OpenAi类中发送，不在这里发送
        # 确保toyield只包含AnswerToken
        if self.reasoning_content:
            self.toyield.append(
                AnswerToken(
                    reasoning_content=self.reasoning_content,
                    content="",
                )
            )
        if self.content is not None:
            self.toyield.append(
                AnswerToken(
                    reasoning_content=None,
                    content=self.content or "",
                )
            )

    def __aiter__(self):
        return self

    async def __anext__(self) -> AnswerToken:
        if self.interrupted or self.truncated:
            raise StopAsyncIteration
        if not self.toyield:
            raise StopAsyncIteration
        return self.toyield.pop(0)

    def get_message(self) -> Message:
        """获取完整的消息对象。"""
        msg = AssistantMessage(
            message=self.content,
            reasoning_message=self.reasoning_content,
        )
        msg.tool_calls = self._get_raw_toolcalls()
        return msg

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

    def get_current_content(self) -> str | None:
        """获取当前累积的回答内容。"""
        return self.content

    def get_token_count(self) -> int:
        """获取当前回答的token总数。"""
        return self.total_tokens

    def get_token_usage(self) -> AnswerTokenUsage | None:
        """获取token使用情况。"""
        if self.total_tokens == 0:
            return None
        return AnswerTokenUsage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.total_tokens,
            cached_input_tokens=self.cached_input_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens,
            estimated_cached_input_tokens=self.estimated_cached_input_tokens,
        )

    def _get_raw_toolcalls(self) -> list[OpenAiToolCall] | None:
        return self._openai_toolcalls

    async def get_openai_toolcalls(self) -> list[OpenAiToolCallResult] | None:
        toolcalls = self._get_raw_toolcalls()
        if not toolcalls:
            return None

        async def _parse_args(args_str: str) -> dict:
            return json.loads(args_str)

        parse_coros = [_parse_args(tc["function"]["arguments"]) for tc in toolcalls]
        results = await asyncio.gather(*parse_coros, return_exceptions=True)

        parsed: list[OpenAiToolCallResult] = []
        for tc, result in zip(toolcalls, results):
            if isinstance(result, dict):
                parsed.append(
                    ParsedOpenAiToolCall(
                        type="success",
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=result,
                    )
                )
            else:
                parsed.append(
                    FailedOpenAiToolCall(
                        type="error",
                        id=tc["id"],
                        name=tc["function"]["name"],
                        raw_arguments=tc["function"]["arguments"],
                        error=str(result),
                    )
                )
        return parsed or None


class OpenAi:
    """OpenAI语言模型实现，用于与OpenAI API交互。"""

    def __init__(
        self,
        *,
        registry: linhai.registry.Registry,
        api_key: str,
        base_url: str,
        model: str,
        openai_config: dict,
        chat_completion_kwargs: dict,
        support_image: bool,
        explicit_cache_info: ExplicitCacheInfo | None,
        tools: list[dict] | None = None,
        token_limit: int | None = None,
        compress_threshold: int | float | None = None,
        compatibility: str | None = None,
        name: str,
        custom_toolcall_format: bool = True,
    ):
        """初始化OpenAI语言模型。

        参数:
            registry: Registry实例，用于发送通知和协调组件
            api_key: OpenAI API密钥
            base_url: API基础URL
            model: 模型名称
            openai_config: 额外的OpenAI配置
            chat_completion_kwargs: 聊天补全额外参数
            tools: 可用工具列表
            token_limit: token限制数量
            compatibility: API兼容性模式，支持minimax、kimi等
            name: LLM的名称
        """
        self.registry = registry
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._openai_config = dict(openai_config)
        self._openai_config.pop("timeout", None)
        self._openai_config.pop("max_retries", None)
        self.openai = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=10,
            max_retries=0,
            **self._openai_config,
        )
        self.tools = tools
        self.chat_completion_kwargs = chat_completion_kwargs
        self.token_limit = token_limit
        self._compress_threshold = compress_threshold
        self.compatibility = compatibility
        self.name = name
        self.previous_history: Sequence[Message] | None = None
        self.previous_input_tokens: int | None = None
        self._minimax_warning_sent: bool = False
        self._support_image = support_image
        self._explicit_cache_info = explicit_cache_info
        self._custom_toolcall_format = custom_toolcall_format

    def get_compatibility(self) -> str | None:
        return self.compatibility

    def get_custom_toolcall_format(self) -> bool:
        return self._custom_toolcall_format

    def support_image(self):
        return self._support_image

    def get_explicit_cache_info(self) -> ExplicitCacheInfo | None:
        return self._explicit_cache_info

    def get_token_limit(self) -> int | None:
        """获取当前LLM的token限制。

        返回:
            int | None: token限制数量，如果没有配置则返回None
        """
        return self.token_limit

    def get_compress_threshold(self) -> int | float | None:
        """获取LLM级别的compress_threshold覆盖。

        返回:
            int | float | None: LLM级别的压缩阈值，如果没有配置则返回None
        """
        return self._compress_threshold

    def get_name(self) -> str:
        """获取当前LLM的名称。

        返回:
            str: LLM的名称
        """
        return self.name

    def get_description(self) -> str:
        """获取LLM的描述信息。

        返回:
            str: LLM的描述，包含名称、模型和token限制等
        """
        token_limit = (
            f"{self.token_limit}" if self.token_limit is not None else "未设置"
        )
        return f"名称: {self.name}, 模型: {self.model}, token限制: {token_limit}"

    async def reconnect(self) -> None:
        """重置底层OpenAI客户端连接。

        关闭当前连接并重新初始化AsyncOpenAI实例，
        用于在429等错误时重置客户端状态。
        """
        await self.openai.close()
        self.openai = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=10,
            max_retries=0,
            **self._openai_config,
        )

    def _estimate_cached_input_tokens(self, current_history: Sequence[Message]) -> int:
        """估算缓存的输入token数量。

        将上一个history和当前history的所有内容拼接成字符串，
        然后按64字符块对比相同前缀，计算缓存比例。
        """
        if self.previous_history is None or self.previous_input_tokens is None:
            return 0
        previous_content = "".join(
            c for msg in self.previous_history if (c := msg.get_content()) is not None
        )
        current_content = "".join(
            c2 for msg in current_history if (c2 := msg.get_content()) is not None
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
        messages = [msg.to_llm_message() for msg in history]

        if self.compatibility == "baizhi":
            from linhai.utils.baizhi_compat import fix_baizhi_messages

            messages = await fix_baizhi_messages(messages)

        estimated_cached_input_tokens = 0
        if self.previous_input_tokens is not None:
            estimated_cached_input_tokens = self._estimate_cached_input_tokens(history)

        params = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "timeout": 30,
            **self.chat_completion_kwargs,
        }

        if self.compatibility == "minimax":
            # minimax在使用stream=True时不返回usage信息，导致兼容问题，已关闭stream
            params["extra_body"] = {"reasoning_split": True}
            params["stream"] = False
            # 提示用户，但只提示一次
            if not self._minimax_warning_sent:
                await self.registry.send(
                    "ui_log",
                    UiNotice(
                        level="INFO",
                        content="minimax的api在开启stream时不返回usage，导致兼容问题，已关闭stream",
                    ),
                )
                self._minimax_warning_sent = True

        if self.compatibility == "kimi":
            params["stream_options"] = {"include_usage": True}

        if self.compatibility == "glm":
            extra_body = params.get("extra_body", {})
            if not isinstance(extra_body, dict):
                extra_body = {}
            thinking = extra_body.get("thinking", {})
            if not isinstance(thinking, dict):
                thinking = {}
            if "type" not in thinking:
                thinking["type"] = "enabled"
            if thinking.get("type") == "enabled" and "clear_thinking" not in thinking:
                thinking["clear_thinking"] = False
            extra_body["thinking"] = thinking
            params["extra_body"] = extra_body

        if self.tools:
            params["tools"] = self.tools
        elif not self._custom_toolcall_format:
            from linhai.tool.main import ToolManager

            tool_manager = self.registry.get_member_typechecked(
                "tool_manager", ToolManager
            )
            params["tools"] = tool_manager.get_tools_info()

        if self.compatibility == "minimax":
            response = await self.openai.chat.completions.create(**params)
            answer = MinimaxAnswer(
                response,
                registry=self.registry,
                cached_input_tokens=estimated_cached_input_tokens,
                llm_instance=self,
            )
        else:
            stream = await self.openai.chat.completions.create(**params)
            answer = OpenAiAnswer(
                stream,
                registry=self.registry,
                compatibility=self.compatibility,
                estimated_cached_input_tokens=estimated_cached_input_tokens,
                llm_instance=self,
            )

        self.previous_history = history
        return answer
