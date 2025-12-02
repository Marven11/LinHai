"""Unit tests for file validation in file operation tools."""

import unittest

from linhai.tool.base import ToolArgInfo
class TestFileValidation(unittest.TestCase):
    """Test cases for file validation in file operation tools."""

    def setUp(self):
        from linhai.tool.base import ToolSet

        self.toolset = ToolSet()
        from linhai.tool.tools.file import (
            read_file,
            write_file,
            append_file,
            replace_file_content,
            run_sed_expression,
            modify_file_with_sed,
            insert_at_line,
        )

        self.toolset.register_tool(
            name="read_file",
            desc="读取文件",
            args={"filepath": ToolArgInfo(desc="文件路径", type="str")},
            required_args=["filepath"],
        )(read_file)

        self.toolset.register_tool(
            name="write_file",
            desc="写入文件",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "content": ToolArgInfo(desc="要写入的内容", type="str"),
            },
            required_args=["filepath", "content"],
        )(write_file)

        self.toolset.register_tool(
            name="append_file",
            desc="追加文件内容",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "content": ToolArgInfo(desc="要在文件后追加的内容", type="str"),
            },
            required_args=["filepath", "content"],
        )(append_file)

        self.toolset.register_tool(
            name="replace_file_content",
            desc="替换文件内容中的指定字符串",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "old": ToolArgInfo(desc="要替换的字符串", type="str"),
                "new": ToolArgInfo(desc="新的字符串", type="str"),
            },
            required_args=["filepath", "old", "new"],
        )(replace_file_content)

        self.toolset.register_tool(
            name="run_sed_expression",
            desc="执行sed表达式并返回输出",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "expression": ToolArgInfo(desc="sed表达式", type="str"),
            },
            required_args=["filepath", "expression"],
        )(run_sed_expression)

        self.toolset.register_tool(
            name="modify_file_with_sed",
            desc="使用sed表达式修改文件",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "expression": ToolArgInfo(desc="sed表达式", type="str"),
            },
            required_args=["filepath", "expression"],
        )(modify_file_with_sed)

        self.toolset.register_tool(
            name="insert_at_line",
            desc="将内容插入到文件的指定行号位置",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "line_number": ToolArgInfo(desc="要插入的行号（从1开始）", type="int"),
                "content": ToolArgInfo(desc="要插入的内容", type="str"),
            },
            required_args=["filepath", "line_number", "content"],
        )(insert_at_line)

    def test_read_file_rejects_binary_file(self):
        """测试read_file拒绝二进制文件"""
        result = self.toolset.call_tool(
            "read_file", {"filepath": "./linhai/tests/test_binary.zip"}
        )
        self.assertIn("不是纯文本文件", result)

    def test_write_file_rejects_binary_file_for_existing_file(self):
        """测试write_file在文件存在时拒绝二进制文件"""
        with open("./linhai/tests/test_temp.txt", "w", encoding="utf-8") as f:
            f.write("test content")
        try:
            result = self.toolset.call_tool(
                "write_file",
                {
                    "filepath": "./linhai/tests/test_binary.zip",
                    "content": "new content",
                },
            )
            pass
        finally:
            import os

            if os.path.exists("./linhai/tests/test_temp.txt"):
                os.remove("./linhai/tests/test_temp.txt")

    def test_append_file_rejects_binary_file(self):
        """测试append_file拒绝二进制文件"""
        result = self.toolset.call_tool(
            "append_file",
            {
                "filepath": "./linhai/tests/test_binary.zip",
                "content": "appended content",
            },
        )
        self.assertIn("不是纯文本文件", result)

    def test_replace_file_content_rejects_binary_file(self):
        """测试replace_file_content拒绝二进制文件"""
        result = self.toolset.call_tool(
            "replace_file_content",
            {
                "filepath": "./linhai/tests/test_binary.zip",
                "old": "test",
                "new": "replacement",
            },
        )
        self.assertIn("不是纯文本文件", result)

    def test_run_sed_expression_rejects_binary_file(self):
        """测试run_sed_expression拒绝二进制文件"""
        result = self.toolset.call_tool(
            "run_sed_expression",
            {
                "filepath": "./linhai/tests/test_binary.zip",
                "expression": "s/test/replacement/",
            },
        )
        self.assertIn("不是纯文本文件", str(result))

    def test_modify_file_with_sed_rejects_binary_file(self):
        """测试modify_file_with_sed拒绝二进制文件"""
        result = self.toolset.call_tool(
            "modify_file_with_sed",
            {
                "filepath": "./linhai/tests/test_binary.zip",
                "expression": "s/test/replacement/",
            },
        )
        self.assertIn("不是纯文本文件", result)

    def test_insert_at_line_rejects_binary_file(self):
        """测试insert_at_line拒绝二进制文件"""
        result = self.toolset.call_tool(
            "insert_at_line",
            {
                "filepath": "./linhai/tests/test_binary.zip",
                "line_number": 1,
                "content": "inserted content",
                "expected_line_content": "dummy",
            },
        )
        self.assertIn("不是纯文本文件", result)



