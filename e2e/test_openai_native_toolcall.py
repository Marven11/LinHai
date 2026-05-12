import json
import pytest

from linhai.base import (
    AssistantMessage,
    OpenAiToolResultMessage,
    OpenAiToolCallToken,
    SystemMessage,
    UserMessage,
)
from linhai.llm import OpenAiAnswer
from linhai.registry import Registry

pytestmark = pytest.mark.asyncio


class _Fn:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _TC:
    def __init__(self, index, id=None, name=None, arguments=None):
        self.index = index
        self.id = id
        self.function = _Fn(name=name, arguments=arguments)


class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls
        self.reasoning_content = None


class _Choice:
    def __init__(self, delta):
        self.delta = delta


class _Chunk:
    def __init__(self, choices):
        self.choices = choices
        self.usage = None


async def _stream_toolcall_answer(registry):
    async def mock_stream():
        yield _Chunk([_Choice(_Delta(content="I will add"))])
        yield _Chunk(
            [
                _Choice(
                    _Delta(
                        tool_calls=[
                            _TC(
                                0,
                                id="call_abc123",
                                name="add",
                                arguments='{"a": 3, "b": 5}',
                            )
                        ]
                    )
                )
            ]
        )
        yield _Chunk([_Choice(_Delta(content=" these numbers."))])

    answer = OpenAiAnswer(stream=mock_stream(), registry=registry)
    tokens = []
    async for t in answer:
        tokens.append(t)
    return answer, tokens


async def test_openai_native_tool_call_generation():
    registry = Registry()
    answer, _ = await _stream_toolcall_answer(registry)

    tool_calls = await answer.get_openai_toolcalls()
    assert tool_calls is not None
    assert len(tool_calls) >= 1
    call = tool_calls[0]
    assert call["name"] == "add"
    assert call["type"] == "success"
    args = call["arguments"]
    assert "a" in args
    assert "b" in args
    assert call["id"] == "call_abc123"


async def test_openai_native_tool_call_multi_turn():
    registry = Registry()
    answer, _ = await _stream_toolcall_answer(registry)

    tool_calls = await answer.get_openai_toolcalls()
    assert tool_calls is not None
    call = tool_calls[0]
    assert call["name"] == "add"
    args = call["arguments"]
    result = args["a"] + args["b"]

    assistant_msg = answer.get_message()
    tool_result_msg = OpenAiToolResultMessage(
        tool_call_id=call["id"],
        content=str(result),
    )

    assert isinstance(assistant_msg, AssistantMessage)
    assert assistant_msg.tool_calls is not None
    assert str(result) == "8"
    assert tool_result_msg.tool_call_id == "call_abc123"
    assert tool_result_msg.content == "8"


async def test_openai_toolcall_token_streaming():
    registry = Registry()
    _, tokens = await _stream_toolcall_answer(registry)

    tc_tokens = [t for t in tokens if isinstance(t, OpenAiToolCallToken)]
    assert len(tc_tokens) > 0
    names = {t.name for t in tc_tokens if t.name is not None}
    assert "add" in names


async def test_openai_answer_get_message_with_toolcalls():
    registry = Registry()
    answer, _ = await _stream_toolcall_answer(registry)

    msg = answer.get_message()
    assert isinstance(msg, AssistantMessage)
    assert msg.tool_calls is not None
    assert len(msg.tool_calls) >= 1
    assert msg.tool_calls[0]["function"]["name"] == "add"
    llm_msg = msg.to_llm_message()
    assert "tool_calls" in llm_msg
    first_tc = next(iter(llm_msg["tool_calls"]))
    assert first_tc["id"]
