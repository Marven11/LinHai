"""Unit tests for ToolResultMessage with large content handling."""

import unittest
class TestToolResultMessage(unittest.TestCase):
    """Test cases for ToolResultMessage with large content handling."""

    def test_tool_result_message_with_short_content(self):
        """测试短内容情况，应直接返回内容"""
        from linhai.tool.main import ToolResultMessage

        # 短内容
        short_content = "This is a short message"
        message = ToolResultMessage(short_content)
        llm_message = message.to_llm_message()

        self.assertEqual(llm_message.get("content", ""), short_content)
        self.assertEqual(llm_message["role"], "user")
        self.assertEqual(llm_message.get("name", ""), "tool-result")

    def test_tool_result_message_with_long_content(self):
        """测试长内容情况，应保存到临时文件并返回文件信息"""
        from linhai.tool.main import ToolResultMessage
        import tempfile
        import os

        # 生成长内容（超过50000字符）
        long_content = "A" * 50001  # 50001个字符
        message = ToolResultMessage(long_content)
        llm_message = message.to_llm_message()

        # 验证返回的消息包含文件信息
        content = str(llm_message.get("content", ""))
        self.assertIn("内容过长", content)
        self.assertIn("已保存到临时文件", content)
        self.assertIn("大小", content)
        self.assertIn("字节", content)
        self.assertEqual(llm_message["role"], "user")
        self.assertEqual(llm_message.get("name", ""), "tool-result")

        # 验证返回的消息包含文件信息
        content = str(llm_message.get("content", ""))
        self.assertIsNotNone(content)
        self.assertIn("已保存到临时文件", content)
        self.assertIn("大小", content)

        # 使用更健壮的方法提取文件路径
        import re

        file_match = re.search(
            r"已保存到临时文件：([^。]+)", str(llm_message.get("content", ""))
        )
        self.assertIsNotNone(file_match, "文件路径未在消息中找到")
        assert file_match is not None
        file_path = file_match.group(1).strip()

        # 验证临时文件存在且内容正确
        self.assertTrue(os.path.exists(file_path), f"临时文件不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        self.assertEqual(file_content, long_content)

        # 清理临时文件
        os.unlink(file_path)

    def test_tool_result_message_with_custom_max_length(self):
        """测试自定义最大长度限制"""
        from linhai.tool.main import ToolResultMessage
        import os

        # 设置自定义最大长度为1000
        custom_max_length = 1000

        # 生成刚好超过自定义限制的内容
        long_content = "A" * 1001  # 1001个字符
        message = ToolResultMessage(long_content, max_output_length=custom_max_length)
        llm_message = message.to_llm_message()

        # 验证返回的消息包含文件信息
        content = str(llm_message.get("content", ""))
        self.assertIn("内容过长", content)
        self.assertIn("已保存到临时文件", content)
        self.assertIn("大小", content)
        self.assertIn("字节", content)

        # 使用更健壮的方法提取文件路径
        import re

        file_match = re.search(
            r"已保存到临时文件：([^。]+)", str(llm_message.get("content", ""))
        )
        self.assertIsNotNone(file_match, "文件路径未在消息中找到")
        assert file_match is not None
        file_path = file_match.group(1).strip()

        # 验证临时文件存在且内容正确
        self.assertTrue(os.path.exists(file_path), f"临时文件不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        self.assertEqual(file_content, long_content)

        # 清理临时文件
        os.unlink(file_path)

        # 测试刚好在限制内的内容
        short_content = "A" * 1000  # 1000个字符
        message = ToolResultMessage(short_content, max_output_length=custom_max_length)
        llm_message = message.to_llm_message()
        self.assertEqual(llm_message.get("content", ""), short_content)

    def test_tool_result_message_with_json_content(self):
        """测试JSON内容情况"""
        from linhai.tool.main import ToolResultMessage

        # JSON内容
        json_content = {"key": "value", "number": 42}
        message = ToolResultMessage(json_content)
        llm_message = message.to_llm_message()

        # 应该是JSON字符串
        self.assertEqual(
            llm_message.get("content", ""), '{"key": "value", "number": 42}'
        )
        self.assertEqual(llm_message["role"], "user")
        self.assertEqual(llm_message.get("name", ""), "tool-result")

    def test_tool_result_message_with_long_json_content(self):
        """测试长JSON内容情况，应保存到临时文件"""
        from linhai.tool.main import ToolResultMessage
        import tempfile
        import os

        # 生成长JSON内容
        long_json_content = {"data": "A" * 50000}  # 超过50000字符
        message = ToolResultMessage(long_json_content)
        llm_message = message.to_llm_message()

        # 验证返回的消息包含文件信息
        content = str(llm_message.get("content", ""))
        self.assertIn("内容过长", content)
        self.assertIn("已保存到临时文件", content)
        self.assertIn("大小", content)
        self.assertIn("字节", content)

        # 验证返回的消息包含文件信息
        content = str(llm_message.get("content", ""))
        self.assertIsNotNone(content)
        self.assertIn("已保存到临时文件", content)
        self.assertIn("大小", content)

        # 使用更健壮的方法提取文件路径
        import re

        file_match = re.search(
            r"已保存到临时文件：([^。]+)", str(llm_message.get("content", ""))
        )
        self.assertIsNotNone(file_match, "文件路径未在消息中找到")
        assert file_match is not None
        file_path = file_match.group(1).strip()

        # 验证临时文件存在且内容正确
        self.assertTrue(os.path.exists(file_path), f"临时文件不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        self.assertEqual(file_content, '{"data": "' + "A" * 50000 + '"}')

        # 清理临时文件
        os.unlink(file_path)

    def test_tool_result_message_includes_line_count_for_long_content(self):
        """测试长内容时包含行数提醒"""
        from linhai.tool.main import ToolResultMessage
        import os

        # 生成长内容，包含多个换行符
        lines = ["Line " + str(i) for i in range(1000)]  # 1000行
        long_content = "\n".join(lines)  # 999个换行符，共1000行
        # 确保内容长度超过50000字符
        while len(long_content) < 50000:
            long_content += "\nAdditional line to make it longer"

        message = ToolResultMessage(long_content)
        llm_message = message.to_llm_message()

        # 验证返回的消息包含行数信息
        content_str = str(llm_message.get("content", ""))
        self.assertIn("共", content_str)
        self.assertIn("行", content_str)

        # 计算预期的行数
        expected_line_count = long_content.count("\n") + 1
        self.assertIn(str(expected_line_count), content_str)

        # 验证其他文件信息也存在
        self.assertIn("内容过长", content_str)
        self.assertIn("已保存到临时文件", content_str)
        self.assertIn("大小", content_str)
        self.assertIn("字节", content_str)

        # 提取文件路径并验证临时文件
        import re

        file_match = re.search(
            r"已保存到临时文件：([^。]+)", str(llm_message.get("content", ""))
        )
        self.assertIsNotNone(file_match, "文件路径未在消息中找到")
        assert file_match is not None
        file_path = file_match.group(1).strip()

        # 验证临时文件存在且内容正确
        self.assertTrue(os.path.exists(file_path), f"临时文件不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        self.assertEqual(file_content, long_content)

        # 清理临时文件
        os.unlink(file_path)


