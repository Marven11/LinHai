import json
import pytest

from linhai.base import (
    AssistantMessage,
    OpenAiToolResultMessage,
    OpenAiToolCallToken,
    SystemMessage,
    UserMessage,
)
from linhai.llm import OpenAi
from linhai.registry import Registry

pytestmark = pytest.mark.asyncio

BASE_URL = "http://192.168.114.149:8124/v1/deepseek"
MODEL = "deepseek-chat"
E2E_NATIVE_TC_RETRIES = 3
SKIP_REASON = "Model does not support native tool calling"

ADD_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two numbers together",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"},
                },
                "required": ["a", "b"],
            },
        },
    }
]


def _create_openai_with_tools() -> tuple[OpenAi, Registry]:
    registry = Registry()
    registry.register_queue("token_usage")
    llm = OpenAi(
        registry=registry,
        api_key="x",
        base_url=BASE_URL,
        model=MODEL,
        openai_config={
            "default_headers": {
                "HTTP-Referer": "https://github.com/Marven11/LinHai",
                "X-Title": "LinHai E2E Tests",
            }
        },
        chat_completion_kwargs={"max_tokens": 200},
        support_image=False,
        explicit_cache_info=None,
        name="test_native_toolcall",
        tools=ADD_TOOL,
        custom_toolcall_format=False,
    )
    return llm, registry


async def _stream_and_collect(llm, history):
    answer = await llm.answer_stream(history)
    tokens = []
    async for t in answer:
        tokens.append(t)
    return answer, tokens


async def _try_get_tool_calls(llm, history):
    for _ in range(E2E_NATIVE_TC_RETRIES):
        answer, tokens = await _stream_and_collect(llm, history)
        tool_calls = answer.get_openai_toolcalls()
        if tool_calls and len(tool_calls) > 0:
            return answer, tool_calls, tokens
    pytest.skip(SKIP_REASON)


async def _try_get_content(llm, history):
    for _ in range(E2E_NATIVE_TC_RETRIES):
        answer, tokens = await _stream_and_collect(llm, history)
        content = answer.get_current_content()
        if content:
            return content
    pytest.skip(SKIP_REASON)


async def test_openai_native_tool_call_generation():
    llm, registry = _create_openai_with_tools()
    system_msg = SystemMessage(registry)
    history = [system_msg, UserMessage("What is 3 plus 5?")]

    answer, tool_calls, _ = await _try_get_tool_calls(llm, history)
    assert len(tool_calls) >= 1
    call = tool_calls[0]
    assert call["function"]["name"] == "add"
    args = json.loads(call["function"]["arguments"])
    assert "a" in args
    assert "b" in args
    assert call["id"]
    assert call["type"] == "function"


async def test_openai_native_tool_call_multi_turn():
    llm, registry = _create_openai_with_tools()
    system_msg = SystemMessage(registry)
    user_msg = UserMessage("What is 3 plus 5?")
    history = [system_msg, user_msg]

    answer1, tool_calls, _ = await _try_get_tool_calls(llm, history)
    assert len(tool_calls) >= 1
    call = tool_calls[0]
    assert call["function"]["name"] == "add"
    args = json.loads(call["function"]["arguments"])
    a = args["a"]
    b = args["b"]
    result = a + b

    assistant_msg = answer1.get_message()
    tool_result_msg = OpenAiToolResultMessage(
        tool_call_id=call["id"],
        content=str(result),
    )
    history2 = [system_msg, user_msg, assistant_msg, tool_result_msg]

    final_content = await _try_get_content(llm, history2)
    assert str(result) in final_content or str(int(result)) in final_content


async def test_openai_toolcall_token_streaming():
    llm, registry = _create_openai_with_tools()
    system_msg = SystemMessage(registry)
    history = [system_msg, UserMessage("What is 3 plus 5?")]

    answer, _, tokens = await _try_get_tool_calls(llm, history)
    tc_tokens = [t for t in tokens if isinstance(t, OpenAiToolCallToken)]
    assert len(tc_tokens) > 0
    names = {t.name for t in tc_tokens if t.name is not None}
    assert "add" in names


async def test_openai_answer_get_message_with_toolcalls():
    llm, registry = _create_openai_with_tools()
    system_msg = SystemMessage(registry)
    history = [system_msg, UserMessage("What is 3 plus 5?")]

    answer, _, _ = await _try_get_tool_calls(llm, history)
    msg = answer.get_message()
    assert isinstance(msg, AssistantMessage)
    assert msg.tool_calls is not None
    assert len(msg.tool_calls) >= 1
    assert msg.tool_calls[0]["function"]["name"] == "add"
    llm_msg = msg.to_llm_message()
    assert "tool_calls" in llm_msg
    first_tc = next(iter(llm_msg["tool_calls"]))
    assert first_tc["id"]
