"""Unit tests for append_file with empty line checking."""

import unittest
import tempfile
import os
from pathlib import Path

from linhai.machine_control.master_host.file import append_file


class TestAppendFile(unittest.TestCase):
    """Test cases for append_file with empty line checking."""

    def test_append_file_with_empty_line_default(self):
        """测试默认行为（assume_empty_line=True）当文件以换行符结尾时。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_file.write("Line 1\nLine 2\n")
            temp_path = temp_file.name

        try:
            result = append_file(temp_path, "Line 3")
            self.assertIn("成功写入文件", result.content)

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content, "Line 1\nLine 2\nLine 3")
        finally:
            os.unlink(temp_path)

    def test_append_file_without_empty_line_default(self):
        """测试默认行为（assume_empty_line=True）当文件不以换行符结尾时。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_file.write("Line 1\nLine 2")  # 没有结尾换行符
            temp_path = temp_file.name

        try:
            result = append_file(temp_path, "Line 3")
            self.assertIn("错误：使用assume_empty_line假设原文件末尾有换行", result.content)
            # 文件内容不应被修改，因为返回了错误
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content, "Line 1\nLine 2")  # 文件应保持不变
        finally:
            os.unlink(temp_path)

    def test_append_file_without_empty_line_default_warning(self):
        """测试默认行为（assume_empty_line=True）当文件不以换行符结尾且新内容也不以换行符开头时产生错误。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_file.write("Line 1\nLine 2")  # 没有结尾换行符
            temp_path = temp_file.name

        try:
            result = append_file(temp_path, "Line 3")
            self.assertIn("错误：使用assume_empty_line假设原文件末尾有换行", result.content)
            # 文件内容不应被修改，因为返回了错误
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content, "Line 1\nLine 2")  # 文件应保持不变
        finally:
            os.unlink(temp_path)

    def test_append_file_with_empty_line_false(self):
        """测试assume_empty_line=False时直接拼接内容。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_file.write("Line 1\nLine 2")  # 没有结尾换行符
            temp_path = temp_file.name

        try:
            result = append_file(temp_path, "Line 3", assume_empty_line=False)
            self.assertIn("成功写入文件", result.content)

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content, "Line 1\nLine 2Line 3")
        finally:
            os.unlink(temp_path)

    def test_append_file_to_new_file(self):
        """测试追加内容到新文件。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_path = temp_file.name

        try:
            # 新文件为空，使用assume_empty_line=False避免换行检查
            result = append_file(temp_path, "Line 1", assume_empty_line=False)
            self.assertIn("成功写入文件", result.content)

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content, "Line 1")
        finally:
            os.unlink(temp_path)

    def test_append_file_with_newline_content(self):
        """测试新内容以换行符开头时的情况。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_file.write("Line 1\nLine 2")  # 没有结尾换行符
            temp_path = temp_file.name

        try:
            result = append_file(temp_path, "\nLine 3")  # 新内容以换行符开头
            self.assertIn("成功写入文件", result.content)

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content, "Line 1\nLine 2\nLine 3")
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()
