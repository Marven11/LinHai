import unittest
import json
from unittest.mock import MagicMock, AsyncMock

from linhai.base import AssistantMessage, OpenAiToolResultMessage
from linhai.type_hints import FunctionCall, OpenAiToolCall
from linhai.llm import OpenAiAnswer, MinimaxAnswer
from linhai.registry import Registry


class TestOpenAiToolCallTypedDict(unittest.TestCase):
    def test_create_openai_toolcall(self):
        tc = OpenAiToolCall(
            id="call_123",
            function=FunctionCall(
                name="get_weather", arguments='{"location": "Hangzhou"}'
            ),
            type="function",
        )
        self.assertEqual(tc["id"], "call_123")
        self.assertEqual(tc["function"]["name"], "get_weather")
        self.assertEqual(tc["type"], "function")

    def test_openai_toolcall_json_roundtrip(self):
        tc = OpenAiToolCall(
            id="call_456",
            function=FunctionCall(name="search", arguments='{"query": "test"}'),
            type="function",
        )
        serialized = json.dumps(tc)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized["id"], "call_456")
        self.assertEqual(deserialized["function"]["name"], "search")


class TestAssistantMessageToolCalls(unittest.TestCase):
    def test_assistant_message_without_tool_calls(self):
        msg = AssistantMessage(message="hello")
        self.assertIsNone(msg.tool_calls)
        llm_msg = msg.to_llm_message()
        self.assertNotIn("tool_calls", llm_msg)

    def test_assistant_message_with_tool_calls(self):
        tool_calls = [
            OpenAiToolCall(
                id="call_1",
                function=FunctionCall(name="func", arguments="{}"),
                type="function",
            )
        ]
        msg = AssistantMessage(message="")
        msg.tool_calls = tool_calls
        self.assertEqual(len(msg.tool_calls), 1)
        llm_msg = msg.to_llm_message()
        self.assertIn("tool_calls", llm_msg)
        self.assertEqual(llm_msg["tool_calls"][0]["id"], "call_1")

    def test_assistant_message_to_json_from_json(self):
        tool_calls = [
            OpenAiToolCall(
                id="call_2",
                function=FunctionCall(name="test_fn", arguments='{"a": 1}'),
                type="function",
            )
        ]
        msg = AssistantMessage(
            message="response",
            reasoning_message="thinking",
        )
        msg.tool_calls = tool_calls
        json_str = msg.to_json()
        data = json.loads(json_str)
        self.assertIn("tool_calls", data)
        self.assertEqual(data["tool_calls"][0]["id"], "call_2")

        restored = AssistantMessage.from_json(json_str, registry=MagicMock())
        self.assertEqual(restored.message, "response")
        self.assertEqual(restored.reasoning_message, "thinking")
        self.assertIsNotNone(restored.tool_calls)
        self.assertEqual(restored.tool_calls[0]["id"], "call_2")


class TestOpenAiAnswerGetToolCalls(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Registry()
        self.mock_stream = AsyncMock()

    async def test_no_tool_calls_returns_none(self):
        answer = OpenAiAnswer(
            stream=self.mock_stream,
            registry=self.registry,
        )
        self.assertIsNone(answer.get_openai_toolcalls())

    async def test_tool_calls_assembled_from_parts(self):
        answer = OpenAiAnswer(
            stream=self.mock_stream,
            registry=self.registry,
        )
        answer._openai_toolcall_parts = {
            0: {"id": "call_a", "name": "func_a", "args": '{"x": 1}'},
            1: {"id": "call_b", "name": "func_b", "args": "{}"},
        }
        result = answer.get_openai_toolcalls()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "call_a")
        self.assertEqual(result[0]["function"]["name"], "func_a")
        self.assertEqual(result[1]["function"]["name"], "func_b")

    async def test_incomplete_tool_call_skipped(self):
        answer = OpenAiAnswer(
            stream=self.mock_stream,
            registry=self.registry,
        )
        answer._openai_toolcall_parts = {
            0: {"id": None, "name": None, "args": ""},
        }
        self.assertIsNone(answer.get_openai_toolcalls())

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


class TestMinimaxAnswerGetToolCalls(unittest.TestCase):
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

    def test_no_tool_calls_returns_none(self):
        response = self._make_minimax_response()
        answer = MinimaxAnswer(
            response=response,
            registry=Registry(),
        )
        self.assertIsNone(answer.get_openai_toolcalls())

    def test_tool_calls_extracted_from_response(self):
        response = self._make_minimax_response(
            [
                {"id": "tc_1", "name": "get_data", "arguments": '{"key": "val"}'},
                {"id": "tc_2", "name": "process", "arguments": "{}"},
            ]
        )
        answer = MinimaxAnswer(
            response=response,
            registry=Registry(),
        )
        result = answer.get_openai_toolcalls()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "tc_1")
        self.assertEqual(result[0]["function"]["name"], "get_data")
        self.assertEqual(result[0]["function"]["arguments"], '{"key": "val"}')
        self.assertEqual(result[1]["id"], "tc_2")

    def test_get_message_includes_tool_calls(self):
        response = self._make_minimax_response(
            [
                {"id": "tc_3", "name": "do_thing", "arguments": "{}"},
            ]
        )
        answer = MinimaxAnswer(
            response=response,
            registry=Registry(),
        )
        msg = answer.get_message()
        self.assertIsInstance(msg, AssistantMessage)
        self.assertIsNotNone(msg.tool_calls)
        self.assertEqual(msg.tool_calls[0]["id"], "tc_3")


class TestOpenAiToolResultMessage(unittest.TestCase):
    def test_basic_construction(self):
        msg = OpenAiToolResultMessage(tool_call_id="call_abc", content="42")
        self.assertEqual(msg.tool_call_id, "call_abc")
        self.assertEqual(msg.content, "42")
        self.assertEqual(msg.get_content(), "42")

    def test_to_llm_message(self):
        msg = OpenAiToolResultMessage(tool_call_id="call_xyz", content="result text")
        llm_msg = msg.to_llm_message()
        self.assertEqual(llm_msg["role"], "tool")
        self.assertEqual(llm_msg["tool_call_id"], "call_xyz")
        self.assertEqual(llm_msg["content"], "result text")

    def test_repr(self):
        msg = OpenAiToolResultMessage(tool_call_id="call_1", content="ok")
        r = repr(msg)
        self.assertIn("call_1", r)
        self.assertIn("ok", r)

    def test_to_json_from_json_roundtrip(self):
        msg = OpenAiToolResultMessage(tool_call_id="call_99", content="success")
        json_str = msg.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["role"], "tool")
        self.assertEqual(data["tool_call_id"], "call_99")
        self.assertEqual(data["content"], "success")

        restored = OpenAiToolResultMessage.from_json(json_str, registry=MagicMock())
        self.assertEqual(restored.tool_call_id, "call_99")
        self.assertEqual(restored.content, "success")


if __name__ == "__main__":
    unittest.main()
