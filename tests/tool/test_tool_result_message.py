"""Unit tests for ToolCallResultMessage with large content handling."""

import unittest
import os
import re
import tempfile
from linhai.tool.base import ToolResultSuccess, ToolResultFailed


class TestToolCallResultMessage(unittest.TestCase):
    """Test cases for ToolCallResultMessage with large content handling."""

    def test_tool_result_message_with_short_content(self):
        """测试短内容情况，应直接返回内容"""
        from linhai.tool.main import ToolCallResultMessage

        short_content = "This is a short message"
        result = ToolResultSuccess(content=short_content)
        message = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=result,
        )
        llm_message = message.to_llm_message()

        # 工具结果消息现在包含格式标记
        self.assertEqual(llm_message["role"], "user")

    def test_tool_result_message_with_long_content_by_chars(self):
        """测试长内容情况，应按字符分块保存到多个文件"""
        from linhai.tool.main import ToolCallResultMessage

        long_content = "A" * 50001  # 50001个字符，1行
        result = ToolResultSuccess(content=long_content)
        message = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=result,
        )
        llm_message = message.to_llm_message()

        content = str(llm_message.get("content", ""))
        self.assertIn("内容过长", content)
        self.assertIn("已按字符分块保存", content)
        self.assertIn("每10000字符一个文件", content)
        self.assertEqual(llm_message["role"], "user")

        file_paths = re.findall(r"- (\S+_chars_\d+-\d+\.txt)", content)
        self.assertGreater(len(file_paths), 1, "应该生成多个文件")

        reconstructed_content = ""
        for file_path in file_paths:
            self.assertTrue(os.path.exists(file_path), f"临时文件不存在: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                reconstructed_content += file_content
            os.unlink(file_path)

        self.assertEqual(reconstructed_content, long_content)

    def test_tool_result_message_with_long_content_by_lines(self):
        """测试长内容情况，应按行分块保存到多个文件"""
        from linhai.tool.main import ToolCallResultMessage

        lines = [f"Line {i}: {'A' * 50}" for i in range(1200)]  # 1200行，每行约55字符
        long_content = "\n".join(lines)
        result = ToolResultSuccess(content=long_content)
        message = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=result,
        )
        llm_message = message.to_llm_message()

        content = str(llm_message.get("content", ""))
        self.assertIn("内容过长", content)
        self.assertIn("已按行分块保存", content)
        self.assertIn("每800行一个文件", content)
        self.assertEqual(llm_message["role"], "user")

        file_paths = re.findall(r"- (\S+_lines_\d+-\d+\.txt)", content)
        self.assertGreater(len(file_paths), 1, "应该生成多个文件")

        reconstructed_lines = []
        for file_path in file_paths:
            self.assertTrue(os.path.exists(file_path), f"临时文件不存在: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                reconstructed_lines.extend(file_content.split("\n"))
            os.unlink(file_path)

        reconstructed_lines = [line for line in reconstructed_lines if line]
        self.assertEqual(len(reconstructed_lines), len(lines))
        self.assertEqual(reconstructed_lines, lines)

    def test_tool_result_message_with_custom_max_length(self):
        """测试自定义最大长度限制"""
        from linhai.tool.main import ToolCallResultMessage

        custom_max_length = 1000

        long_content = "A" * 1001  # 1001个字符
        result = ToolResultSuccess(content=long_content)
        message = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=result,
            max_output_length=custom_max_length,
        )
        llm_message = message.to_llm_message()

        content = str(llm_message.get("content", ""))
        self.assertIn("内容过长", content)
        self.assertIn("已按字符分块保存", content)
        self.assertIn("每10000字符一个文件", content)

        file_paths = re.findall(r"- (\S+_chars_\d+-\d+\.txt)", content)
        self.assertEqual(len(file_paths), 1, "应该生成一个文件")

        for file_path in file_paths:
            self.assertTrue(os.path.exists(file_path), f"临时文件不存在: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            self.assertEqual(file_content, long_content)
            os.unlink(file_path)

        short_content = "A" * 1000  # 1000个字符
        result = ToolResultSuccess(content=short_content)
        message = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=result,
            max_output_length=custom_max_length,
        )
        llm_message = message.to_llm_message()
        # 工具结果消息现在包含格式标记

    def test_tool_result_message_with_json_content(self):
        """测试JSON内容情况"""
        from linhai.tool.main import ToolCallResultMessage

        json_content = {"key": "value", "number": 42}
        result = ToolResultSuccess(content=str(json_content))
        message = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=result,
        )
        llm_message = message.to_llm_message()

        self.assertEqual(llm_message["role"], "user")

    def test_tool_result_message_with_long_json_content(self):
        """测试长JSON内容情况，应分块保存到文件"""
        from linhai.tool.main import ToolCallResultMessage

        long_json_content = {"data": "A" * 50000}  # 超过50000字符
        result = ToolResultSuccess(content=str(long_json_content))
        message = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=result,
        )
        llm_message = message.to_llm_message()

        content = str(llm_message.get("content", ""))
        self.assertIn("内容过长", content)
        self.assertIn("已按字符分块保存", content)
        self.assertIn("每10000字符一个文件", content)

        file_paths = re.findall(r"- (\S+_chars_\d+-\d+\.txt)", content)
        self.assertGreater(len(file_paths), 1, "应该生成多个文件")

        reconstructed_content = ""
        for file_path in file_paths:
            self.assertTrue(os.path.exists(file_path), f"临时文件不存在: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                reconstructed_content += file_content
            os.unlink(file_path)

        self.assertEqual(reconstructed_content, '{"data": "' + "A" * 50000 + '"}')

    def test_tool_result_message_includes_line_count_for_long_content(self):
        """测试长内容时包含行数信息"""
        from linhai.tool.main import ToolCallResultMessage

        lines = ["Line " + str(i) for i in range(1000)]  # 1000行
        long_content = "\n".join(lines)  # 999个换行符，共1000行
        while len(long_content) < 50000:
            long_content += "\nAdditional line to make it longer"

        result = ToolResultSuccess(content=long_content)
        message = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=result,
        )
        llm_message = message.to_llm_message()

        content_str = str(llm_message.get("content", ""))
        self.assertIn("共", content_str)
        self.assertIn("行", content_str)

        expected_line_count = long_content.count("\n") + 1
        self.assertIn(str(expected_line_count), content_str)

        self.assertIn("内容过长", content_str)
        self.assertIn("已按行分块保存", content_str)
        self.assertIn("每800行一个文件", content_str)

        file_paths = re.findall(r"- (\S+_lines_\d+-\d+\.txt)", content_str)
        self.assertGreater(len(file_paths), 1, "应该生成多个文件")

        reconstructed_content = ""
        for file_path in file_paths:
            self.assertTrue(os.path.exists(file_path), f"临时文件不存在: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                reconstructed_content += file_content
            os.unlink(file_path)

        self.assertEqual(reconstructed_content, long_content)
