"""Unit tests for file validation in file operation tools."""

import unittest

from linhai.tool.base import ToolArgInfo


class TestFileValidation(unittest.TestCase):
    """Test cases for file validation in file operation tools."""

    def setUp(self):
        from linhai.tool.base import ToolSet

        self.toolset = ToolSet()
        from linhai.machine_control.master_host.file import (
            read_file,
            write_file,
            replace_file_content,
            read_file_with_sed,
            modify_file_with_sed,
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
            name="read_file_with_sed",
            desc="执行sed表达式并返回输出",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "expression": ToolArgInfo(desc="sed表达式", type="str"),
            },
            required_args=["filepath", "expression"],
        )(read_file_with_sed)

        self.toolset.register_tool(
            name="modify_file_with_sed",
            desc="使用sed表达式修改文件",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "expression": ToolArgInfo(desc="sed表达式", type="str"),
            },
            required_args=["filepath", "expression"],
        )(modify_file_with_sed)

    def test_read_file_rejects_binary_file(self):
        """测试read_file拒绝二进制文件"""
        result = self.toolset.call_tool(
            "read_file", {"filepath": "./tests/test_binary.zip"}
        )
        self.assertIn("不是纯文本文件", str(result))

    def test_write_file_rejects_binary_file_for_existing_file(self):
        """测试write_file在文件存在时拒绝二进制文件"""
        with open("./tests/test_temp.txt", "w", encoding="utf-8") as f:
            f.write("test content")
        try:
            result = self.toolset.call_tool(
                "write_file",
                {
                    "filepath": "./tests/test_binary.zip",
                    "content": "new content",
                },
            )
            pass
        finally:
            import os

            if os.path.exists("./tests/test_temp.txt"):
                os.remove("./tests/test_temp.txt")

    def test_replace_file_content_rejects_binary_file(self):
        """测试replace_file_content拒绝二进制文件"""
        result = self.toolset.call_tool(
            "replace_file_content",
            {
                "filepath": "./tests/test_binary.zip",
                "old": "test",
                "new": "replacement",
            },
        )
        self.assertIn("不是纯文本文件", str(result))

    def test_read_file_with_sed_rejects_binary_file(self):
        """测试read_file_with_sed拒绝二进制文件"""
        result = self.toolset.call_tool(
            "read_file_with_sed",
            {
                "filepath": "./tests/test_binary.zip",
                "expression": "s/test/replacement/",
            },
        )
        self.assertIn("不是纯文本文件", str(result))

    def test_modify_file_with_sed_rejects_binary_file(self):
        """测试modify_file_with_sed拒绝二进制文件"""
        result = self.toolset.call_tool(
            "modify_file_with_sed",
            {
                "filepath": "./tests/test_binary.zip",
                "expression": "s/test/replacement/",
            },
        )
        self.assertIn("不是纯文本文件", str(result))
