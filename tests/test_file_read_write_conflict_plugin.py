import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import tempfile

from linhai.plugin import FileReadWriteConflictPlugin
from linhai.group_chat import GroupChat
from linhai.llm import ToolCallMessage
from linhai.tool.base import ToolResultSuccess


class TestFileReadWriteConflictPlugin(unittest.IsolatedAsyncioTestCase):
    """测试文件读写冲突插件"""

    def setUp(self):
        """设置测试环境"""
        self.group_chat = MagicMock(spec=GroupChat)
        self.plugin = FileReadWriteConflictPlugin(self.group_chat)
        # 创建临时文件用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.write_text("测试内容\n第二行\n第三行", encoding="utf-8")
        # 模拟machine_control
        self.mock_machine_control = MagicMock()
        self.mock_machine_control.target_machine = "master_host"

    def tearDown(self):
        """清理测试环境"""
        import shutil

        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    async def test_read_then_write_same_file_should_warn(self):
        """测试读取文件后写入同一文件应触发警告"""
        # 模拟group_chat.get_member_typechecked返回machine_control
        self.group_chat.get_member_typechecked.return_value = self.mock_machine_control

        # 清空读取文件列表（模拟新消息开始）
        await self.plugin.before_message_generation()
        # 模拟读取文件工具调用
        read_tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": str(self.test_file)},
            assert_success=True,
            with_secret=[],
        )
        read_result = ToolResultSuccess(
            content="文件内容",
            original_tool_call=read_tool_call,
            with_secret=[],
        )
        # 调用on_tool_result处理读取
        result = await self.plugin.after_toolcall(
            "read_file",
            0,
            "success",
            read_result.content,
            read_tool_call.function_arguments,
            read_tool_call.with_secret,
            False,
        )
        self.assertIsNone(result)
        # 读取文件不应该返回警告

        # 模拟写入同一文件工具调用
        write_tool_call = ToolCallMessage(
            function_name="write_file",
            function_arguments={
                "filepath": str(self.test_file),
                "content": "新内容",
                "override": True,
            },
            assert_success=True,
            with_secret=[],
        )
        write_result = ToolResultSuccess(
            content="写入成功",
            original_tool_call=write_tool_call,
            with_secret=[],
        )
        # 调用on_tool_result处理写入
        result = await self.plugin.after_toolcall(
            "write_file",
            0,
            "success",
            write_result.content,
            write_tool_call.function_arguments,
            write_tool_call.with_secret,
            False,
        )
        # 应该返回警告消息
        self.assertIsNotNone(result)
        self.assertIn("警告", result.message)
        self.assertIn(str(self.test_file), result.message)
        # 应该调用了send_if_exists发送UI日志
        self.group_chat.send_if_exists.assert_called_once()

    async def test_read_then_write_different_file_should_not_warn(self):
        """测试读取文件后写入不同文件不应触发警告"""
        # 模拟group_chat.get_member_typechecked返回machine_control
        self.group_chat.get_member_typechecked.return_value = self.mock_machine_control

        # 清空读取文件列表
        await self.plugin.before_message_generation()
        # 创建第二个文件
        other_file = Path(self.temp_dir) / "other.txt"
        other_file.write_text("其他文件内容", encoding="utf-8")
        # 模拟读取第一个文件
        result = await self.plugin.after_toolcall(
            "read_file",
            0,
            "success",
            "文件内容",
            {"filepath": str(self.test_file)},
            [],
            False,
        )
        self.assertIsNone(result)
        # 模拟写入第二个文件
        result = await self.plugin.after_toolcall(
            "write_file",
            0,
            "success",
            "写入成功",
            {"filepath": str(other_file), "content": "新内容", "override": True},
            [],
            False,
        )
        # 不应该返回警告消息
        self.assertIsNone(result)

    async def test_not_master_host_should_not_check(self):
        """测试非master_host机器不应检查冲突"""
        # 模拟machine_control返回非master_host
        self.mock_machine_control.target_machine = "other_host"
        self.group_chat.get_member_typechecked.return_value = self.mock_machine_control

        # 清空读取文件列表
        await self.plugin.before_message_generation()
        # 模拟读取文件
        read_tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": str(self.test_file)},
            assert_success=True,
            with_secret=[],
        )
        read_result = ToolResultSuccess(
            content="文件内容",
            original_tool_call=read_tool_call,
            with_secret=[],
        )
        result = await self.plugin.after_toolcall(
            "read_file",
            0,
            "success",
            (
                read_result.content
                if hasattr(read_result, "content")
                else str(read_result)
            ),
            (
                read_tool_call.function_arguments
                if hasattr(read_tool_call, "function_arguments")
                else {}
            ),
            (
                read_tool_call.with_secret
                if hasattr(read_tool_call, "with_secret")
                else []
            ),
            False,
        )
        self.assertIsNone(result)
        # 模拟写入同一文件
        write_tool_call = ToolCallMessage(
            function_name="write_file",
            function_arguments={
                "filepath": str(self.test_file),
                "content": "新内容",
                "override": True,
            },
            assert_success=True,
            with_secret=[],
        )
        write_result = ToolResultSuccess(
            content="写入成功",
            original_tool_call=write_tool_call,
            with_secret=[],
        )
        result = await self.plugin.after_toolcall(
            "write_file",
            0,
            "success",
            (
                read_result.content
                if hasattr(read_result, "content")
                else str(read_result)
            ),
            (
                read_tool_call.function_arguments
                if hasattr(read_tool_call, "function_arguments")
                else {}
            ),
            (
                read_tool_call.with_secret
                if hasattr(read_tool_call, "with_secret")
                else []
            ),
            False,
        )
        # 不应该返回警告消息（因为不在master_host）
        self.assertIsNone(result)

    async def test_various_read_write_tools(self):
        """测试各种读取和写入工具"""
        self.group_chat.get_member_typechecked.return_value = self.mock_machine_control
        await self.plugin.before_message_generation()
        # 测试read_file_with_sed
        read_tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={
                "filepath": str(self.test_file),
                "expression": "1p",
            },
            assert_success=True,
            with_secret=[],
        )
        read_result = ToolResultSuccess(
            content="第一行",
            original_tool_call=read_tool_call,
            with_secret=[],
        )
        result = await self.plugin.after_toolcall(
            "read_file",
            0,
            "success",
            (
                read_result.content
                if hasattr(read_result, "content")
                else str(read_result)
            ),
            (
                read_tool_call.function_arguments
                if hasattr(read_tool_call, "function_arguments")
                else {}
            ),
            (
                read_tool_call.with_secret
                if hasattr(read_tool_call, "with_secret")
                else []
            ),
            False,
        )
        self.assertIsNone(result)
        # 测试replace_file_content
        write_tool_call = ToolCallMessage(
            function_name="replace_file_content",
            function_arguments={
                "filepath": str(self.test_file),
                "old": "测试内容",
                "new": "新内容",
            },
            assert_success=True,
            with_secret=[],
        )
        write_result = ToolResultSuccess(
            content="替换成功",
            original_tool_call=write_tool_call,
            with_secret=[],
        )
        result = await self.plugin.after_toolcall(
            "write_file",
            0,
            "success",
            (
                read_result.content
                if hasattr(read_result, "content")
                else str(read_result)
            ),
            (
                read_tool_call.function_arguments
                if hasattr(read_tool_call, "function_arguments")
                else {}
            ),
            (
                read_tool_call.with_secret
                if hasattr(read_tool_call, "with_secret")
                else []
            ),
            False,
        )
        # 应该返回警告消息
        self.assertIsNotNone(result)

    async def test_failed_tool_call_should_be_ignored(self):
        """测试失败的工具调用应被忽略"""
        self.group_chat.get_member_typechecked.return_value = self.mock_machine_control
        await self.plugin.before_message_generation()
        # 模拟失败的读取文件工具调用
        read_tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": str(self.test_file)},
            assert_success=True,
            with_secret=[],
        )
        # 调用on_tool_result，status="failed"
        result = await self.plugin.after_toolcall(
            "read_file", 0, "failed", None, {"filepath": str(self.test_file)}, [], False
        )
        self.assertIsNone(result)
        # 失败的工具调用应该被忽略
        # 验证文件没有被添加到读取列表
        self.assertEqual(len(self.plugin.read_files), 0)

    def test_before_message_generation_clears_list(self):
        """测试before_message_generation清空读取文件列表"""
        import asyncio

        # 先添加一些文件到列表
        self.plugin.read_files = {"/path/to/file1.txt", "/path/to/file2.txt"}
        self.assertEqual(len(self.plugin.read_files), 2)
        # 调用before_message_generation
        asyncio.run(self.plugin.before_message_generation())
        # 列表应该被清空
        self.assertEqual(len(self.plugin.read_files), 0)


if __name__ == "__main__":
    unittest.main()
