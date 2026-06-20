import json
import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.base import AssistantMessage, OpenAiToolResultMessage
from linhai.type_hints import FunctionCall, OpenAiToolCall
from linhai.llm import OpenAiAnswer, MinimaxAnswer
from linhai.registry import Registry


class TestAssistantMessageToolCalls(unittest.TestCase):
    def test_without_tool_calls(self):
        msg = AssistantMessage(message="hello")
        self.assertIsNone(msg.tool_calls)
        llm_msg = msg.to_llm_message()
        self.assertNotIn("tool_calls", llm_msg)

    def test_with_tool_calls(self):
        tool_calls = [
            OpenAiToolCall(
                id="call_1",
                function=FunctionCall(name="func", arguments="{}"),
                type="function",
            )
        ]
        msg = AssistantMessage(message="")
        msg.tool_calls = tool_calls
        llm_msg = msg.to_llm_message()
        self.assertIn("tool_calls", llm_msg)
        self.assertEqual(llm_msg["tool_calls"][0]["id"], "call_1")

    def test_to_json_from_json_with_tool_calls(self):
        tool_calls = [
            OpenAiToolCall(
                id="call_2",
                function=FunctionCall(name="test_fn", arguments='{"a": 1}'),
                type="function",
            )
        ]
        msg = AssistantMessage(message="response", reasoning_message="thinking")
        msg.tool_calls = tool_calls
        json_str = msg.to_json()
        restored = AssistantMessage.from_json(json_str, registry=MagicMock())
        self.assertEqual(restored.message, "response")
        self.assertEqual(restored.reasoning_message, "thinking")
        self.assertIsNotNone(restored.tool_calls)
        self.assertEqual(restored.tool_calls[0]["id"], "call_2")
        self.assertEqual(restored.tool_calls[0]["function"]["name"], "test_fn")


class TestOpenAiAnswerGetToolCalls(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Registry()
        self.mock_stream = AsyncMock()

    async def test_no_tool_calls_returns_none(self):
        answer = OpenAiAnswer(
            stream=self.mock_stream,
            registry=self.registry,
        )
        self.assertIsNone(await answer.get_native_toolcalls())

    async def test_tool_calls_assembled_from_parts(self):
        answer = OpenAiAnswer(
            stream=self.mock_stream,
            registry=self.registry,
        )
        answer._openai_toolcall_parts = {
            0: {"id": "call_a", "name": "func_a", "args": '{"x": 1}'},
            1: {"id": "call_b", "name": "func_b", "args": "{}"},
        }
        result = await answer.get_native_toolcalls()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "call_a")
        self.assertEqual(result[0]["arguments"], {"x": 1})
        self.assertEqual(result[1]["name"], "func_b")

    async def test_incomplete_tool_call_skipped(self):
        answer = OpenAiAnswer(
            stream=self.mock_stream,
            registry=self.registry,
        )
        answer._openai_toolcall_parts = {
            0: {"id": None, "name": None, "args": ""},
        }
        self.assertIsNone(await answer.get_native_toolcalls())

    async def test_get_message_includes_tool_calls(self):
        answer = OpenAiAnswer(
            stream=self.mock_stream,
            registry=self.registry,
        )
        answer.content = "some text"
        answer._openai_toolcall_parts = {
            0: {"id": "call_x", "name": "my_func", "args": "{}"},
        }
        msg = answer.get_message()
        self.assertIsInstance(msg, AssistantMessage)
        self.assertIsNotNone(msg.tool_calls)
        self.assertEqual(msg.tool_calls[0]["id"], "call_x")


class TestMinimaxAnswerGetToolCalls(unittest.IsolatedAsyncioTestCase):
    def _make_minimax_response(self, tool_calls_data=None):
        message = MagicMock()
        message.content = "response text"
        message.__dict__["reasoning_details"] = None
        if tool_calls_data is None:
            message.tool_calls = None
        else:
            mock_tool_calls = []
            for tc in tool_calls_data:
                mock_tc = MagicMock()
                mock_tc.id = tc["id"]
                mock_tc.function = MagicMock()
                mock_tc.function.name = tc["name"]
                mock_tc.function.arguments = tc["arguments"]
                mock_tool_calls.append(mock_tc)
            message.tool_calls = mock_tool_calls

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message = message
        response.__dict__["usage"] = None
        return response

    async def test_no_tool_calls_returns_none(self):
        response = self._make_minimax_response()
        answer = MinimaxAnswer(response=response, registry=Registry())
        self.assertIsNone(await answer.get_native_toolcalls())

    async def test_tool_calls_extracted_from_response(self):
        response = self._make_minimax_response(
            [
                {"id": "tc_1", "name": "get_data", "arguments": '{"key": "val"}'},
                {"id": "tc_2", "name": "process", "arguments": "{}"},
            ]
        )
        answer = MinimaxAnswer(response=response, registry=Registry())
        result = await answer.get_native_toolcalls()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "tc_1")
        self.assertEqual(result[0]["arguments"], {"key": "val"})
        self.assertEqual(result[1]["name"], "process")


class TestOpenAiToolResultMessage(unittest.TestCase):
    def test_to_llm_message_format(self):
        msg = OpenAiToolResultMessage(
            tool_call_id="call_xyz", content="result text", tool_name="test_tool"
        )
        llm_msg = msg.to_llm_message()
        self.assertEqual(llm_msg["role"], "tool")
        self.assertEqual(llm_msg["tool_call_id"], "call_xyz")
        self.assertEqual(llm_msg["content"], "result text")

    def test_to_json_from_json_roundtrip(self):
        msg = OpenAiToolResultMessage(
            tool_call_id="call_99", content="success", tool_name="test_tool"
        )
        json_str = msg.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["role"], "tool")
        self.assertEqual(data["tool_call_id"], "call_99")

        restored = OpenAiToolResultMessage.from_json(json_str, registry=MagicMock())
        self.assertEqual(restored.tool_call_id, "call_99")
        self.assertEqual(restored.content, "success")
        self.assertEqual(restored.tool_name, "test_tool")

    def test_missing_tool_call_id_crashes(self):
        data = {"role": "tool", "content": "x", "tool_name": "t"}
        with self.assertRaises(KeyError):
            OpenAiToolResultMessage.from_json(json.dumps(data), MagicMock())

    def test_missing_content_crashes(self):
        data = {"role": "tool", "tool_call_id": "x", "tool_name": "t"}
        with self.assertRaises(KeyError):
            OpenAiToolResultMessage.from_json(json.dumps(data), MagicMock())

    def test_missing_tool_name_crashes(self):
        data = {"role": "tool", "tool_call_id": "x", "content": "y"}
        with self.assertRaises(KeyError):
            OpenAiToolResultMessage.from_json(json.dumps(data), MagicMock())

    def test_empty_content(self):
        msg = OpenAiToolResultMessage(
            tool_call_id="call_empty", content="", tool_name="test"
        )
        self.assertEqual(msg.get_content(), "")
        json_str = msg.to_json()
        restored = OpenAiToolResultMessage.from_json(json_str, MagicMock())
        self.assertEqual(restored.content, "")

    def test_repr_contains_id_and_content(self):
        msg = OpenAiToolResultMessage(
            tool_call_id="call_1", content="ok", tool_name="t"
        )
        r = repr(msg)
        self.assertIn("call_1", r)
        self.assertIn("ok", r)


if __name__ == "__main__":
    unittest.main()
