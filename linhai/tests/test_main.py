"""测试main.py命令行参数"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import io
from linhai.main import main


class TestMainCommandLine(unittest.TestCase):
    """测试main.py的命令行参数"""

    @patch("linhai.main.create_agent")
    @patch("linhai.main.CLIApp")
    def test_agent_command_with_message_option(self, mock_cli_app, mock_create_agent):
        """测试使用-m选项时消息被正确传递"""
        # 模拟create_agent返回的值
        mock_agent = MagicMock()
        mock_input_queue = MagicMock()
        mock_output_queue = MagicMock()
        mock_tool_request_queue = MagicMock()
        mock_tool_confirmation_queue = MagicMock()
        mock_tool_manager = MagicMock()

        mock_create_agent.return_value = (
            mock_agent,
            mock_input_queue,
            mock_output_queue,
            mock_tool_request_queue,
            mock_tool_confirmation_queue,
            mock_tool_manager,
        )

        # 模拟CLIApp，让run()方法立即返回
        mock_app = MagicMock()
        mock_app.run = MagicMock(return_value=None)
        mock_cli_app.return_value = mock_app

        # 测试命令行参数（新结构：直接使用-m，无agent命令）
        test_args = ["linhai", "-m", "测试消息"]

        with patch.object(sys, "argv", test_args):
            # main()现在直接运行agent，不会调用sys.exit
            main()

        # 验证create_agent被调用时init_messages为None（新行为）
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        self.assertIsNotNone(call_args)

        # 检查init_messages参数为None
        init_messages = call_args.kwargs.get("init_messages")
        self.assertIsNone(init_messages)

        # 验证CLIApp被调用时init_message为测试消息（新行为）
        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertEqual(cli_call_args.kwargs.get("init_message"), "测试消息")

        # 验证CLIApp.run()被调用
        mock_app.run.assert_called_once()

    @patch("linhai.main.create_agent")
    @patch("linhai.main.CLIApp")
    def test_agent_command_without_message_option(
        self, mock_cli_app, mock_create_agent
    ):
        """测试不使用-m选项时init_message为None"""
        # 模拟create_agent返回的值
        mock_agent = MagicMock()
        mock_input_queue = MagicMock()
        mock_output_queue = MagicMock()
        mock_tool_request_queue = MagicMock()
        mock_tool_confirmation_queue = MagicMock()
        mock_tool_manager = MagicMock()

        mock_create_agent.return_value = (
            mock_agent,
            mock_input_queue,
            mock_output_queue,
            mock_tool_request_queue,
            mock_tool_confirmation_queue,
            mock_tool_manager,
        )

        # 模拟CLIApp，让run()方法立即返回
        mock_app = MagicMock()
        mock_app.run = MagicMock(return_value=None)
        mock_cli_app.return_value = mock_app

        # 测试命令行参数（不使用-m选项）
        test_args = ["linhai"]

        with patch.object(sys, "argv", test_args):
            # main()现在直接运行agent，不会调用sys.exit
            main()

        # 验证create_agent被调用时init_messages为None
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        self.assertIsNotNone(call_args)

        # 检查init_messages参数为None
        init_messages = call_args.kwargs.get("init_messages")
        self.assertIsNone(init_messages)

        # 验证CLIApp被调用时init_message为None
        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertIsNone(cli_call_args.kwargs.get("init_message"))

        # 验证CLIApp.run()被调用
        mock_app.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
