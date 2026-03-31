import unittest
import json
from linhai.utils import (
    simplify_value,
    simplify_toolcall_json,
    parse_and_simplify_toolcall,
)


class TestToolCallCollapse(unittest.TestCase):
    """测试工具调用折叠功能"""

    def test_simplify_value_string_short(self):
        """测试短字符串参数简化"""
        result = simplify_value("short")
        self.assertEqual(result, '"short"')

    def test_simplify_value_string_long(self):
        """测试长字符串参数简化"""
        long_string = "a very long string that should be truncated because it's too long for display"
        result = simplify_value(long_string)
        self.assertEqual(result, '"a very long string that should be tru..."')

    def test_simplify_value_path(self):
        """测试路径参数简化"""
        result = simplify_value("/path/to/file.txt")
        self.assertEqual(result, '"/path/to/file.txt"')

    def test_simplify_value_directory_path(self):
        """测试目录路径（以/结尾）简化，应保留最后一个文件夹名"""
        result = simplify_value("/home/linhai/LinHai-Agent-Worker1/tests/")
        self.assertEqual(result, '".../tests/"')

    def test_simplify_value_directory_path_no_trailing_slash(self):
        """测试目录路径（不以/结尾）简化"""
        result = simplify_value("/home/linhai/LinHai-Agent-Worker1/tests")
        self.assertEqual(result, '".../tests"')

    def test_simplify_value_number(self):
        """测试数字参数简化"""
        result = simplify_value(123)
        self.assertEqual(result, "123")

    def test_simplify_value_dict_short(self):
        """测试短字典参数简化"""
        short_dict = {"key1": "value1", "key2": "value2"}
        result = simplify_value(short_dict)
        self.assertEqual(result, '{"key1": "value1", "key2": "value2"}')

    def test_simplify_value_dict_long(self):
        """测试长字典参数简化"""
        long_dict = {
            "key1": "a very long value that makes this dictionary exceed 80 characters",
            "key2": "value2",
            "key3": "value3",
            "key4": "value4",
            "key5": "value5",
        }
        result = simplify_value(long_dict)
        self.assertIn(
            '{"key1": "a very long value that makes this dic...", ...}', result
        )

    def test_simplify_value_list_short(self):
        """测试短列表参数简化"""
        short_list = ["item1", "item2", "item3"]
        result = simplify_value(short_list)
        self.assertEqual(result, '["item1", "item2", "item3"]')

    def test_simplify_value_list_long(self):
        """测试长列表参数简化"""
        long_list = [
            "a very long item that makes the list exceed 80 characters by having even more text here to ensure the total length is over 80 and even more to guarantee it's really long enough for truncation",
            "another long item to add more length to the list representation",
            "item3",
            "item4",
            "item5",
        ]
        result = simplify_value(long_list)
        self.assertIn('"a very long item that makes the list ..."', result)

    def test_simplify_toolcall_json_normal(self):
        """测试正常工具调用JSON简化"""
        toolcall_json = {
            "name": "read_file",
            "arguments": {"filepath": "test.txt"},
        }
        result = simplify_toolcall_json(toolcall_json)
        self.assertEqual(result, 'read_file(filepath="test.txt")')

    def test_simplify_toolcall_json_error(self):
        """测试错误工具调用JSON简化"""
        # 由于移除了has_error参数，此测试不再适用，改为测试无效输入
        # 无效输入应该在parse_and_simplify_toolcall中处理，所以这里可以删除或修改
        # 我们改为测试空字典的简化（应该返回空参数）
        result = simplify_toolcall_json({})
        self.assertEqual(result, "()")

    def test_parse_and_simplify_toolcall_valid(self):
        """测试解析和简化有效的工具调用JSON"""
        json_str = '{"name": "read_file", "arguments": {"filepath": "test.txt"}}'
        simplified = parse_and_simplify_toolcall(json_str)
        self.assertEqual(simplified, 'read_file(filepath="test.txt")')

    def test_parse_and_simplify_toolcall_invalid_json(self):
        json_str = '{"name": "read_file", "arguments": {'
        simplified = parse_and_simplify_toolcall(json_str)
        self.assertEqual(simplified, "<parse json error>")

    def test_parse_and_simplify_toolcall_empty_string(self):
        """测试解析空字符串"""
        json_str = ""
        simplified = parse_and_simplify_toolcall(json_str)
        self.assertEqual(simplified, "<parse json error>")

    def test_parse_and_simplify_toolcall_normal_no_arguments(self):
        """测试解析没有arguments的正常工具调用"""
        json_str = '{"name": "list_files"}'
        simplified = parse_and_simplify_toolcall(json_str)
        self.assertEqual(simplified, "list_files()")

    def test_parse_and_simplify_toolcall_normal_empty_arguments(self):
        """测试解析arguments为空的正常工具调用"""
        json_str = '{"name": "list_files", "arguments": {}}'
        simplified = parse_and_simplify_toolcall(json_str)
        self.assertEqual(simplified, "list_files()")

    def test_normal_toolcall_not_marked_error(self):
        normal_toolcalls = [
            '{"name": "read_file", "arguments": {"filepath": "test.txt"}}',
            '{"name": "write_file", "arguments": {}}',
            '{"name": "list_files", "arguments": {"dirpath": "./"}}',
            '{"name": "sleep", "arguments": {"seconds": 1.0}}',
            '{"name": "change_directory", "arguments": {"directory": "/some/path"}}',
        ]
        for json_str in normal_toolcalls:
            simplified = parse_and_simplify_toolcall(json_str)
            self.assertNotEqual(simplified, "<parse json error>")

    def test_change_directory_comprehensive(self):
        """全面测试change_directory工具的各种路径情况"""
        test_cases = [
            # (json字符串, 期望不是error toolcall)
            (
                '{"name": "change_directory", "arguments": {"directory": "/home/user"}}',
                True,
            ),
            (
                '{"name": "change_directory", "arguments": {"directory": "./relative/path"}}',
                True,
            ),
            (
                '{"name": "change_directory", "arguments": {"directory": "~/Documents"}}',
                True,
            ),
            (
                '{"name": "change_directory", "arguments": {"directory": "C:\\\\Program Files"}}',
                True,
            ),
            (
                '{"name": "change_directory", "arguments": {"directory": "/path/with spaces/and\\"quotes\\""}}',
                True,
            ),
            ('{"name": "change_directory", "arguments": {"directory": ""}}', True),
            # Windows路径
            (
                '{"name": "change_directory", "arguments": {"directory": "C:\\\\Users\\\\Test"}}',
                True,
            ),
            # 包含特殊字符
            (
                '{"name": "change_directory", "arguments": {"directory": "/path/with\\t tab"}}',
                True,
            ),
            # 非常长路径
            (
                '{"name": "change_directory", "arguments": {"directory": "/very/long/path/that/exceeds/the/typical/length/limit/for/display/purposes"}}',
                True,
            ),
        ]
        for json_str, should_pass in test_cases:
            simplified = parse_and_simplify_toolcall(json_str)
            if should_pass:
                self.assertNotEqual(simplified, "<parse json error>")


if __name__ == "__main__":
    unittest.main()
