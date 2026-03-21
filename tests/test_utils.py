"""Unit tests for utils module."""

import unittest
import re
import json
from linhai.utils import generate_id, simplify_toolcall_json


class TestUtils(unittest.TestCase):
    """Test cases for utils functions."""

    def test_generate_id_format(self):
        """Test generate_id function output format."""
        terminal_id = generate_id("terminal")
        self.assertTrue(terminal_id.startswith("terminal_"))

        large_message_id = generate_id("largemessage")
        self.assertTrue(large_message_id.startswith("largemessage_"))

        custom_id = generate_id("custom")
        self.assertTrue(custom_id.startswith("custom_"))

    def test_generate_id_length(self):
        """Test generate_id function output length."""
        terminal_id = generate_id("terminal")
        expected_length = len("terminal_") + 12
        self.assertEqual(len(terminal_id), expected_length)

        large_message_id = generate_id("largemessage")
        expected_length = len("largemessage_") + 12
        self.assertEqual(len(large_message_id), expected_length)

    def test_generate_id_hex_format(self):
        """Test generate_id function hex part format."""
        terminal_id = generate_id("terminal")
        parts = terminal_id.split("_")
        self.assertEqual(len(parts), 2)
        hex_part = parts[1]

        self.assertEqual(len(hex_part), 12)
        self.assertTrue(re.match(r"^[0-9a-f]{12}$", hex_part))

    def test_generate_id_uniqueness(self):
        """Test generate_id function produces unique IDs."""
        ids = set()
        for _ in range(100):
            terminal_id = generate_id("terminal")
            large_message_id = generate_id("largemessage")
            ids.add(terminal_id)
            ids.add(large_message_id)

        self.assertEqual(len(ids), 200)

    def test_simplify_toolcall_json_one_param(self):
        """Test simplify_toolcall_json with one parameter."""
        toolcall = {"name": "sleep", "arguments": {"seconds": 5}}
        result = simplify_toolcall_json(toolcall)
        self.assertEqual(result, "sleep(seconds=5)")

    def test_simplify_toolcall_json_two_params(self):
        """Test simplify_toolcall_json with two parameters."""
        toolcall = {
            "name": "http_request",
            "arguments": {"method": "GET", "url": "https://example.com"},
        }
        result = simplify_toolcall_json(toolcall)
        self.assertEqual(
            result, 'http_request(method="GET", url="https://example.com")'
        )

    def test_simplify_toolcall_json_three_params(self):
        """Test simplify_toolcall_json with three parameters."""
        toolcall = {
            "name": "replace_file_content",
            "arguments": {
                "filepath": "/tmp/test.txt",
                "old": "old_text",
                "new": "new_text",
            },
        }
        result = simplify_toolcall_json(toolcall)
        expected = 'replace_file_content( \n    filepath="/tmp/test.txt",\n    old="old_text",\n    new="new_text"\n)'
        self.assertEqual(result, expected)

    def test_simplify_toolcall_json_four_params(self):
        """Test simplify_toolcall_json with four parameters."""
        toolcall = {
            "name": "some_tool",
            "arguments": {
                "arg1": "value1",
                "arg2": "value2",
                "arg3": "value3",
                "arg4": "value4",
            },
        }
        result = simplify_toolcall_json(toolcall)
        expected = 'some_tool( \n    arg1="value1",\n    arg2="value2",\n    arg3="value3",\n    arg4="value4"\n)'
        self.assertEqual(result, expected)

    def test_simplify_toolcall_json_no_arguments(self):
        """Test simplify_toolcall_json with empty arguments."""
        toolcall = {"name": "no_args_tool", "arguments": {}}
        result = simplify_toolcall_json(toolcall)
        self.assertEqual(result, "no_args_tool()")

    def test_simplify_toolcall_json_with_path_argument(self):
        """Test simplify_toolcall_json with a long file path."""
        toolcall = {
            "name": "read_file",
            "arguments": {"filepath": "/very/long/path/to/some/interesting/file.txt"},
        }
        result = simplify_toolcall_json(toolcall)
        self.assertEqual(result, 'read_file(filepath=".../file.txt")')

    def test_simplify_toolcall_json_sed_expression_with_comma(self):
        """Test sed expression with comma range is not treated as path."""
        toolcall = {
            "name": "read_file_with_sed",
            "arguments": {
                "filepath": "/some/file.txt",
                "expression": "/JS_EvalFunction/,+30p",
            },
        }
        result = simplify_toolcall_json(toolcall)
        self.assertIn('expression="/JS_EvalFunction/,+30p"', result)

    def test_simplify_toolcall_json_sed_expression_with_plus(self):
        """Test sed expression with + offset is not treated as path."""
        toolcall = {
            "name": "modify_file_with_sed",
            "arguments": {
                "filepath": "/path/to/file.txt",
                "expression": "1,+5s/old/new/",
            },
        }
        result = simplify_toolcall_json(toolcall)
        self.assertIn('expression="1,+5s/old/new/"', result)

    def test_simplify_toolcall_json_sed_expression_with_caret(self):
        """Test sed expression with regex pattern starting with caret."""
        toolcall = {
            "name": "read_file_with_sed",
            "arguments": {
                "filepath": "/file.txt",
                "expression": "/^JSValue JS_Eval\\b/,/^}$/p",
            },
        }
        result = simplify_toolcall_json(toolcall)
        self.assertIn('expression="/^JSValue JS_Eval\\\\b/,/^}$/p"', result)


if __name__ == "__main__":
    unittest.main()
