"""Test markdown_parser module."""

import unittest
from linhai.markdown_parser import extract_tool_calls, extract_tool_calls_with_errors


class TestMarkdownParser(unittest.TestCase):
    """Test cases for markdown_parser."""

    def test_extract_tool_calls_json(self):
        """Test extracting tool calls with 'json' format."""
        markdown_text = """
```json
{"name": "test_tool", "arguments": {"param": "value"}}
```
"""
        tool_calls = extract_tool_calls(markdown_text)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "test_tool")
        self.assertEqual(tool_calls[0]["arguments"]["param"], "value")

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
"""
        tool_calls, errors = extract_tool_calls_with_errors(markdown_text)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("解析JSON出错", errors[0])

    def test_extract_tool_calls_mixed_formats(self):
        """Test extracting tool calls with mixed 'json' and 'json toolcall' formats."""
        markdown_text = """
```json
{"name": "tool1", "arguments": {"param": "value1"}}
```
```json toolcall
{"name": "tool2", "arguments": {"param": "value2"}}
```
"""
        tool_calls = extract_tool_calls(markdown_text)
        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["name"], "tool1")
        self.assertEqual(tool_calls[1]["name"], "tool2")


if __name__ == "__main__":
    unittest.main()