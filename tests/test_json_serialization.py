import json
import unittest
from unittest.mock import Mock

from linhai.base import (
    SystemMessage,
    UserMessage,
    AssistantMessage,
    MESSAGE_CLASS_REGISTRY,
)
from linhai.tool.base import (
    ToolCallResultMessage,
    SuccessfulToolResult,
    FailedToolResult,
    FileContentToolResult,
    tool_result_from_json,
)


def _mock_registry():
    mock = Mock()
    mock_tool_manager = Mock()
    mock_tool_manager.get_tools_info = Mock(return_value=[])
    mock.get_member_typechecked = Mock(
        side_effect=lambda name, cls=None: (
            mock_tool_manager if name == "tool_manager" else Mock()
        )
    )
    return mock


class TestUserMessageSerialization(unittest.TestCase):
    def test_roundtrip(self):
        original = UserMessage("hello world", "user1")
        restored = UserMessage.from_json(original.to_json(), _mock_registry())
        self.assertEqual(restored.message, "hello world")

    def test_missing_message_crashes(self):
        data = {"role": "user", "name": "x"}
        with self.assertRaises(KeyError):
            UserMessage.from_json(json.dumps(data), _mock_registry())

    def test_extra_fields_ignored(self):
        data = {"role": "user", "message": "hi", "extra_field": 42}
        restored = UserMessage.from_json(json.dumps(data), _mock_registry())
        self.assertEqual(restored.message, "hi")

    def test_unicode_preserved(self):
        text = "中文测试にほんご한국어"
        restored = UserMessage.from_json(UserMessage(text).to_json(), _mock_registry())
        self.assertEqual(restored.message, text)
        self.assertNotIn("\\u", UserMessage(text).to_json())


class TestAssistantMessageSerialization(unittest.TestCase):
    def test_roundtrip_with_reasoning(self):
        original = AssistantMessage("response", "thinking process")
        restored = AssistantMessage.from_json(original.to_json(), _mock_registry())
        self.assertEqual(restored.message, "response")
        self.assertEqual(restored.reasoning_message, "thinking process")

    def test_none_message_roundtrip(self):
        original = AssistantMessage(message=None)
        restored = AssistantMessage.from_json(original.to_json(), _mock_registry())
        self.assertIsNone(restored.get_content())
        self.assertEqual(original.to_llm_message(), restored.to_llm_message())

    def test_missing_message_crashes(self):
        data = {"role": "assistant", "reasoning_message": "thinking"}
        with self.assertRaises(KeyError):
            AssistantMessage.from_json(json.dumps(data), _mock_registry())

    def test_tool_calls_roundtrip(self):
        original = AssistantMessage(message="text")
        original.tool_calls = [
            {
                "id": "call_1",
                "function": {"name": "search", "arguments": '{"q": "test"}'},
                "type": "function",
            }
        ]
        restored = AssistantMessage.from_json(original.to_json(), _mock_registry())
        self.assertIsNotNone(restored.tool_calls)
        self.assertEqual(restored.tool_calls[0]["id"], "call_1")
        self.assertEqual(restored.tool_calls[0]["function"]["name"], "search")


