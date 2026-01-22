"""测试队列监听方法的功能"""

import unittest
from unittest.mock import MagicMock
from linhai.cli.app import CLIApp
from linhai.group_chat import GroupChat
from linhai.config import CLIConfig


class TestQueueListeningMethods(unittest.TestCase):
    """测试队列监听方法"""

    def setUp(self):
        """设置测试环境"""
        self.group_chat = GroupChat()
        # 不注册队列，让CLIApp在初始化时注册
        from linhai.agent import Agent

        mock_agent = MagicMock(spec=Agent)
        self.group_chat.register_member("agent", mock_agent)

        import argparse

        mock_cli_args = argparse.Namespace()
        mock_cli_args.message = None
        mock_cli_args.file = None
        self.group_chat.register_member("cli_args", mock_cli_args)

        self.app = CLIApp(self.group_chat, cli_config=CLIConfig())

        self.app.query_one = MagicMock()

    def test_method_exists(self):
        """测试队列监听方法是否存在"""
        self.assertTrue(hasattr(self.app, "watch_parsed_agent_answer_queue"))
        self.assertTrue(hasattr(self.app, "watch_ui_log_queue"))
        self.assertTrue(hasattr(self.app, "watch_exit_signal_queue"))
        self.assertTrue(hasattr(self.app, "watch_subagent_message_queue"))
        self.assertTrue(hasattr(self.app, "watch_token_usage_queue"))

    def test_method_signatures(self):
        """测试方法签名"""
        import inspect

        self.assertTrue(
            inspect.iscoroutinefunction(self.app.watch_parsed_agent_answer_queue)
        )
        self.assertTrue(inspect.iscoroutinefunction(self.app.watch_ui_log_queue))
        self.assertTrue(inspect.iscoroutinefunction(self.app.watch_exit_signal_queue))
        self.assertTrue(
            inspect.iscoroutinefunction(self.app.watch_subagent_message_queue)
        )
        self.assertTrue(inspect.iscoroutinefunction(self.app.watch_token_usage_queue))

    def test_group_chat_registration(self):
        """测试GroupChat队列注册"""
        self.assertIn("parsed_agent_answer", self.group_chat.queues)
        self.assertIn("ui_log", self.group_chat.queues)
        self.assertIn("exit_signal", self.group_chat.queues)
        self.assertIn("subagent_message", self.group_chat.queues)
        self.assertIn("token_usage", self.group_chat.queues)


if __name__ == "__main__":
    unittest.main()
