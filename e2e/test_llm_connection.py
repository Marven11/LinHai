import asyncio

import os

import pytest
from openai import OpenAIError

from linhai.llm import (
    OpenAi,
    SystemMessage,
    UserMessage,
    AssistantMessage,
)
from linhai.registry import Registry

pytestmark = pytest.mark.asyncio

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openrouter/free"


def _get_token() -> str:
    token = os.environ.get("OPENROUTER_TOKEN")
    if not token:
        pytest.fail("OPENROUTER_TOKEN not set")
    return token


def _create_llm(api_key: str) -> tuple[OpenAi, Registry]:
    registry = Registry()
    registry.register_queue("token_usage")
    llm = OpenAi(
        registry=registry,
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        model=OPENROUTER_MODEL,
        openai_config={
            "default_headers": {
                "HTTP-Referer": "https://github.com/Marven11/LinHai",
                "X-Title": "LinHai E2E Tests",
            }
        },
        chat_completion_kwargs={
            "max_tokens": 100,
            "stream_options": {"include_usage": True},
        },
        support_image=False,
        explicit_cache_info=None,
        name="test",
    )
    return llm, registry


async def _collect_answer(answer):
    async for _ in answer:
        pass


async def test_basic_streaming_response():
    token = _get_token()
    llm, registry = _create_llm(token)
    system_msg = SystemMessage(registry)
    for _ in range(3):
        answer = await llm.answer_stream(
            [system_msg, UserMessage("Say hello in one word")]
        )
        tokens: list = []
        async for t in answer:
            tokens.append(t)
        content = answer.get_current_content()
        if len(content) > 0 and len(tokens) > 0:
            return
    pytest.fail("Free model returned empty response after retries")


async def _stream_and_collect(llm, history):
    answer = await llm.answer_stream(history)
    await _collect_answer(answer)
    return answer


async def _stream_with_retry(llm, history, max_retries: int = 5):
    for i in range(max_retries):
        answer = await _stream_and_collect(llm, history)
        if len(answer.get_current_content()) > 0:
            return answer
        if i < max_retries - 1:
            await asyncio.sleep(1)
    pytest.fail("Free model returned empty response after retries")


async def test_token_usage_reporting():
    token = _get_token()
    llm, registry = _create_llm(token)
    system_msg = SystemMessage(registry)
    answer = await _stream_and_collect(llm, [system_msg, UserMessage("Say hi")])
    for _ in range(3):
        usage = answer.get_token_usage()
        if usage is not None and usage.input_tokens > 0:
            assert usage.output_tokens > 0
            assert usage.total_tokens > 0
            return
        answer = await _stream_and_collect(llm, [system_msg, UserMessage("Say hi")])
    pytest.fail("Free model did not return token usage after retries")


async def test_multi_turn_conversation():
    token = _get_token()
    llm, registry = _create_llm(token)
    system_msg = SystemMessage(registry)

    history = [system_msg, UserMessage("Tell me a number between 1 and 10")]
    answer1 = await _stream_with_retry(llm, history)
    first_response = answer1.get_current_content()

    assistant_msg = AssistantMessage(first_response)
    history = [
        system_msg,
        UserMessage("Tell me a number between 1 and 10"),
        assistant_msg,
        UserMessage("Now tell me a different number"),
    ]
    answer2 = await _stream_with_retry(llm, history)
    second_response = answer2.get_current_content()
    assert first_response != second_response


async def test_empty_history_raises_error():
    token = _get_token()
    llm, _ = _create_llm(token)
    with pytest.raises(ValueError, match="history is empty"):
        await llm.answer_stream([])


async def test_invalid_api_key():
    llm, _ = _create_llm("invalid-key-12345")
    history = [UserMessage("Hello")]
    with pytest.raises(OpenAIError):
        answer = await llm.answer_stream(history)
        await _collect_answer(answer)