class TestToolCallResultSerialization(unittest.TestCase):
    def test_successful_result_roundtrip(self):
        original = ToolCallResultMessage(
            tool_name="read_file",
            tool_index=0,
            result=SuccessfulToolResult(content="file content"),
            toolcall_arguments={"path": "/tmp"},
        )
        restored = ToolCallResultMessage.from_json(original.to_json(), _mock_registry())
        self.assertEqual(restored.tool_name, "read_file")
        self.assertEqual(restored.tool_index, 0)
        self.assertIsInstance(restored.result, SuccessfulToolResult)
        self.assertEqual(restored.result.content, "file content")
        self.assertEqual(restored.toolcall_arguments, {"path": "/tmp"})

    def test_failed_result_roundtrip(self):
        original = ToolCallResultMessage(
            tool_name="write_file",
            tool_index=2,
            result=FailedToolResult(content="permission denied"),
            toolcall_arguments={},
        )
        restored = ToolCallResultMessage.from_json(original.to_json(), _mock_registry())
        self.assertIsInstance(restored.result, FailedToolResult)
        self.assertEqual(restored.result.content, "permission denied")

    def test_file_content_result_roundtrip(self):
        original = ToolCallResultMessage(
            tool_name="read_file",
            tool_index=0,
            result=FileContentToolResult(
                filepath="/tmp/test.py",
                content="print('hi')",
                show_line_numbers=True,
            ),
            toolcall_arguments={},
        )
        restored = ToolCallResultMessage.from_json(original.to_json(), _mock_registry())
        self.assertIsInstance(restored.result, FileContentToolResult)
        self.assertEqual(restored.result.filepath, "/tmp/test.py")
        self.assertTrue(restored.result.show_line_numbers)

    def test_missing_tool_name_crashes(self):
        data = {
            "tool_index": 0,
            "result": '{"type": "SuccessfulToolResult", "content": "ok"}',
            "toolcall_arguments": {},
        }
        with self.assertRaises(KeyError):
            ToolCallResultMessage.from_json(json.dumps(data), _mock_registry())

    def test_missing_result_crashes(self):
        data = {
            "tool_name": "test",
            "tool_index": 0,
            "toolcall_arguments": {},
        }
        with self.assertRaises(KeyError):
            ToolCallResultMessage.from_json(json.dumps(data), _mock_registry())

    def test_unknown_result_type_crashes(self):
        data = {
            "tool_name": "test",
            "tool_index": 0,
            "result": '{"type": "UnknownType", "content": "ok"}',
            "toolcall_arguments": {},
        }
        with self.assertRaises(RuntimeError):
            ToolCallResultMessage.from_json(json.dumps(data), _mock_registry())

    def test_toolcall_arguments_defaults_empty(self):
        data = {
            "tool_name": "test",
            "tool_index": 0,
            "result": '{"type": "SuccessfulToolResult", "content": "ok"}',
        }
        restored = ToolCallResultMessage.from_json(json.dumps(data), _mock_registry())
        self.assertEqual(restored.toolcall_arguments, {})


class TestRealMessageCombination(unittest.TestCase):
    def test_full_conversation_roundtrip(self):
        registry = _mock_registry()
        messages = [
            SystemMessage(registry=registry),
            UserMessage("what is 2+2?"),
            AssistantMessage("2+2=4"),
            ToolCallResultMessage(
                tool_name="calculator",
                tool_index=0,
                result=SuccessfulToolResult(content="4"),
                toolcall_arguments={},
            ),
            AssistantMessage(message=None),
        ]
        json_strs = [m.to_json() for m in messages]

        restored = [
            SystemMessage.from_json(json_strs[0], registry),
            UserMessage.from_json(json_strs[1], registry),
            AssistantMessage.from_json(json_strs[2], registry),
            ToolCallResultMessage.from_json(json_strs[3], registry),
            AssistantMessage.from_json(json_strs[4], registry),
        ]

        self.assertEqual(restored[1].message, "what is 2+2?")
        self.assertEqual(restored[2].message, "2+2=4")
        self.assertIsInstance(restored[3].result, SuccessfulToolResult)
        self.assertIsNone(restored[4].get_content())

    def test_unicode_through_full_pipeline(self):
        chinese = "你好世界🎉"
        registry = _mock_registry()
        original = AssistantMessage(chinese)
        json_str = original.to_json()
        self.assertIn(chinese, json_str)
        restored = AssistantMessage.from_json(json_str, registry)
        self.assertEqual(restored.get_content(), chinese)


class TestMessageClassRegistry(unittest.TestCase):
    def test_key_types_registered(self):
        for name in [
            "UserMessage",
            "AssistantMessage",
            "SystemMessage",
            "ToolCallResultMessage",
            "RuntimeMessage",
        ]:
            self.assertIn(name, MESSAGE_CLASS_REGISTRY)

    def test_registry_values_have_from_json(self):
        for name, cls in MESSAGE_CLASS_REGISTRY.items():
            self.assertTrue(callable(getattr(cls, "from_json", None)))
