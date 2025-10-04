"""测试main.py命令行参数"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import io
from linhai.main import main


class TestMainCommandLine(unittest.TestCase):
    """测试main.py的命令行参数"""

    @patch('linhai.main.create_agent')
    @patch('linhai.main.CLIApp')
    def test_agent_command_with_message_option(self, mock_cli_app, mock_create_agent):
        """测试使用-m选项时消息被正确传递"""
        # 模拟create_agent返回的值
        mock_agent = MagicMock()
        mock_input_queue = MagicMock()
        mock_output_queue = MagicMock()
        mock_tool_request_queue = MagicMock()
        mock_tool_confirmation_queue = MagicMock()
        mock_tool_manager = MagicMock()
        
        # 模拟agent的messages属性来检查重复消息
        mock_agent.messages = []
        
        # 模拟create_agent行为：将init_messages添加到agent.messages
        def mock_create_agent_func(config_path, init_messages=None):
            if init_messages:
                mock_agent.messages.extend(init_messages)
            return (
                mock_agent,
                mock_input_queue,
                mock_output_queue,
                mock_tool_request_queue,
                mock_tool_confirmation_queue,
                mock_tool_manager
            )
        
        mock_create_agent.side_effect = mock_create_agent_func
        
        # 模拟CLIApp，让run()方法立即返回
        mock_app = MagicMock()
        mock_app.run = MagicMock(return_value=None)
        mock_cli_app.return_value = mock_app
        
        # 测试命令行参数（新结构：直接使用-m，无agent命令）
        test_args = ["linhai", "-m", "测试消息"]
        
        with patch.object(sys, 'argv', test_args):
            # main()现在直接运行agent，不会调用sys.exit
            main()
        
        # 验证create_agent被调用时传入了init_messages
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        self.assertIsNotNone(call_args)
        
        # 检查init_messages参数
        init_messages = call_args.kwargs.get('init_messages')
        # 注意：由于create_agent的第二个参数是位置参数，我们需要从args获取
        if init_messages is None and len(call_args.args) >= 2:
            init_messages = call_args.args[1]
        self.assertIsNotNone(init_messages)
        self.assertEqual(len(init_messages), 1)
        self.assertEqual(init_messages[0].role, "user")
        self.assertEqual(init_messages[0].message, "测试消息")
        
        # 验证CLIApp被调用时init_message为None（避免重复消息）
        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertIsNone(cli_call_args.kwargs.get('init_message'))
        
        # 验证CLIApp.run()被调用
        mock_app.run.assert_called_once()
        
        # 检查agent的messages属性：应该只有一条用户消息，没有重复
        # 由于init_messages在create_agent中被添加到agent.messages，
        # 而CLIApp的on_mount又发送了一次，所以这里应该只有一条用户消息
        user_messages = [msg for msg in mock_agent.messages if hasattr(msg, 'role') and msg.role == 'user']
        self.assertEqual(len(user_messages), 1, f"期望1条用户消息，但找到{len(user_messages)}条: {user_messages}")
        self.assertEqual(user_messages[0].message, "测试消息")

    @patch('linhai.main.create_agent')
    @patch('linhai.main.CLIApp')
    def test_agent_command_without_message_option(self, mock_cli_app, mock_create_agent):
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
            mock_tool_manager
        )
        
        # 模拟CLIApp，让run()方法立即返回
        mock_app = MagicMock()
        mock_app.run = MagicMock(return_value=None)
        mock_cli_app.return_value = mock_app
        
        # 测试命令行参数（不使用-m选项）
        test_args = ["linhai"]
        
        with patch.object(sys, 'argv', test_args):
            # main()现在直接运行agent，不会调用sys.exit
            main()
        
        # 验证create_agent被调用时init_messages为None
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        self.assertIsNotNone(call_args)
        
        # 检查init_messages参数为None
        init_messages = call_args.kwargs.get('init_messages')
        self.assertIsNone(init_messages)
        
        # 验证CLIApp被调用时init_message为None
        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertIsNone(cli_call_args.kwargs.get('init_message'))
        
        # 验证CLIApp.run()被调用
        mock_app.run.assert_called_once()


if __name__ == '__main__':
    unittest.main()