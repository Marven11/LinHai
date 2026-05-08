"""Test markdown_parser module."""

import unittest
from linhai.markdown_parser import extract_tool_calls, extract_tool_calls_with_errors


class TestMarkdownParser(unittest.TestCase):
    """Test cases for markdown_parser."""

    def test_extract_tool_calls_json_toolcall(self):
        """Test extracting tool calls with 'json toolcall' format."""
        markdown_text = """
```json toolcall
{"name": "test_tool", "arguments": {"param": "value"}}
```
"""
        tool_calls = extract_tool_calls(markdown_text)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "test_tool")
        self.assertEqual(tool_calls[0]["arguments"]["param"], "value")

    def test_extract_tool_calls_with_errors(self):
        """Test extracting tool calls with errors."""
        markdown_text = """
```json toolcall
{"name": "test_tool", "arguments": {"param": "value"}}
```
```json toolcall
invalid json
```
```json toolcall
["not", "an", "object"]
```
```json toolcall
{"name": "missing_arguments"}
```
```json toolcall
{"arguments": {"missing_name": "test"}}
```
"""
        tool_calls, errors = extract_tool_calls_with_errors(markdown_text)

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "test_tool")

        self.assertEqual(len(errors), 4)
        self.assertIn("JSON格式无效", errors[0])
        self.assertIn("不是对象类型", errors[1])
        self.assertIn("缺少必需的'arguments'字段", errors[2])
        self.assertIn("缺少必需的'name'字段", errors[3])

    def test_extract_tool_calls_with_secret(self):
        """Test extracting tool calls with with_secret field."""
        markdown_text = """
```json toolcall
{"name": "secret_tool", "arguments": {}, "with_secret": ["API_KEY"]}
```
```json toolcall
{"name": "assertive_tool", "arguments": {"x": 1}, "assert_success": false}
```
"""
        tool_calls, errors = extract_tool_calls_with_errors(markdown_text)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(tool_calls), 2)

        self.assertEqual(tool_calls[0]["name"], "secret_tool")
        self.assertEqual(tool_calls[0]["arguments"], {})
        self.assertEqual(tool_calls[0].get("with_secret"), ["API_KEY"])

        self.assertEqual(tool_calls[1]["name"], "assertive_tool")
        self.assertEqual(tool_calls[1]["arguments"], {"x": 1})
        self.assertEqual(tool_calls[1].get("assert_success"), False)

    def test_extract_tool_calls_returns_toolcalldict(self):
        """Test that returned dict has ToolCallDict structure."""
        from linhai.type_hints import ToolCallDict

        markdown_text = """
```json toolcall
{"name": "mytool", "arguments": {"a": 1}}
```
"""
        tool_calls, _ = extract_tool_calls_with_errors(markdown_text)

        tc = tool_calls[0]
        self.assertIsInstance(tc, dict)
        self.assertIn("name", tc)
        self.assertIn("arguments", tc)


if __name__ == "__main__":
    unittest.main()
