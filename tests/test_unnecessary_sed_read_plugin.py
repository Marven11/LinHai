"""测试UnnecessarySedReadPlugin插件。"""

import unittest
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path

from linhai.agent.plugin import UnnecessarySedReadPlugin
from linhai.llm import ToolCallMessage
from linhai.agent.base import FileContentMessage


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
        self.assertEqual(self.plugin.unnecessary_history, {})

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
        from linhai.tool.base import ToolResultMessage

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage("test result"), True
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
        from linhai.tool.base import ToolResultMessage

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(self.small_result), True
            )
        )
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    def test_not_string_result(self, mock_path):
        """测试非字符串结果。"""
        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, FileContentMessage("./test.py", "content"), True
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
        from linhai.tool.base import ToolResultMessage

        large_result = "x" * 10000  # 刚好10000字符
        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(large_result), True
            )
        )
        self.assertIsNone(result)

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
        from linhai.tool.base import ToolResultMessage

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(self.small_result), True
            )
        )
        self.assertIsNone(result)

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
        from linhai.tool.base import ToolResultMessage

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(self.small_result), True
            )
        )
        self.assertIsNone(result)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line\n" * 1600)
    def test_large_line_count(self, mock_open, mock_path):
        """测试文件行数大于等于1600行的情况。"""
        mock_path.return_value.is_file.return_value = True

        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import ToolResultMessage

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(self.small_result), True
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
        from linhai.tool.base import ToolResultMessage

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(self.small_result), True
            )
        )
        self.assertIsNone(result)
        # 现在插件使用绝对路径作为键
        self.assertIn(absolute_path, self.plugin.unnecessary_history)
        timestamp = self.plugin.unnecessary_history[absolute_path]
        self.assertAlmostEqual(timestamp, time.time(), delta=2)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\n")
    def test_second_call_within_minute(self, mock_open, mock_path):
        """测试一分钟内的第二次调用。"""
        mock_path.return_value.is_file.return_value = True
        # 模拟resolve返回绝对路径
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        import time

        # 现在插件使用绝对路径作为键
        self.plugin.unnecessary_history[absolute_path] = (
            time.time() - 30
        )  # 30秒前，在1分钟内

        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import ToolResultMessage

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(self.small_result), True
            )
        )

        self.assertIsNotNone(result)
        from linhai.agent.base import RuntimeMessage

        self.assertIsInstance(result, RuntimeMessage)
        assert result is not None
        self.assertIn("滥用read_file_with_sed多次小块读取代码文件", result.message)

        self.group_chat.send_if_exists.assert_called_once()

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\n")
    def test_second_call_after_minute(self, mock_open, mock_path):
        """测试一分钟后的第二次调用。"""
        mock_path.return_value.is_file.return_value = True
        # 模拟resolve返回绝对路径
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)
        import time

        current_time = time.time()

        # 现在插件使用绝对路径作为键
        self.plugin.unnecessary_history[absolute_path] = (
            current_time - 70
        )  # 70秒前，超过1分钟

        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import ToolResultMessage

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(self.small_result), True
            )
        )

        self.assertIsNone(result)
        self.assertIn(absolute_path, self.plugin.unnecessary_history)
        timestamp = self.plugin.unnecessary_history[absolute_path]
        self.assertAlmostEqual(timestamp, time.time(), delta=2)

    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\n")
    def test_history_cleanup(self, mock_open, mock_path):
        """测试历史记录清理。"""
        mock_path.return_value.is_file.return_value = True
        # 模拟resolve返回绝对路径
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)
        import time

        current_time = time.time()

        # 现在插件使用绝对路径作为键，所以历史记录中的键也应该是绝对路径
        old_absolute_path = "/absolute/path/old.py"
        new_absolute_path = "/absolute/path/new.py"
        self.plugin.unnecessary_history[old_absolute_path] = (
            current_time - 300
        )  # 300秒前，应该被清理
        self.plugin.unnecessary_history[new_absolute_path] = (
            current_time - 50
        )  # 50秒前，应该保留

        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import ToolResultMessage

        result = asyncio.run(
            self.plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(self.small_result), True
            )
        )

        self.assertIsNone(result)
        self.assertIn(
            old_absolute_path, self.plugin.unnecessary_history
        )  # 不需要清理旧记录，应该还在
        self.assertIn(new_absolute_path, self.plugin.unnecessary_history)  # 应该保留
        self.assertIn(absolute_path, self.plugin.unnecessary_history)  # 新记录已添加
        new_timestamp = self.plugin.unnecessary_history[new_absolute_path]
        old_timestamp = self.plugin.unnecessary_history[old_absolute_path]
        # 检查时间戳是否保持不变（因为新记录没有更新）
        self.assertAlmostEqual(new_timestamp, current_time - 50, delta=2)
        self.assertAlmostEqual(
            old_timestamp, current_time - 300, delta=2
        )  # old.py的时间戳也应该保持不变


    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\\nline2\\nline3\\n")
    def test_duplicate_file_read_plugin_blocks_sed_after_full_read(self, mock_open, mock_path):
        """测试DuplicateFileReadPlugin在完整读取文件后阻止read_file_with_sed。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin
        plugin = DuplicateFileReadPlugin(self.group_chat)
        
        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)
        
        # 模拟消息历史中包含FileContentMessage（完整读取的结果）
        file_content_message = FileContentMessage(absolute_path, "line1\nline2\nline3\n")
        self.agent.message_processor.get_messages.return_value = [file_content_message]
        
        # 模拟read_file_with_sed工具调用
        tool_call = ToolCallMessage(
            function_name="read_file_with_sed",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        from linhai.tool.base import ToolResultMessage
        
        result = asyncio.run(
            plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(self.small_result), True
            )
        )
        
        # 应该被阻止，因为文件已完整读取
        self.assertIsNotNone(result)
        from linhai.agent.base import RuntimeMessage
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("错误：此文件已经读取", result.message)
        self.group_chat.send_if_exists.assert_called_once()
    
    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\\nline2\\nline3\\n")
    def test_duplicate_file_read_plugin_allows_sed_when_no_full_read(self, mock_open, mock_path):
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
        from linhai.tool.base import ToolResultMessage
        
        result = asyncio.run(
            plugin._after_tool_call(
                self.agent, tool_call, ToolResultMessage(self.small_result), True
            )
        )
        
        # 应该允许，因为没有完整读取
        self.assertIsNone(result)
        self.group_chat.send_if_exists.assert_not_called()
    
    @patch("linhai.agent.plugin.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\\nline2\\nline3\\n")
    def test_duplicate_file_read_plugin_blocks_read_file_when_identical(self, mock_open, mock_path):
        """测试DuplicateFileReadPlugin在重复读取相同内容时阻止read_file。"""
        from linhai.agent.plugin import DuplicateFileReadPlugin
        plugin = DuplicateFileReadPlugin(self.group_chat)
        
        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)
        
        # 模拟消息历史中包含FileContentMessage
        file_content_message = FileContentMessage(absolute_path, "line1\nline2\nline3\n")
        self.agent.message_processor.get_messages.return_value = [file_content_message]
        
        # 模拟read_file工具调用，返回相同内容
        from linhai.agent.base import FileContentMessage as FCM
        new_file_content = FCM(absolute_path, "line1\nline2\nline3\n")
        
        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )
        
        result = asyncio.run(
            plugin._after_tool_call(
                self.agent, tool_call, new_file_content, True
            )
        )
        
        # 应该被阻止，因为内容相同
        self.assertIsNotNone(result)
        from linhai.agent.base import RuntimeMessage
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("错误：你已经读取过文件", result.message)
        self.group_chat.send_if_exists.assert_called_once()


if __name__ == "__main__":
    unittest.main()
