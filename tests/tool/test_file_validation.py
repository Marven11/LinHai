"""Unit tests for file validation in file operation tools."""

import unittest

from linhai.tool.base import ToolArgInfo


class TestFileValidation(unittest.TestCase):
    """Test cases for file validation in file operation tools."""

    def setUp(self):
        from linhai.tool.base import ToolSet
        from linhai.sandbox import NoSandbox

        self.toolset = ToolSet()
        sandbox = NoSandbox()
        from linhai.machine_control.master_host.file import (
            read_file,
            write_file,
            replace_file_content,
            read_file_with_sed,
        )

        self.toolset.register_tool(
            name="read_file",
            desc="读取文件",
            args={"filepath": ToolArgInfo(desc="文件路径", schema={"type": "string"})},
            required_args=["filepath"],
        )(read_file)

        self.toolset.register_tool(
            name="write_file",
            desc="写入文件",
            args={
                "filepath": ToolArgInfo(desc="文件路径", schema={"type": "string"}),
                "content": ToolArgInfo(desc="要写入的内容", schema={"type": "string"}),
            },
            required_args=["filepath", "content"],
        )(write_file)

        self.toolset.register_tool(
            name="replace_file_content",
            desc="替换文件内容中的指定字符串",
            args={
                "filepath": ToolArgInfo(desc="文件路径", schema={"type": "string"}),
                "old": ToolArgInfo(desc="要替换的字符串", schema={"type": "string"}),
                "new": ToolArgInfo(desc="新的字符串", schema={"type": "string"}),
            },
            required_args=["filepath", "old", "new"],
        )(replace_file_content)

        self.toolset.register_tool(
            name="read_file_with_sed",
            desc="执行sed表达式并返回输出",
            args={
                "filepath": ToolArgInfo(desc="文件路径", schema={"type": "string"}),
                "expression": ToolArgInfo(desc="sed表达式", schema={"type": "string"}),
            },
            required_args=["filepath", "expression"],
        )(
            lambda expression, filepath: read_file_with_sed(
                expression, filepath, sandbox.wrap_argv
            )
        )

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

    def test_validate_file_for_sed_validates_text_file(self):
        """测试validate_file_for_sed正确验证文本文件"""
        from linhai.machine_control.master_host.file import validate_file_for_sed
        from pathlib import Path
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("这是一个文本文件\n第二行")
            temp_path = Path(f.name)

        try:
            result = validate_file_for_sed(temp_path)
            self.assertEqual(result, "")
        finally:
            temp_path.unlink()

    def test_validate_file_for_sed_rejects_nonexistent_file(self):
        """测试validate_file_for_sed拒绝不存在的文件"""
        from linhai.machine_control.master_host.file import validate_file_for_sed
        from pathlib import Path

        non_existent = Path("/nonexistent/file.txt")
        result = validate_file_for_sed(non_existent)
        self.assertIn("不存在", result)

    def test_validate_file_for_sed_rejects_directory(self):
        """测试validate_file_for_sed拒绝目录"""
        from linhai.machine_control.master_host.file import validate_file_for_sed
        from pathlib import Path

        dir_path = Path(".")
        result = validate_file_for_sed(dir_path)
        self.assertIn("不是文件", result)

    def test_validate_file_for_sed_rejects_binary_file(self):
        """测试validate_file_for_sed拒绝二进制文件"""
        from linhai.machine_control.master_host.file import validate_file_for_sed
        from pathlib import Path

        binary_file = Path("./tests/test_binary.zip")
        result = validate_file_for_sed(binary_file)
        self.assertIn("不是纯文本文件", result)
