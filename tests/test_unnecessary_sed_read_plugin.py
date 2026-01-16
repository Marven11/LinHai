"""测试UnnecessarySedReadPlugin插件。"""

import unittest
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path

from linhai.agent.plugin import UnnecessarySedReadPlugin
from linhai.llm import ToolCallMessage
from linhai.agent.base import FileContentMessage
from linhai.agent.base import RuntimeMessage


class TestUnnecessarySedReadPlugin(unittest.TestCase):
    """测试UnnecessarySedReadPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = MagicMock()
        self.group_chat.send_if_exists = AsyncMock(return_value=None)

        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])

        # 模拟machine_control
        self.mock_machine_control = MagicMock()
        self.mock_machine_control.target_machine = "master_host"

        def get_members_side_effect(member_type, _member_class=None):
            if member_type == "agent":
                return self.agent
            if member_type == "machine_control":
                return self.mock_machine_control
            raise RuntimeError(f"{member_type!r} not exists")

        self.group_chat.get_members = MagicMock(side_effect=get_members_side_effect)

        self.plugin = UnnecessarySedReadPlugin(self.group_chat)

        self.small_result = "line 1\nline 2\nline 3\n"

    def test_init(self):
        """测试初始化。"""
        self.assertEqual(self.plugin.group_chat, self.group_chat)
        self.assertEqual(self.plugin.warning_count, 0)

    def test_register(self):
        """测试注册插件。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_tool_call.assert_called_once_with(
            self.plugin._after_tool_call
        )

    @patch("linhai.agent.plugin.Path")
    def test_not_read_file_with_sed(self, mock_path):
        """测试非read_file_with_sed工具调用。"""
        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import (
            ToolCallResultMessage,
            ToolResultSuccess,
            ToolResultFailed,
            ToolResultSuccess,
            ToolResultFailed,
        )

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent,
                tool_call,
                ToolCallResultMessage(
                    tool_name="test_tool",
                    tool_index=1,
                    result=ToolResultSuccess(content="test result"),
                ),
                True,
            )
        )
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    def test_failed_tool_call(self, mock_path):
        """测试失败的工具调用。"""
        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        result = asyncio.run(
            self.plugin._after_tool_call(self.agent, tool_call, "test result", False)
        )
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    def test_no_filepath(self, mock_path):
        """测试没有文件路径的情况。"""
        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import (
            ToolCallResultMessage,
            ToolResultSuccess,
            ToolResultFailed,
            ToolResultSuccess,
            ToolResultFailed,
        )

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent,
                tool_call,
                ToolCallResultMessage(
                    tool_name="test_tool",
                    tool_index=1,
                    result=ToolResultSuccess(content=self.small_result),
                ),
                True,
            )
        )
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\n")
    def test_large_result(self, mock_open, mock_path):
        """测试结果长度大于等于10000字符的情况。"""
        mock_path.return_value.is_file.return_value = True

        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import (
            ToolCallResultMessage,
            ToolResultSuccess,
            ToolResultFailed,
            ToolResultSuccess,
            ToolResultFailed,
        )

        large_result = "x" * 10000  # 刚好10000字符
        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent,
                tool_call,
                ToolCallResultMessage(
                    tool_name="test_tool",
                    tool_index=1,
                    result=ToolResultSuccess(content=large_result),
                ),
                True,
            )
        )
        # 结果很大，但插件仍然会警告
        self.assertIsNotNone(result)
        from linhai.agent.base import RuntimeMessage

        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("警告：检测到不必要的sed读取", result.message)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\n")
    def test_file_not_exists(self, mock_open, mock_path):
        """测试文件不存在的情况。"""
        mock_path.return_value.is_file.return_value = False

        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import (
            ToolCallResultMessage,
            ToolResultSuccess,
            ToolResultFailed,
            ToolResultSuccess,
            ToolResultFailed,
        )

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent,
                tool_call,
                ToolCallResultMessage(
                    tool_name="test_tool",
                    tool_index=1,
                    result=ToolResultSuccess(content=self.small_result),
                ),
                True,
            )
        )
        # 文件不存在，但插件仍然会警告
        self.assertIsNotNone(result)
        from linhai.agent.base import RuntimeMessage

        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("警告：检测到不必要的sed读取", result.message)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", side_effect=IOError("文件读取错误"))
    def test_file_read_error(self, mock_open, mock_path):
        """测试文件读取错误的情况。"""
        mock_path.return_value.is_file.return_value = True

        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import (
            ToolCallResultMessage,
            ToolResultSuccess,
            ToolResultFailed,
            ToolResultSuccess,
            ToolResultFailed,
        )

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent,
                tool_call,
                ToolCallResultMessage(
                    tool_name="test_tool",
                    tool_index=1,
                    result=ToolResultSuccess(content=self.small_result),
                ),
                True,
            )
        )
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line\n" * 2100)
    def test_large_line_count(self, mock_open, mock_path):
        """测试文件行数大于等于1600行的情况。"""
        mock_path.return_value.is_file.return_value = True

        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import (
            ToolCallResultMessage,
            ToolResultSuccess,
            ToolResultFailed,
            ToolResultSuccess,
            ToolResultFailed,
        )

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent,
                tool_call,
                ToolCallResultMessage(
                    tool_name="test_tool",
                    tool_index=1,
                    result=ToolResultSuccess(content=self.small_result),
                ),
                True,
            )
        )
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\n")
    def test_first_call(self, mock_open, mock_path):
        """测试第一次调用。"""
        mock_path.return_value.is_file.return_value = True
        # 模拟resolve返回绝对路径
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import (
            ToolCallResultMessage,
            ToolResultSuccess,
            ToolResultFailed,
            ToolResultSuccess,
            ToolResultFailed,
        )

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent,
                tool_call,
                ToolCallResultMessage(
                    tool_name="test_tool",
                    tool_index=1,
                    result=ToolResultSuccess(content=self.small_result),
                ),
                True,
            )
        )
        # 新逻辑：第一次警告
        self.assertIsNotNone(result)
        from linhai.agent.base import RuntimeMessage

        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("警告：检测到不必要的sed读取", result.message)
        self.assertEqual(self.plugin.warning_count, 1)

    @patch("linhai.agent.plugin.Path")
    @patch(
        "builtins.open", new_callable=mock_open, read_data=b"line1\\nline2\\nline3\\n"
    )
    def test_duplicate_file_read_plugin_allows_sed_when_no_full_read(
        self, mock_open, mock_path
    ):
        """测试当没有完整读取文件时，DuplicateFileReadPlugin允许read_file_with_sed。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        # 模拟消息历史中没有FileContentMessage
        self.agent.message_processor.get_messages.return_value = []

        # 模拟read_file_with_sed工具调用
        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import (
            ToolCallResultMessage,
            ToolResultSuccess,
            ToolResultFailed,
            ToolResultSuccess,
            ToolResultFailed,
        )

        result = asyncio.run(
            plugin._after_tool_call(
                self.agent,
                tool_call,
                ToolCallResultMessage(
                    tool_name="test_tool",
                    tool_index=1,
                    result=ToolResultSuccess(content=self.small_result),
                ),
                True,
            )
        )

        # 应该允许，因为没有完整读取
        self.assertIsNone(result)
        self.group_chat.send_if_exists.assert_not_called()

    @patch("linhai.agent.plugin.Path")
    @patch(
        "builtins.open", new_callable=mock_open, read_data=b"line1\\nline2\\nline3\\n"
    )
    def test_duplicate_file_read_plugin_blocks_read_file_when_identical(
        self, mock_open, mock_path
    ):
        """测试DuplicateFileReadPlugin在重复读取相同内容时阻止read_file。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        # 模拟消息历史中包含FileContentMessage
        file_content_message = FileContentMessage(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )
        self.agent.message_processor.get_messages.return_value = [file_content_message]

        # 模拟read_file工具调用，返回相同内容
        from linhai.agent.base import FileContentMessage as FCM

        new_file_content = FCM(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, new_file_content, True)
        )

        # 应该被阻止，因为内容相同
        self.assertIsNotNone(result)
        from linhai.agent.base import RuntimeMessage

        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("错误：你已经读取过文件", result.message)
        self.group_chat.send_if_exists.assert_called_once()

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_duplicate_file_read_plugin_allows_first_read(self, mock_open, mock_path):
        """测试第一次读取文件应允许。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        # 模拟消息历史中没有FileContentMessage
        self.agent.message_processor.get_messages.return_value = []

        # 模拟read_file工具调用
        from linhai.agent.base import FileContentMessage as FCM

        new_file_content = FCM(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, new_file_content, True)
        )

        # 应该允许，因为没有历史消息
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_duplicate_file_read_plugin_allows_different_content(
        self, mock_open, mock_path
    ):
        """测试读取相同文件但内容不同应允许。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        # 模拟消息历史中包含FileContentMessage，内容为旧版本
        from linhai.agent.base import FileContentMessage as FCM

        old_file_content = FCM(
            absolute_path, "old line1\nold line2\nold line3\n", show_line_numbers=False
        )
        self.agent.message_processor.get_messages.return_value = [old_file_content]

        # 模拟read_file工具调用，返回新内容
        new_file_content = FCM(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, new_file_content, True)
        )

        # 应该允许，因为内容不同
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_duplicate_file_read_plugin_ignores_on_non_master_host(
        self, mock_open, mock_path
    ):
        """测试不在master_host上时应忽略。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        # 模拟不在master_host上
        self.mock_machine_control.target_machine = "other_host"

        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        # 模拟消息历史中包含FileContentMessage
        from linhai.agent.base import FileContentMessage as FCM

        old_file_content = FCM(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )
        self.agent.message_processor.get_messages.return_value = [old_file_content]

        # 模拟read_file工具调用，返回相同内容
        new_file_content = FCM(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, new_file_content, True)
        )

        # 应该允许，因为不在master_host上
        self.assertIsNone(result)

        # 恢复master_host
        self.mock_machine_control.target_machine = "master_host"

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_duplicate_file_read_plugin_handles_multiple_messages_latest_same(
        self, mock_open, mock_path
    ):
        """测试多个历史消息，最新相同应拦截。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        # 模拟多个历史消息，旧内容不同，最新内容相同
        from linhai.agent.base import FileContentMessage as FCM

        old_content1 = FCM(absolute_path, "old content", show_line_numbers=False)
        old_content2 = FCM(absolute_path, "different content", show_line_numbers=False)
        latest_content = FCM(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )
        self.agent.message_processor.get_messages.return_value = [
            old_content1,
            old_content2,
            latest_content,
        ]

        # 模拟read_file工具调用，返回与最新消息相同的内容
        new_file_content = FCM(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, new_file_content, True)
        )

        # 应该拦截，因为最新消息内容相同
        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("错误：你已经读取过文件", result.message)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_duplicate_file_read_plugin_handles_multiple_messages_latest_different(
        self, mock_open, mock_path
    ):
        """测试多个历史消息，最新不同应允许。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        # 模拟多个历史消息，旧内容相同，最新内容不同
        from linhai.agent.base import FileContentMessage as FCM

        old_content1 = FCM(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )
        old_content2 = FCM(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )
        latest_content = FCM(
            absolute_path, "different content", show_line_numbers=False
        )
        self.agent.message_processor.get_messages.return_value = [
            old_content1,
            old_content2,
            latest_content,
        ]

        # 模拟read_file工具调用，返回与旧消息相同但最新消息不同的内容
        new_file_content = FCM(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, new_file_content, True)
        )

        # 应该允许，因为最新消息内容不同
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_duplicate_file_read_plugin_handles_resolve_error_current_path(
        self, mock_open, mock_path
    ):
        """测试当前文件路径解析失败时返回None。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        # 模拟Path.resolve抛出OSError
        mock_path.return_value.resolve.side_effect = OSError("Permission denied")

        # 模拟read_file工具调用
        from linhai.agent.base import FileContentMessage as FCM

        new_file_content = FCM(
            "/some/path/test.py", "line1\nline2\nline3\n", show_line_numbers=False
        )

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, new_file_content, True)
        )

        # 路径解析失败，应返回None
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_duplicate_file_read_plugin_handles_resolve_error_historical_path(
        self, mock_open, mock_path
    ):
        """测试历史消息文件路径解析失败时跳过该消息。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        absolute_path = "/absolute/path/test.py"

        # 创建三个不同的Path模拟实例
        current_path_instance = MagicMock(spec=Path)
        current_path_instance.resolve.return_value = Path(absolute_path)

        bad_path_instance = MagicMock(spec=Path)
        bad_path_instance.resolve.side_effect = OSError("Bad path")

        good_path_instance = MagicMock(spec=Path)
        good_path_instance.resolve.return_value = Path(absolute_path)

        # 根据不同的路径字符串返回不同的实例
        def path_side_effect(path_str):
            if path_str == "/bad/path":
                return bad_path_instance
            elif path_str == "/absolute/path/test.py" or path_str == "./test.py":
                return good_path_instance
            else:
                return current_path_instance

        mock_path.side_effect = path_side_effect

        # 模拟两个历史消息：一个坏路径（解析失败），一个好路径（内容与当前读取相同）
        from linhai.agent.base import FileContentMessage as FCM

        bad_message = MagicMock(spec=FCM)
        bad_message.filepath = "/bad/path"
        bad_message.content = "old content"
        bad_message._resolved_path = None  # 解析失败，设置为None
        bad_message.show_line_numbers = False

        good_message = MagicMock(spec=FCM)
        good_message.filepath = "/absolute/path/test.py"
        good_message.content = "line1\nline2\nline3\n"
        good_message._resolved_path = Path(
            absolute_path
        )  # 直接设置Path对象，避免调用resolve()
        good_message.show_line_numbers = False

        self.agent.message_processor.get_messages.return_value = [
            bad_message,
            good_message,
        ]

        # 模拟read_file工具调用，返回与好消息相同的内容
        new_file_content = FCM(
            "/absolute/path/test.py", "line1\nline2\nline3\n", show_line_numbers=False
        )

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, new_file_content, True)
        )

        # 应该拦截，因为好消息的内容与当前读取相同
        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("错误：你已经读取过文件", result.message)

        # 重置模拟，确保没有意外调用
        mock_path.reset_mock()

    def test_duplicate_file_read_plugin_returns_none_on_failed_tool_call(self):
        """测试工具调用失败时返回None。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "/some/file.txt"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, "result", False)
        )

        self.assertIsNone(result)

    def test_duplicate_file_read_plugin_returns_none_on_non_read_file_tool(self):
        """测试非read_file工具时返回None。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        tool_call = ToolCallMessage(
            function_name="write_file",
            function_arguments={"filepath": "/some/file.txt", "content": "content"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, "result", True)
        )

        self.assertIsNone(result)

    def test_duplicate_file_read_plugin_returns_none_on_missing_filepath(self):
        """测试缺少filepath参数时返回None。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, "result", True)
        )

        self.assertIsNone(result)

    def test_duplicate_file_read_plugin_returns_none_on_non_file_content_message(self):
        """测试tool_result不是FileContentMessage时返回None。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "/some/file.txt"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, "just a string result", True)
        )

        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    def test_duplicate_file_read_plugin_returns_none_on_value_error_resolve(
        self, mock_path
    ):
        """测试当前文件路径解析抛出ValueError时返回None。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin

        plugin = DuplicateFileReadPlugin(self.group_chat)

        mock_path.return_value.resolve.side_effect = ValueError("Invalid path")

        from linhai.agent.base import FileContentMessage as FCM

        new_file_content = FCM("/some/file.txt", "content", show_line_numbers=False)

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.txt"},
            assert_success=True,
            with_secret=None,
        )

        result = asyncio.run(
            plugin._after_tool_call(self.agent, tool_call, new_file_content, True)
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
