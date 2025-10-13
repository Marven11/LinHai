"""测试对话历史保存功能。"""

import unittest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from linhai.agent import Agent, AgentConfig
from linhai.llm import ChatMessage, SystemMessage, ToolCallMessage
from linhai.agent_base import RuntimeMessage


class TestConversationHistory(unittest.TestCase):
    """测试对话历史保存功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.temp_dir = tempfile.mkdtemp()
        self.history_dir = Path(self.temp_dir) / ".local" / "share" / "linhai" / "history"
        
        # 创建模拟配置
        self.config: AgentConfig = {
            "system_prompt": "测试系统提示",
            "model": Mock(),
            "compress_threshold_soft": 1000,
            "compress_threshold_hard": 2000,
        }
        
        # 创建模拟队列
        self.user_input_queue = Mock()
        self.user_output_queue = Mock()
        self.tool_request_queue = Mock()
        self.tool_confirmation_queue = Mock()
        self.tool_manager = Mock()
        
        # 创建初始消息
        self.init_messages = [
            SystemMessage("测试系统消息"),
            ChatMessage("user", "测试用户消息"),
        ]
        
        # 创建Agent实例
        self.agent = Agent(
            config=self.config,
            user_input_queue=self.user_input_queue,
            user_output_queue=self.user_output_queue,
            tool_request_queue=self.tool_request_queue,
            tool_confirmation_queue=self.tool_confirmation_queue,
            tool_manager=self.tool_manager,
            init_messages=self.init_messages,
        )

    def tearDown(self):
        """清理测试环境。"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('linhai.agent.Path.home')
    def test_save_conversation_history(self, mock_home):
        """测试保存对话历史。"""
        # 模拟home目录为临时目录
        mock_home.return_value = Path(self.temp_dir)
        
        # 添加一些测试消息
        self.agent.messages.extend([
            ChatMessage("user", "你好"),
            ChatMessage("assistant", "你好！有什么可以帮助你的？"),
            RuntimeMessage("测试运行时消息"),
        ])
        
        # 调用保存方法
        import asyncio
        asyncio.run(self.agent.save_conversation_history())
        
        # 检查历史目录是否创建
        self.assertTrue(self.history_dir.exists())
        
        # 检查文件是否创建
        history_files = list(self.history_dir.glob("conversation_*.json"))
        self.assertEqual(len(history_files), 1)
        
        # 检查文件内容
        with open(history_files[0], 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        
        # 应该保存了有to_json方法的消息
        self.assertGreater(len(history_data), 0)
        
        # 检查消息类型
        for msg in history_data:
            self.assertIn("role", msg)
            self.assertIn("message", msg)

    @patch('linhai.agent.Path.home')
    def test_save_conversation_history_with_tool_calls(self, mock_home):
        """测试保存包含工具调用的对话历史。"""
        # 模拟home目录为临时目录
        mock_home.return_value = Path(self.temp_dir)
        
        # 添加包含工具调用的消息
        self.agent.messages.extend([
            ChatMessage("user", "请调用一个工具"),
            ToolCallMessage("test_tool", {"param": "value"}),
        ])
        
        # 调用保存方法
        import asyncio
        asyncio.run(self.agent.save_conversation_history())
        
        # 检查文件是否创建
        history_files = list(self.history_dir.glob("conversation_*.json"))
        self.assertEqual(len(history_files), 1)
        
        # 检查文件内容
        with open(history_files[0], 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        
        # 应该保存了工具调用消息
        tool_call_found = any(
            "tool_calls" in msg for msg in history_data
        )
        self.assertTrue(tool_call_found)

    @patch('linhai.agent.Path.home')
    def test_save_conversation_history_directory_creation(self, mock_home):
        """测试历史目录的创建。"""
        # 模拟home目录为临时目录
        mock_home.return_value = Path(self.temp_dir)
        
        # 确保目录不存在
        if self.history_dir.exists():
            import shutil
            shutil.rmtree(self.history_dir)
        
        self.assertFalse(self.history_dir.exists())
        
        # 调用保存方法
        import asyncio
        asyncio.run(self.agent.save_conversation_history())
        
        # 检查目录是否创建
        self.assertTrue(self.history_dir.exists())

    @patch('linhai.agent.Path.home')
    @patch('linhai.agent.logger')
    def test_save_conversation_history_error_handling(self, mock_logger, mock_home):
        """测试保存对话历史的错误处理。"""
        # 模拟home目录为临时目录
        mock_home.return_value = Path(self.temp_dir)
        
        # 模拟文件写入错误
        with patch('builtins.open', side_effect=IOError("模拟IO错误")):
            # 调用保存方法
            import asyncio
            asyncio.run(self.agent.save_conversation_history())
            
            # 检查是否记录了错误
            mock_logger.error.assert_called()


if __name__ == "__main__":
    unittest.main()