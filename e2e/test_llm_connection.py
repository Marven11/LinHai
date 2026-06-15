import pytest

from linhai.base import SystemMessage, UserMessage, AssistantMessage
from linhai.llm import OpenAi
from linhai.registry import Registry

from conftest import retry_llm_call

pytestmark = pytest.mark.asyncio

DEEPSEEK_BASE_URL = "http://192.168.114.149:8124/v1"
DEEPSEEK_MODEL = "deepseek/deepseek-v4-flash"


def _create_llm(api_key: str) -> tuple[OpenAi, Registry]:
    registry = Registry()
    registry.register_queue("token_usage")
    llm = OpenAi(
        registry=registry,
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
        model=DEEPSEEK_MODEL,
        openai_config={
            "default_headers": {
                "HTTP-Referer": "https://github.com/Marven11/LinHai",
                "X-Title": "LinHai E2E Tests",
            }
        },
        chat_completion_kwargs={
            "max_tokens": 4096,
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
    token = "gomodel-master-key"
    llm, registry = _create_llm(token)
    system_msg = SystemMessage(registry)

    async def try_once():
        answer = await llm.answer_stream(
            [system_msg, UserMessage("Say hello in one word")]
        )
        tokens: list = []
        async for t in answer:
            tokens.append(t)
        content = answer.get_current_content()
        if content is None or len(content) == 0 or len(tokens) == 0:
            return None
        return content

    await retry_llm_call(try_once)


async def _stream_and_collect(llm, history):
    answer = await llm.answer_stream(history)
    await _collect_answer(answer)
    return answer


async def _stream_with_retry(llm, history):
    async def try_once():
        answer = await _stream_and_collect(llm, history)
        content = answer.get_current_content()
        if content is None:
            return None
        return answer if len(content) > 0 else None

    return await retry_llm_call(try_once)


async def test_token_usage_reporting():
    token = "gomodel-master-key"
    llm, registry = _create_llm(token)
    system_msg = SystemMessage(registry)

    async def try_once():
        answer = await _stream_and_collect(llm, [system_msg, UserMessage("Say hi")])
        usage = answer.get_token_usage()
        if usage is not None and usage.input_tokens > 0:
            return usage
        return None

    usage = await retry_llm_call(try_once)
    assert usage.output_tokens > 0
    assert usage.total_tokens > 0


async def test_multi_turn_conversation():
    token = "gomodel-master-key"
    llm, registry = _create_llm(token)
    system_msg = SystemMessage(registry)

    history = [system_msg, UserMessage("Tell me a number between 1 and 10")]
    answer1 = await _stream_with_retry(llm, history)
    first_response = answer1.get_current_content()
    assert len(first_response) > 0

    assistant_msg = AssistantMessage(first_response)
    history = [
        system_msg,
        UserMessage("Tell me a number between 1 and 10"),
        assistant_msg,
        UserMessage("Now tell me a different number"),
    ]
    answer2 = await _stream_with_retry(llm, history)
    second_response = answer2.get_current_content()
    assert len(second_response) > 0


async def test_empty_history_raises_error():
    token = "gomodel-master-key"
    llm, _ = _create_llm(token)
    with pytest.raises(ValueError, match="history is empty"):
        await llm.answer_stream([])
