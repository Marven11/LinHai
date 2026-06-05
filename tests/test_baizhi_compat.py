import unittest
import asyncio
import json
from linhai.utils.baizhi_compat import (
    fix_baizhi_messages,
    _is_valid_json,
    _build_dummy_arguments,
)


class TestBaizhiCompat(unittest.IsolatedAsyncioTestCase):
    async def test_valid_json_unchanged(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "arguments": '{"key": "value"}',
                        },
                    }
                ],
            }
        ]
        result = await fix_baizhi_messages(messages)
        self.assertEqual(
            result[0]["tool_calls"][0]["function"]["arguments"],
            '{"key": "value"}',
        )

    async def test_invalid_json_replaced(self):
        invalid_args = "not json at all!!!"
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "arguments": invalid_args,
                        },
                    }
                ],
            }
        ]
        result = await fix_baizhi_messages(messages)
        new_args = result[0]["tool_calls"][0]["function"]["arguments"]
        parsed = json.loads(new_args)
        self.assertIn("notice", parsed)
        self.assertEqual(parsed["original_arguments"], invalid_args)

    async def test_non_assistant_messages_unchanged(self):
        messages = [
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "arguments": '{"valid": true}',
                        },
                    }
                ],
            },
        ]
        result = await fix_baizhi_messages(messages)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "hello")
        self.assertEqual(
            result[1]["tool_calls"][0]["function"]["arguments"],
            '{"valid": true}',
        )

    async def test_no_tool_calls_unchanged(self):
        messages = [
            {"role": "assistant", "content": "Hello, how can I help?"},
            {"role": "user", "content": "test"},
        ]
        result = await fix_baizhi_messages(messages)
        self.assertEqual(result, messages)

    async def test_empty_arguments_unchanged(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "test_tool", "arguments": ""},
                    }
                ],
            }
        ]
        result = await fix_baizhi_messages(messages)
        self.assertEqual(result[0]["tool_calls"][0]["function"]["arguments"], "")

    async def test_mixed_valid_and_invalid(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "valid_tool",
                            "arguments": '{"a": 1}',
                        },
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "invalid_tool",
                            "arguments": "bad json",
                        },
                    },
                ],
            }
        ]
        result = await fix_baizhi_messages(messages)
        tc = result[0]["tool_calls"]
        self.assertEqual(tc[0]["function"]["arguments"], '{"a": 1}')
        self.assertIn("original_arguments", tc[1]["function"]["arguments"])

    async def test_multiple_assistant_messages(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "tool1",
                            "arguments": "bad json 1",
                        },
                    }
                ],
            },
            {"role": "user", "content": "continue"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "tool2",
                            "arguments": "bad json 2",
                        },
                    }
                ],
            },
        ]
        result = await fix_baizhi_messages(messages)
        args0 = result[0]["tool_calls"][0]["function"]["arguments"]
        args2 = result[2]["tool_calls"][0]["function"]["arguments"]
        self.assertIn("bad json 1", args0)
        self.assertIn("bad json 2", args2)

    async def test_is_valid_json_true(self):
        self.assertTrue(await _is_valid_json('{"key": "value"}'))
        self.assertTrue(await _is_valid_json("123"))
        self.assertTrue(await _is_valid_json("[1, 2, 3]"))

    async def test_is_valid_json_false(self):
        self.assertFalse(await _is_valid_json("not json"))
        self.assertFalse(await _is_valid_json("{broken"))
        self.assertFalse(await _is_valid_json(""))

    def test_build_dummy_arguments(self):
        original = "bad json here"
        result = _build_dummy_arguments(original)
        parsed = json.loads(result)
        self.assertIn("notice", parsed)
        self.assertIn("502", parsed["notice"])
        self.assertEqual(parsed["original_arguments"], original)

    async def test_no_function_field(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [{"id": "call_1", "type": "function"}],
            }
        ]
        result = await fix_baizhi_messages(messages)
        self.assertEqual(result, messages)

    async def test_empty_tool_calls_list(self):
        messages = [
            {"role": "assistant", "tool_calls": []},
        ]
        result = await fix_baizhi_messages(messages)
        self.assertEqual(result, messages)


if __name__ == "__main__":
    unittest.main()
