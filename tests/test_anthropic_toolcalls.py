import json
import unittest
from dataclasses import dataclass

from linhai.llm.anthropic_compatible import AnthropicAnswer, AnthropicLanguageModel
from linhai.base import (
    AnthropicToolCallToken,
    AssistantMessage,
    OpenAiToolResultMessage,
)


@dataclass
class MockContentBlock:
    type: str
    id: str | None = None
    name: str | None = None


@dataclass
class MockDelta:
    type: str
    text: str | None = None
    thinking: str | None = None
    partial_json: str | None = None


@dataclass
class MockEvent:
    type: str
    index: int = 0
    content_block: MockContentBlock | None = None
    delta: MockDelta | None = None


def _make_stream(events):
    async def _stream():
        for e in events:
            yield e

    return _stream()


def _make_answer(events):
    answer = AnthropicAnswer.__new__(AnthropicAnswer)
    answer.reasoning_content = None
    answer.content = None
    answer.stream = _make_stream(events)
    answer.interrupted = False
    answer.truncated = False
    answer.registry = None
    answer.total_tokens = 0
    answer.input_tokens = 0
    answer.output_tokens = 0
    answer.estimated_cached_input_tokens = 0
    answer.cached_input_tokens = None
    answer.cache_creation_input_tokens = None
    answer.llm_instance = None
    answer.toyield = []
    answer._anthropic_toolcall_parts = {}
    answer._current_content_block_idx = -1
    answer._explicit_cache_info = None
    return answer


class TestAnthropicAnswerToolUse(unittest.IsolatedAsyncioTestCase):
    async def test_parses_tool_use(self):
        events = [
            MockEvent(
                type="content_block_start",
                index=0,
                content_block=MockContentBlock(
                    type="tool_use", id="tool_123", name="read_file"
                ),
            ),
            MockEvent(
                type="content_block_delta",
                index=0,
                delta=MockDelta(type="input_json_delta", partial_json='{"file'),
            ),
            MockEvent(
                type="content_block_delta",
                index=0,
                delta=MockDelta(
                    type="input_json_delta", partial_json='path": "/tmp/test.txt"}'
                ),
            ),
            MockEvent(type="content_block_stop", index=0),
            MockEvent(type="message_stop"),
        ]

        answer = _make_answer(events)
        tokens = []
        async for token in answer:
            tokens.append(token)

        tool_tokens = [t for t in tokens if isinstance(t, AnthropicToolCallToken)]
        self.assertGreaterEqual(len(tool_tokens), 1)
        self.assertEqual(tool_tokens[0].id, "tool_123")
        self.assertEqual(tool_tokens[0].name, "read_file")

        result = await answer.get_native_toolcalls()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "success")
        self.assertEqual(result[0]["id"], "tool_123")
        self.assertEqual(result[0]["name"], "read_file")
        self.assertEqual(result[0]["arguments"], {"filepath": "/tmp/test.txt"})

    async def test_get_native_toolcalls_returns_none(self):
        answer = AnthropicAnswer.__new__(AnthropicAnswer)
        answer._anthropic_toolcall_parts = {}
        result = await answer.get_native_toolcalls()
        self.assertIsNone(result)

    async def test_failed_json_parse(self):
        events = [
            MockEvent(
                type="content_block_start",
                index=0,
                content_block=MockContentBlock(
                    type="tool_use", id="tool_789", name="read_file"
                ),
            ),
            MockEvent(
                type="content_block_delta",
                index=0,
                delta=MockDelta(type="input_json_delta", partial_json='{"invalid'),
            ),
            MockEvent(type="content_block_stop", index=0),
            MockEvent(type="message_stop"),
        ]

        answer = _make_answer(events)
        async for _ in answer:
            pass

        result = await answer.get_native_toolcalls()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "error")
        self.assertEqual(result[0]["id"], "tool_789")
        self.assertEqual(result[0]["name"], "read_file")


class TestAnthropicAnswerGetMessage(unittest.TestCase):
    def test_includes_tool_calls(self):
        answer = AnthropicAnswer.__new__(AnthropicAnswer)
        answer.content = "Let me read that file."
        answer.reasoning_content = None
        answer._anthropic_toolcall_parts = {
            0: {"id": "tool_456", "name": "write_file", "args": '{"path": "x"}'},
        }

        msg = answer.get_message()
        self.assertIsNotNone(msg.tool_calls)
        self.assertEqual(len(msg.tool_calls), 1)
        self.assertEqual(msg.tool_calls[0]["id"], "tool_456")
        self.assertEqual(msg.tool_calls[0]["function"]["name"], "write_file")


class TestConvertMessages(unittest.TestCase):
    def test_with_tool_calls(self):
        from linhai.type_hints import OpenAiToolCall, FunctionCall

        llm = AnthropicLanguageModel.__new__(AnthropicLanguageModel)
        llm._custom_toolcall_format = False

        asst = AssistantMessage(message="Using tool now")
        asst.tool_calls = [
            OpenAiToolCall(
                id="tc1",
                function=FunctionCall(name="read_file", arguments='{"f": "x"}'),
                type="function",
            )
        ]

        _, raw = llm._convert_messages([asst])
        self.assertEqual(len(raw), 1)
        msg = raw[0]
        self.assertEqual(msg["role"], "assistant")
        self.assertIsInstance(msg["content"], list)
        tool_use_blocks = [b for b in msg["content"] if b["type"] == "tool_use"]
        self.assertEqual(len(tool_use_blocks), 1)
        self.assertEqual(tool_use_blocks[0]["id"], "tc1")
        self.assertEqual(tool_use_blocks[0]["name"], "read_file")
        self.assertEqual(tool_use_blocks[0]["input"], {"f": "x"})

    def test_tool_result(self):
        llm = AnthropicLanguageModel.__new__(AnthropicLanguageModel)
        llm._custom_toolcall_format = False

        tool_result = OpenAiToolResultMessage(
            tool_call_id="tc1", content="file content here", tool_name="read_file"
        )

        _, raw = llm._convert_messages([tool_result])
        self.assertEqual(len(raw), 1)
        msg = raw[0]
        self.assertEqual(msg["role"], "user")
        self.assertIsInstance(msg["content"], list)
        self.assertEqual(msg["content"][0]["type"], "tool_result")
        self.assertEqual(msg["content"][0]["tool_use_id"], "tc1")
