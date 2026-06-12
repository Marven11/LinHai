"""Anthropic兼容LLM实现，使用anthropic SDK与Anthropic Messages API交互。"""

from __future__ import annotations

from typing import Sequence

import anthropic

from linhai.base import (
    Answer,
    AnswerToken,
    AnswerTokenUsage,
    AssistantMessage,
    ExplicitCacheInfo,
    Message,
    extract_usage,
)
from linhai.type_hints import (
    OpenAiToolCallResult,
)
import linhai


class AnthropicAnswer:
    """Anthropic回答类，用于处理Anthropic API的流式响应。"""

    def __init__(
        self,
        stream,
        registry: linhai.registry.Registry,
        llm_instance,
        estimated_cached_input_tokens: int = 0,
    ):
        self.reasoning_content: str | None = None
        self.content: str | None = None
        self.stream = stream
        self.interrupted = False
        self.truncated = False
        self.registry = registry
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.estimated_cached_input_tokens = estimated_cached_input_tokens
        self.cached_input_tokens: int | None = None
        self.cache_creation_input_tokens: int | None = None
        self.llm_instance = llm_instance
        self.toyield: list[AnswerToken] = []

    def __aiter__(self):
        return self

    async def update_toyield(self):
        if self.interrupted or self.truncated:
            raise StopAsyncIteration

        event = await anext(self.stream, None)

        if event is None:
            raise StopAsyncIteration

        if self.interrupted:
            await self.stream.close()
            raise StopAsyncIteration

        event_type = event.type

        if event_type == "message_start":
            usage = event.message.usage
            self.input_tokens = usage.input_tokens
            self.output_tokens = usage.output_tokens
            self.total_tokens = self.input_tokens + self.output_tokens
            if self.llm_instance is not None and self.input_tokens > 0:
                self.llm_instance.previous_input_tokens = self.input_tokens
            if usage.cache_read_input_tokens:
                self.cached_input_tokens = usage.cache_read_input_tokens
            if usage.cache_creation_input_tokens:
                self.cache_creation_input_tokens = usage.cache_creation_input_tokens
            return

        if event_type == "content_block_delta":
            delta = event.delta
            if delta.type == "text_delta":
                text = delta.text
                if self.content is None:
                    self.content = text
                else:
                    self.content += text
                self.toyield.append(AnswerToken(content=text))
                return
            if delta.type == "thinking_delta":
                thinking = delta.thinking
                if self.reasoning_content is None:
                    self.reasoning_content = thinking
                else:
                    self.reasoning_content += thinking
                self.toyield.append(AnswerToken(reasoning_content=thinking, content=""))
                return
            return

        if event_type == "message_delta":
            usage = event.usage
            if usage and usage.output_tokens:
                self.output_tokens = usage.output_tokens
                self.total_tokens = self.input_tokens + self.output_tokens
            return

        if event_type == "message_stop":
            return

    async def __anext__(self) -> AnswerToken:
        while not self.toyield:
            await self.update_toyield()
            if not self.toyield:
                continue
        return self.toyield.pop(0)

    def get_message(self) -> Message:
        msg = AssistantMessage(
            message=self.content,
            reasoning_message=self.reasoning_content,
        )
        return msg

    def get_reasoning_message(self) -> str | None:
        return self.reasoning_content

    def interrupt(self):
        self.interrupted = True
        self.toyield.clear()

    def truncate(self):
        self.truncated = True
        self.toyield.clear()

    def get_current_content(self) -> str | None:
        return self.content

    def get_token_count(self) -> int:
        return self.total_tokens

    def get_token_usage(self) -> AnswerTokenUsage | None:
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

    async def get_openai_toolcalls(self) -> list[OpenAiToolCallResult] | None:
        return None


def _convert_content_to_anthropic(content) -> str | list[dict]:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        blocks: list[dict] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type == "text":
                text = part.get("text", "")
                if text:
                    blocks.append({"type": "text", "text": text})
            elif part_type == "image_url":
                url = part.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    header, b64data = url.split(",", 1)
                    media_type = header.split(":")[1].split(";")[0]
                    blocks.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64data,
                            },
                        }
                    )
        return blocks
    return ""


