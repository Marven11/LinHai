"""测试DynamicFileContentMessage类。"""

import json
import unittest
from pathlib import Path

from linhai.agent import DynamicFileContentMessage
from linhai.llm import Message


class TestDynamicFileContentMessage(unittest.TestCase):
    """测试DynamicFileContentMessage类。"""

    def setUp(self):
        """创建测试文件。"""
        self.test_file = Path("test_temp_file.txt")
        self.test_file.write_text("Hello World")

    def tearDown(self):
        """清理测试文件。"""
        if self.test_file.exists():
            self.test_file.unlink()

    def test_init(self):
        """测试初始化。"""
        msg = DynamicFileContentMessage(str(self.test_file), False)
        self.assertEqual(msg.filepath, str(self.test_file))
        self.assertFalse(msg.show_line_numbers)

    def test_get_content_without_line_numbers(self):
        """测试get_content不显示行号。"""
        msg = DynamicFileContentMessage(str(self.test_file), False)
        content = msg.get_content()
        self.assertIn("Hello World", content)
        self.assertNotIn("1:", content)

    def test_get_content_with_line_numbers(self):
        """测试get_content显示行号。"""
        msg = DynamicFileContentMessage(str(self.test_file), True)
        content = msg.get_content()
        self.assertIn("Hello World", content)
        self.assertIn("1:", content)

    def test_get_content_reads_latest(self):
        """测试get_content每次读取最新内容。"""
        msg = DynamicFileContentMessage(str(self.test_file), False)
        first_content = msg.get_content()
        self.assertIn("Hello World", first_content)

        self.test_file.write_text("Updated content")
        second_content = msg.get_content()
        self.assertIn("Updated content", second_content)
        self.assertNotIn("Hello World", second_content)

    def test_get_content_file_not_found(self):
        """测试文件不存在时的错误处理。"""
        msg = DynamicFileContentMessage("/nonexistent/file.txt", False)
        content = msg.get_content()
        self.assertIn("error", content.lower())
        self.assertIn("/nonexistent/file.txt", content)

    def test_to_json_saves_only_filepath(self):
        """测试to_json只保存路径和行号设置。"""
        msg = DynamicFileContentMessage(str(self.test_file), True)
        json_str = msg.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["filepath"], str(self.test_file))
        self.assertTrue(data["show_line_numbers"])
        self.assertNotIn("content", data)

    def test_from_json(self):
        """测试from_json正确反序列化。"""
        msg = DynamicFileContentMessage(str(self.test_file), False)
        json_str = msg.to_json()
        restored_msg = DynamicFileContentMessage.from_json(json_str, None)
        self.assertEqual(restored_msg.filepath, msg.filepath)
        self.assertEqual(restored_msg.show_line_numbers, msg.show_line_numbers)

    def test_from_json_reads_latest_content(self):
        """测试从json恢复的消息能读取最新内容。"""
        msg = DynamicFileContentMessage(str(self.test_file), False)
        json_str = msg.to_json()

        self.test_file.write_text("New content after serialization")

        restored_msg = DynamicFileContentMessage.from_json(json_str, None)
        content = restored_msg.get_content()
        self.assertIn("New content after serialization", content)

    def test_to_llm_message(self):
        """测试to_llm_message返回正确格式。"""
        msg = DynamicFileContentMessage(str(self.test_file), False)
        llm_msg = msg.to_llm_message()
        self.assertEqual(llm_msg["role"], "user")
        self.assertIn("Hello World", llm_msg["content"])

    def test_is_message_instance(self):
        """测试是Message的实例。"""
        msg = DynamicFileContentMessage(str(self.test_file), False)
        self.assertIsInstance(msg, Message)


if __name__ == "__main__":
    unittest.main()
