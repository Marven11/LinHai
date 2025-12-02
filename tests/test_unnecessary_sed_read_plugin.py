"""测试UnnecessarySedReadPlugin插件。"""

import unittest
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from linhai.agent.plugin import UnnecessarySedReadPlugin
from linhai.llm import ToolCallMessage
from linhai.agent.base import FileContentMessage


class TestUnnecessarySedReadPlugin(unittest.TestCase):
    """测试UnnecessarySedReadPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = MagicMock()
        self.group_chat.send_if_exists = AsyncMock(return_value=None)
        self.plugin = UnnecessarySedReadPlugin(self.group_chat)
        self.agent = MagicMock()
        
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        
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
    
    @patch('linhai.agent.plugin.Path')
    def test_not_run_sed_expression(self, mock_path):
        """测试非run_sed_expression工具调用。"""
        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        from linhai.tool.base import ToolResultMessage
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, ToolResultMessage("test result"), True
        ))
        self.assertIsNone(result)
    
    @patch('linhai.agent.plugin.Path')
    def test_failed_tool_call(self, mock_path):
        """测试失败的工具调用。"""
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, "test result", False
        ))
        self.assertIsNone(result)
    
    @patch('linhai.agent.plugin.Path')
    def test_no_filepath(self, mock_path):
        """测试没有文件路径的情况。"""
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={},
            assert_success=True
        )
        from linhai.tool.base import ToolResultMessage
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, ToolResultMessage(self.small_result), True
        ))
        self.assertIsNone(result)
    
    @patch('linhai.agent.plugin.Path')
    def test_not_string_result(self, mock_path):
        """测试非字符串结果。"""
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, FileContentMessage("./test.py", "content"), True
        ))
        self.assertIsNone(result)
    
    @patch('linhai.agent.plugin.Path')
    @patch('builtins.open', new_callable=mock_open, read_data=b'line1\nline2\n')
    def test_large_result(self, mock_open, mock_path):
        """测试结果长度大于等于10000字符的情况。"""
        mock_path.return_value.is_file.return_value = True
        
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        from linhai.tool.base import ToolResultMessage
        large_result = "x" * 10000  # 刚好10000字符
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, ToolResultMessage(large_result), True
        ))
        self.assertIsNone(result)
    
    @patch('linhai.agent.plugin.Path')
    @patch('builtins.open', new_callable=mock_open, read_data=b'line1\nline2\n')
    def test_file_not_exists(self, mock_open, mock_path):
        """测试文件不存在的情况。"""
        mock_path.return_value.is_file.return_value = False
        
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        from linhai.tool.base import ToolResultMessage
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, ToolResultMessage(self.small_result), True
        ))
        self.assertIsNone(result)
    
    @patch('linhai.agent.plugin.Path')
    @patch('builtins.open', side_effect=IOError('文件读取错误'))
    def test_file_read_error(self, mock_open, mock_path):
        """测试文件读取错误的情况。"""
        mock_path.return_value.is_file.return_value = True
        
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        from linhai.tool.base import ToolResultMessage
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, ToolResultMessage(self.small_result), True
        ))
        self.assertIsNone(result)
    
    @patch('linhai.agent.plugin.Path')
    @patch('builtins.open', new_callable=mock_open, read_data=b'line\n' * 1600)
    def test_large_line_count(self, mock_open, mock_path):
        """测试文件行数大于等于1600行的情况。"""
        mock_path.return_value.is_file.return_value = True
        
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        from linhai.tool.base import ToolResultMessage
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, ToolResultMessage(self.small_result), True
        ))
        self.assertIsNone(result)
    
    @patch('linhai.agent.plugin.Path')
    @patch('builtins.open', new_callable=mock_open, read_data=b'line1\nline2\n')
    def test_first_call(self, mock_open, mock_path):
        """测试第一次调用。"""
        mock_path.return_value.is_file.return_value = True
        
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        from linhai.tool.base import ToolResultMessage
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, ToolResultMessage(self.small_result), True
        ))
        self.assertIsNone(result)
        self.assertIn("./test.py", self.plugin.unnecessary_history)
        timestamp = self.plugin.unnecessary_history["./test.py"]
        self.assertAlmostEqual(timestamp, time.time(), delta=2)
    
    @patch('linhai.agent.plugin.Path')
    @patch('builtins.open', new_callable=mock_open, read_data=b'line1\nline2\n')
    def test_second_call_within_minute(self, mock_open, mock_path):
        """测试一分钟内的第二次调用。"""
        mock_path.return_value.is_file.return_value = True
        
        import time
        self.plugin.unnecessary_history["./test.py"] = time.time() - 30  # 30秒前，在1分钟内
        
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        from linhai.tool.base import ToolResultMessage
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, ToolResultMessage(self.small_result), True
        ))
        
        self.assertIsNotNone(result)
        from linhai.agent.base import RuntimeMessage
        self.assertIsInstance(result, RuntimeMessage)
        assert result is not None
        self.assertIn("错误：一分钟内多次小块读取代码文件", result.message)
        
        self.group_chat.send_if_exists.assert_called_once()
    
    @patch('linhai.agent.plugin.Path')
    @patch('builtins.open', new_callable=mock_open, read_data=b'line1\nline2\n')
    def test_second_call_after_minute(self, mock_open, mock_path):
        """测试一分钟后的第二次调用。"""
        mock_path.return_value.is_file.return_value = True
        import time
        current_time = time.time()
        
        self.plugin.unnecessary_history["./test.py"] = current_time - 70  # 70秒前，超过1分钟
        
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        from linhai.tool.base import ToolResultMessage
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, ToolResultMessage(self.small_result), True
        ))
        
        self.assertIsNone(result)
        self.assertIn("./test.py", self.plugin.unnecessary_history)
        timestamp = self.plugin.unnecessary_history["./test.py"]
        self.assertAlmostEqual(timestamp, time.time(), delta=2)
    
    @patch('linhai.agent.plugin.Path')
    @patch('builtins.open', new_callable=mock_open, read_data=b'line1\nline2\n')
    def test_history_cleanup(self, mock_open, mock_path):
        """测试历史记录清理。"""
        mock_path.return_value.is_file.return_value = True
        import time
        current_time = time.time()
        
        self.plugin.unnecessary_history["old.py"] = current_time - 300  # 300秒前，应该被清理
        self.plugin.unnecessary_history["new.py"] = current_time - 50  # 50秒前，应该保留
        
        tool_call = ToolCallMessage(
            function_name="run_sed_expression",
            function_arguments={"filepath": "./test.py"},
            assert_success=True
        )
        from linhai.tool.base import ToolResultMessage
        result = asyncio.run(self.plugin._after_tool_call(
            self.agent, tool_call, ToolResultMessage(self.small_result), True
        ))
        
        self.assertIsNone(result)
        self.assertIn("old.py", self.plugin.unnecessary_history)  # 不需要清理旧记录，应该还在
        self.assertIn("new.py", self.plugin.unnecessary_history)     # 应该保留
        self.assertIn("./test.py", self.plugin.unnecessary_history)   # 新记录已添加
        new_timestamp = self.plugin.unnecessary_history["new.py"]
        old_timestamp = self.plugin.unnecessary_history["old.py"]
        # 检查时间戳是否保持不变（因为新记录没有更新）
        self.assertAlmostEqual(new_timestamp, current_time - 50, delta=2)
        self.assertAlmostEqual(old_timestamp, current_time - 300, delta=2)  # old.py的时间戳也应该保持不变


if __name__ == "__main__":
    unittest.main()