class AnthropicLanguageModel:
    """Anthropic语言模型实现，用于与Anthropic Messages API交互。"""

    def __init__(
        self,
        *,
        registry: linhai.registry.Registry,
        api_key: str,
        base_url: str,
        model: str,
        client_options: dict,
        completion_options: dict,
        support_image: bool,
        explicit_cache_info: ExplicitCacheInfo | None,
        token_limit: int | None,
        compress_threshold: int | float | None,
        compatibility: str | None,
        name: str,
        custom_toolcall_format: bool = True,
    ):
        self.registry = registry
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._client_options = dict(client_options)
        self._client_options.pop("timeout", None)
        self._client_options.pop("max_retries", None)
        self.client = anthropic.AsyncAnthropic(
            auth_token=self._api_key,
            base_url=self._base_url,
            timeout=10.0,
            max_retries=0,
            **self._client_options,
        )
        self.completion_options = dict(completion_options)
        self.token_limit = token_limit
        self._compress_threshold = compress_threshold
        self.compatibility = compatibility
        self.name = name
        self._support_image = support_image
        self._explicit_cache_info = explicit_cache_info
        self._custom_toolcall_format = custom_toolcall_format
        self.previous_history: Sequence[Message] | None = None
        self.previous_input_tokens: int | None = None

    def get_compatibility(self) -> str | None:
        return self.compatibility

    def get_custom_toolcall_format(self) -> bool:
        return self._custom_toolcall_format

    def support_image(self):
        return self._support_image

    def get_explicit_cache_info(self) -> ExplicitCacheInfo | None:
        return self._explicit_cache_info

    def get_token_limit(self) -> int | None:
        return self.token_limit

    def get_compress_threshold(self) -> int | float | None:
        return self._compress_threshold

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        token_limit = (
            f"{self.token_limit}" if self.token_limit is not None else "未设置"
        )
        return f"名称: {self.name}, 模型: {self.model}, token限制: {token_limit}"

    async def reconnect(self) -> None:
        await self.client.close()
        self.client = anthropic.AsyncAnthropic(
            auth_token=self._api_key,
            base_url=self._base_url,
            timeout=10.0,
            max_retries=0,
            **self._client_options,
        )

    def _convert_messages(
        self, history: Sequence[Message]
    ) -> tuple[str | None, list[dict]]:
        system_parts: list[str] = []
        raw_messages: list[dict] = []

        for msg in history:
            llm_msg = msg.to_llm_message()
            role = llm_msg.get("role", "user")
            content = llm_msg.get("content")

            if role == "system":
                if isinstance(content, str):
                    system_parts.append(content)
                continue

            if role == "tool":
                tool_content = content if isinstance(content, str) else str(content)
                raw_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": llm_msg.get("tool_call_id", ""),
                                "content": tool_content,
                            }
                        ],
                    }
                )
                continue

            if role == "assistant":
                reasoning = llm_msg.get("reasoning_content")
                assistant_content = content if content is not None else ""
                if reasoning:
                    blocks = []
                    blocks.append({"type": "thinking", "thinking": reasoning})
                    if assistant_content:
                        blocks.append({"type": "text", "text": assistant_content})
                    raw_messages.append({"role": "assistant", "content": blocks})
                else:
                    raw_messages.append(
                        {"role": "assistant", "content": str(assistant_content)}
                    )
                continue

            converted = _convert_content_to_anthropic(content)
            raw_messages.append({"role": "user", "content": converted})

        merged: list[dict] = []
        for msg in raw_messages:
            if merged and merged[-1]["role"] == msg["role"]:
                prev = merged[-1]["content"]
                curr = msg["content"]
                if isinstance(prev, str) and isinstance(curr, str):
                    merged[-1]["content"] = prev + "\n" + curr
                else:
                    prev_list = (
                        prev
                        if isinstance(prev, list)
                        else [{"type": "text", "text": prev}]
                    )
                    curr_list = (
                        curr
                        if isinstance(curr, list)
                        else [{"type": "text", "text": curr}]
                    )
                    merged[-1]["content"] = prev_list + curr_list
            else:
                merged.append(dict(msg))

        system_prompt = "\n\n".join(system_parts) if system_parts else None
        return system_prompt, merged

    def _estimate_cached_input_tokens(self, current_history: Sequence[Message]) -> int:
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
        if not history:
            raise ValueError("history is empty")

        estimated_cached_input_tokens = 0
        if self.previous_input_tokens is not None:
            estimated_cached_input_tokens = self._estimate_cached_input_tokens(history)

        system_prompt, messages = self._convert_messages(history)

        params: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        opts = dict(self.completion_options)
        max_tokens = opts.pop("max_tokens", 8192)
        params["max_tokens"] = max_tokens

        for key, value in opts.items():
            params[key] = value

        if system_prompt:
            params["system"] = system_prompt

        stream = await self.client.messages.create(**params)
        answer = AnthropicAnswer(
            stream,
            registry=self.registry,
            estimated_cached_input_tokens=estimated_cached_input_tokens,
            llm_instance=self,
        )

        self.previous_history = history
        return answer
