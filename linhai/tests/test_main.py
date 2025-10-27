"""测试main.py命令行参数"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import io
from pathlib import Path
from linhai.main import main
from linhai.agent import Agent


class TestMainCommandLine(unittest.TestCase):
    """测试main.py的命令行参数"""

    @patch("linhai.main.create_agent")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    def test_agent_command_with_message_option(self, mock_group_chat, mock_cli_app, mock_create_agent):
        """测试使用-m选项时消息被正确传递"""
        # 模拟 GroupChat 实例
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance
        
        # 模拟 create_agent 没有返回值
        mock_create_agent.return_value = None

        # 模拟CLIApp，让run()方法立即返回
        mock_app = MagicMock()
        mock_app.run = MagicMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        # 测试命令行参数
        test_args = ["linhai", "-m", "测试消息"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            # 由于CLIApp.return_code是MagicMock，我们直接检查SystemExit被调用
        self.assertIsInstance(cm.exception, SystemExit)

        # 验证 create_agent 被调用，参数为 group_chat 和 config
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        # 应该被调用为 create_agent(group_chat, config_path)
        self.assertEqual(call_args[0][0], mock_group_chat_instance)  # 第一个参数是 group_chat
        self.assertIsInstance(call_args[0][1], Path)  # 第二个参数是 config path

        # 验证 GroupChat 的 get_members 被调用
        mock_group_chat_instance.get_members.assert_called_once_with("agent", Agent)

        # 验证CLIApp被调用时init_message为测试消息
        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertEqual(cli_call_args.kwargs.get("init_message"), "测试消息")
        self.assertEqual(cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance)

        # 验证CLIApp.run()被调用
        mock_app.run.assert_called_once()

    @patch("linhai.main.create_agent")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    def test_agent_command_without_message_option(
        self, mock_group_chat, mock_cli_app, mock_create_agent
    ):
        """测试不使用-m选项时init_message为None"""
        # 模拟 GroupChat 实例
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance
        
        # 模拟 create_agent 没有返回值
        mock_create_agent.return_value = None

        # 模拟CLIApp，让run()方法立即返回
        mock_app = MagicMock()
        mock_app.run = MagicMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        # 测试命令行参数（不使用-m选项）
        test_args = ["linhai"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            # 由于CLIApp.return_code是MagicMock，我们直接检查SystemExit被调用
        self.assertIsInstance(cm.exception, SystemExit)

        # 验证 create_agent 被调用，参数为 group_chat 和 config
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        # 应该被调用为 create_agent(group_chat, config_path)
        self.assertEqual(call_args[0][0], mock_group_chat_instance)  # 第一个参数是 group_chat
        self.assertIsInstance(call_args[0][1], Path)  # 第二个参数是 config path

        # 验证 GroupChat 的 get_members 被调用
        mock_group_chat_instance.get_members.assert_called_once_with("agent", Agent)

        # 验证CLIApp被调用时init_message为None
        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertIsNone(cli_call_args.kwargs.get("init_message"))
        self.assertEqual(cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance)

        # 验证CLIApp.run()被调用
        mock_app.run.assert_called_once()

    @patch("linhai.main.create_agent")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    @patch("builtins.open")
    def test_agent_command_with_file_option(self, mock_open, mock_group_chat, mock_cli_app, mock_create_agent):
        """测试使用-f选项时从文件读取消息"""
        # 模拟 GroupChat 实例
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance
        
        # 模拟 create_agent 没有返回值
        mock_create_agent.return_value = None

        # 模拟CLIApp，让run()方法立即返回
        mock_app = MagicMock()
        mock_app.run = MagicMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        # 模拟文件读取
        mock_file = MagicMock()
        mock_file.read.return_value = "文件中的测试消息\n"
        mock_open.return_value.__enter__.return_value = mock_file

        # 测试命令行参数（使用-f选项）
        test_args = ["linhai", "-f", "test_message.txt"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            # 由于CLIApp.return_code是MagicMock，我们直接检查SystemExit被调用
        self.assertIsInstance(cm.exception, SystemExit)

        # 验证文件被正确打开
        mock_open.assert_called_once_with(Path("test_message.txt"), "r", encoding="utf-8")

        # 验证 create_agent 被调用，参数为 group_chat 和 config
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        # 应该被调用为 create_agent(group_chat, config_path)
        self.assertEqual(call_args[0][0], mock_group_chat_instance)  # 第一个参数是 group_chat
        self.assertIsInstance(call_args[0][1], Path)  # 第二个参数是 config path

        # 验证 GroupChat 的 get_members 被调用
        mock_group_chat_instance.get_members.assert_called_once_with("agent", Agent)

        # 验证CLIApp被调用时init_message为文件内容（包含额外描述信息）
        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        expected_message = f"用户使用-f选项指定了第一条消息，路径为: {str(Path('test_message.txt'))}, 内容如下:\n文件中的测试消息"
        self.assertEqual(cli_call_args.kwargs.get("init_message"), expected_message)
        self.assertEqual(cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance)

        # 验证CLIApp.run()被调用
        mock_app.run.assert_called_once()

    @patch("linhai.main.create_agent")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    @patch("builtins.open")
    def test_agent_command_with_both_message_and_file_options(self, mock_open, mock_group_chat, mock_cli_app, mock_create_agent):
        """测试同时使用-m和-f选项时文件内容优先"""
        # 模拟 GroupChat 实例
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance
        
        # 模拟 create_agent 没有返回值
        mock_create_agent.return_value = None

        # 模拟CLIApp，让run()方法立即返回
        mock_app = MagicMock()
        mock_app.run = MagicMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        # 模拟文件读取
        mock_file = MagicMock()
        mock_file.read.return_value = "文件中的优先消息\n"
        mock_open.return_value.__enter__.return_value = mock_file

        # 测试命令行参数（同时使用-m和-f选项）
        test_args = ["linhai", "-m", "命令行消息", "-f", "test_message.txt"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            # 由于CLIApp.return_code是MagicMock，我们直接检查SystemExit被调用
        self.assertIsInstance(cm.exception, SystemExit)

        # 验证文件被正确打开
        mock_open.assert_called_once_with(Path("test_message.txt"), "r", encoding="utf-8")

        # 验证 create_agent 被调用，参数为 group_chat 和 config
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        # 应该被调用为 create_agent(group_chat, config_path)
        self.assertEqual(call_args[0][0], mock_group_chat_instance)  # 第一个参数是 group_chat
        self.assertIsInstance(call_args[0][1], Path)  # 第二个参数是 config path

        # 验证 GroupChat 的 get_members 被调用
        mock_group_chat_instance.get_members.assert_called_once_with("agent", Agent)

        # 验证CLIApp被调用时init_message为文件内容（包含额外描述信息）
        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        expected_message = f"用户使用-f选项指定了第一条消息，路径为: {str(Path('test_message.txt'))}, 内容如下:\n文件中的优先消息"
        self.assertEqual(cli_call_args.kwargs.get("init_message"), expected_message)
        self.assertEqual(cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance)

        # 验证CLIApp.run()被调用
        mock_app.run.assert_called_once()

    @patch("linhai.main.create_agent")
    @patch("linhai.main.CLIApp")
    @patch("builtins.open")
    def test_agent_command_with_file_option_file_not_found(self, mock_open, mock_cli_app, mock_create_agent):
        """测试使用-f选项时文件不存在的错误处理"""
        # 模拟文件不存在错误
        mock_open.side_effect = FileNotFoundError("文件未找到")

        # 测试命令行参数（使用-f选项）
        test_args = ["linhai", "-f", "nonexistent.txt"]

        with patch.object(sys, "argv", test_args):
            with patch("sys.exit") as mock_exit:
                # 让sys.exit抛出SystemExit异常
                mock_exit.side_effect = SystemExit(1)
                with self.assertRaises(SystemExit):
                    main()

        # 验证文件打开尝试
        mock_open.assert_called_once_with(Path("nonexistent.txt"), "r", encoding="utf-8")

        # 验证create_agent和CLIApp没有被调用
        mock_create_agent.assert_not_called()
        mock_cli_app.assert_not_called()

        # 验证程序以错误代码退出
        mock_exit.assert_called_once_with(1)

    @patch("linhai.main.create_agent")
    @patch("linhai.main.CLIApp")
    @patch("builtins.open")
    def test_agent_command_with_file_option_read_error(self, mock_open, mock_cli_app, mock_create_agent):
        """测试使用-f选项时文件读取错误的处理"""
        # 模拟文件读取错误
        mock_open.side_effect = Exception("读取错误")

        # 测试命令行参数（使用-f选项）
        test_args = ["linhai", "-f", "corrupted.txt"]

        with patch.object(sys, "argv", test_args):
            with patch("sys.exit") as mock_exit:
                # 让sys.exit抛出SystemExit异常
                mock_exit.side_effect = SystemExit(1)
                with self.assertRaises(SystemExit):
                    main()

        # 验证文件打开尝试
        mock_open.assert_called_once_with(Path("corrupted.txt"), "r", encoding="utf-8")

        # 验证create_agent和CLIApp没有被调用
        mock_create_agent.assert_not_called()
        mock_cli_app.assert_not_called()

        # 验证程序以错误代码退出
        mock_exit.assert_called_once_with(1)

    @patch("linhai.main.create_agent")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    def test_agent_command_with_llm_option(self, mock_group_chat, mock_cli_app, mock_create_agent):
        """测试使用--llm选项时LLM名称被正确传递"""
        # 模拟 GroupChat 实例
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance
        
        # 模拟 create_agent 没有返回值
        mock_create_agent.return_value = None

        # 模拟CLIApp，让run()方法立即返回
        mock_app = MagicMock()
        mock_app.run = MagicMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        # 测试命令行参数
        test_args = ["linhai", "--llm", "test_llm"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            # 由于CLIApp.return_code是MagicMock，我们直接检查SystemExit被调用
        self.assertIsInstance(cm.exception, SystemExit)

        # 验证 create_agent 被调用，参数为 group_chat, config_path 和 llm_name
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        # 应该被调用为 create_agent(group_chat, config_path, llm_name)
        self.assertEqual(call_args[0][0], mock_group_chat_instance)  # 第一个参数是 group_chat
        self.assertIsInstance(call_args[0][1], Path)  # 第二个参数是 config path
        self.assertEqual(call_args[0][2], "test_llm")  # 第三个参数是 llm_name

        # 验证 GroupChat 的 get_members 被调用
        mock_group_chat_instance.get_members.assert_called_once_with("agent", Agent)

        # 验证CLIApp被调用时init_message为None
        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertIsNone(cli_call_args.kwargs.get("init_message"))
        self.assertEqual(cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance)

        # 验证CLIApp.run()被调用
        mock_app.run.assert_called_once()

    @patch("linhai.main.create_agent")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    def test_agent_command_with_llm_and_message_options(self, mock_group_chat, mock_cli_app, mock_create_agent):
        """测试同时使用--llm和-m选项"""
        # 模拟 GroupChat 实例
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance
        
        # 模拟 create_agent 没有返回值
        mock_create_agent.return_value = None

        # 模拟CLIApp，让run()方法立即返回
        mock_app = MagicMock()
        mock_app.run = MagicMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        # 测试命令行参数
        test_args = ["linhai", "--llm", "test_llm", "-m", "测试消息"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            # 由于CLIApp.return_code是MagicMock，我们直接检查SystemExit被调用
        self.assertIsInstance(cm.exception, SystemExit)

        # 验证 create_agent 被调用，参数为 group_chat, config_path 和 llm_name
        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        # 应该被调用为 create_agent(group_chat, config_path, llm_name)
        self.assertEqual(call_args[0][0], mock_group_chat_instance)  # 第一个参数是 group_chat
        self.assertIsInstance(call_args[0][1], Path)  # 第二个参数是 config path
        self.assertEqual(call_args[0][2], "test_llm")  # 第三个参数是 llm_name

        # 验证 GroupChat 的 get_members 被调用
        mock_group_chat_instance.get_members.assert_called_once_with("agent", Agent)

        # 验证CLIApp被调用时init_message为测试消息
        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertEqual(cli_call_args.kwargs.get("init_message"), "测试消息")
        self.assertEqual(cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance)

        # 验证CLIApp.run()被调用
        mock_app.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()