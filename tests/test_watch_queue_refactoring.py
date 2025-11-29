"""测试watch_output_queue重构后的功能"""

import unittest
from unittest.mock import MagicMock
from linhai.cli.app import CLIApp
from linhai.group_chat import GroupChat
from linhai.config import CLIConfig


class TestWatchQueueRefactoring(unittest.TestCase):
    """测试重构后的watch_queue函数"""
    
    def setUp(self):
        """设置测试环境"""
        self.group_chat = GroupChat()
        self.app = CLIApp(self.group_chat, cli_config=CLIConfig())
        
        # 模拟UI组件
        self.app.query_one = MagicMock()
        
    def test_method_exists(self):
        """测试四个新方法是否存在"""
        self.assertTrue(hasattr(self.app, 'watch_agent_answer_queue'))
        self.assertTrue(hasattr(self.app, 'watch_ui_log_queue'))
        self.assertTrue(hasattr(self.app, 'watch_exit_signal_queue'))
        self.assertTrue(hasattr(self.app, 'watch_subagent_message_queue'))
        self.assertTrue(hasattr(self.app, 'watch_output_queue'))
        
    def test_method_signatures(self):
        """测试方法签名"""
        import inspect
        
        # 检查watch_output_queue是async方法
        self.assertTrue(inspect.iscoroutinefunction(self.app.watch_output_queue))
        
        # 检查其他方法也都是async方法
        self.assertTrue(inspect.iscoroutinefunction(self.app.watch_agent_answer_queue))
        self.assertTrue(inspect.iscoroutinefunction(self.app.watch_ui_log_queue))
        self.assertTrue(inspect.iscoroutinefunction(self.app.watch_exit_signal_queue))
        self.assertTrue(inspect.iscoroutinefunction(self.app.watch_subagent_message_queue))
        
    def test_group_chat_registration(self):
        """测试GroupChat队列注册"""
        # 检查四个队列是否已注册
        self.assertIn("agent_answer", self.group_chat.queues)
        self.assertIn("ui_log", self.group_chat.queues)
        self.assertIn("exit_signal", self.group_chat.queues)
        self.assertIn("subagent_message", self.group_chat.queues)
        

if __name__ == "__main__":
    unittest.main()
