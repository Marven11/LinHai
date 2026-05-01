"""测试UnnecessaryRunCommandPlugin插件。"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from linhai.plugin import UnnecessaryRunCommandPlugin
from linhai.agent.messages import RuntimeMessage
from linhai.tool.base import ToolCallResultMessage
from linhai.base import ToolCallMessage


class TestUnnecessaryRunCommandPlugin(unittest.IsolatedAsyncioTestCase):
    """测试UnnecessaryRunCommandPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = MagicMock()
        self.registry = MagicMock()

        self.mock_machine_control = MagicMock()
        self.mock_machine_control.target_machine = "master_host"

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            if member_type == "agent":
                return self.agent
            if member_type == "machine_control":
                return self.mock_machine_control
            raise RuntimeError(f"{member_type!r} not exists")

        self.registry.get_member_typechecked = MagicMock(
            side_effect=get_member_typechecked_side_effect
        )
        self.registry.send_if_exists = AsyncMock()
        self.plugin = UnnecessaryRunCommandPlugin(self.registry)

    async def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.after_toolcall.register.assert_called_once_with(
            self.plugin.after_toolcall
        )

    async def test_after_toolcall_not_process_create(self):
        """测试非process_create工具调用。"""
        result = await self.plugin.after_toolcall(
            tool_name="read_file",
            tool_index=0,
            status="success",
            message="result",
            toolcall_arguments={"filepath": "test.txt"},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_process_create_failed(self):
        """测试process_create调用失败。"""
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="failed",
            message="result",
            toolcall_arguments={"command": ["ls"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_no_command(self):
        """测试process_create没有命令参数。"""
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message="result",
            toolcall_arguments={},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_with_pipeline_allowed(self):
        """测试包含管道符号的命令允许。"""
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message="result",
            toolcall_arguments={"command": ["cat", "file.txt", "|", "grep", "pattern"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_with_redirect_allowed(self):
        """测试有重定向的cat命令允许。"""
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message="result",
            toolcall_arguments={"command": ["cat", "file.txt", ">", "output.txt"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_read_file_tracking(self):
        """测试已读取文件跟踪。"""
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={
                        "command": ["grep", "pattern", "/path/to/read.txt"]
                    },
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件", result.message
        )
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_toolcall_read_file_relative_path(self):
        """测试相对路径的已读取文件跟踪。"""
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "test.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={"command": ["cat", "test.txt"]},
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件", result.message
        )
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_toolcall_tail_command(self):
        """测试tail命令拦截。"""
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={
                        "command": ["tail", "-10", "/path/to/read.txt"]
                    },
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件", result.message
        )
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_toolcall_head_command(self):
        """测试head命令拦截。"""
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={
                        "command": ["head", "-10", "/path/to/read.txt"]
                    },
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件", result.message
        )
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_toolcall_awk_command(self):
        """测试awk命令拦截。"""
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={
                        "command": ["awk", "{print $1}", "/path/to/read.txt"]
                    },
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件", result.message
        )
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_toolcall_rg_command(self):
        """测试rg命令拦截。"""
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={
                        "command": ["rg", "pattern", "/path/to/read.txt"]
                    },
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件", result.message
        )
        self.assertEqual(self.plugin.warning_count, 1)


if __name__ == "__main__":
    unittest.main()
