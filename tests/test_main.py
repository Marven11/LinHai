"""测试main.py命令行参数"""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
from pathlib import Path
from linhai.main import main
from linhai.config import Config


class TestMainCommandLine(unittest.TestCase):
    """测试main.py的命令行参数"""

    @patch("linhai.agent.create.create_agent_from_config")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    def test_agent_command_with_message_option(
        self, mock_group_chat, mock_cli_app, mock_create_agent
    ):
        """测试使用-m选项时消息被正确传递"""
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        # 设置cli_args以正确模拟
        mock_cli_args = MagicMock()
        mock_cli_args.message = ["测试消息"]
        mock_cli_args.file = []
        mock_cli_args.claw = False
        mock_group_chat_instance.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: mock_cli_args
        )

        test_args = ["linhai", "-m", "测试消息"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertIsInstance(cm.exception, SystemExit)

        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        self.assertEqual(len(call_args[0]), 1)  # 现在只有一个参数：context字典
        context = call_args[0][0]
        self.assertEqual(
            context["group_chat"], mock_group_chat_instance
        )  # context字典中的group_chat
        self.assertIsInstance(context["config"], Config)  # context字典中的config
        self.assertIn("cli_args", context)  # cli_args应该在context中

        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertEqual(
            cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance
        )
        # 不再检查init_messages参数，因为现在它在CLIApp内部构建

        mock_app.run_async.assert_called_once()

    @patch("linhai.agent.create.create_agent_from_config")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    def test_agent_command_without_message_option(
        self, mock_group_chat, mock_cli_app, mock_create_agent
    ):
        """测试不使用-m选项时init_message为None"""
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        test_args = ["linhai"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertIsInstance(cm.exception, SystemExit)

        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        self.assertEqual(len(call_args[0]), 1)  # 现在只有一个参数：context字典
        context = call_args[0][0]
        self.assertEqual(
            context["group_chat"], mock_group_chat_instance
        )  # context字典中的group_chat
        self.assertIsInstance(context["config"], Config)  # context字典中的config

        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertEqual(
            cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance
        )

        mock_app.run_async.assert_called_once()

    @patch("linhai.agent.create.create_agent_from_config")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    @patch("builtins.open")
    def test_agent_command_with_file_option(
        self, mock_open, mock_group_chat, mock_cli_app, mock_create_agent
    ):
        """测试使用-f选项时从文件读取消息"""
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        mock_file = MagicMock()
        mock_file.read.return_value = "文件中的测试消息\n"
        mock_open.return_value.__enter__.return_value = mock_file

        test_args = ["linhai", "-f", "test_message.txt"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertIsInstance(cm.exception, SystemExit)

        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        self.assertEqual(len(call_args[0]), 1)  # 现在只有一个参数：context字典
        context = call_args[0][0]
        self.assertEqual(
            context["group_chat"], mock_group_chat_instance
        )  # context字典中的group_chat
        self.assertIsInstance(context["config"], Config)  # context字典中的config

        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertEqual(
            cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance
        )

        mock_app.run_async.assert_called_once()

    @patch("linhai.agent.create.create_agent_from_config")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    @patch("builtins.open")
    def test_agent_command_with_both_message_and_file_options(
        self, mock_open, mock_group_chat, mock_cli_app, mock_create_agent
    ):
        """测试同时使用-m和-f选项时文件内容优先"""
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        mock_file = MagicMock()
        mock_file.read.return_value = "文件中的优先消息\n"
        mock_open.return_value.__enter__.return_value = mock_file

        test_args = ["linhai", "-m", "命令行消息", "-f", "test_message.txt"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertIsInstance(cm.exception, SystemExit)

        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        self.assertEqual(len(call_args[0]), 1)  # 现在只有一个参数：context字典
        context = call_args[0][0]
        self.assertEqual(
            context["group_chat"], mock_group_chat_instance
        )  # context字典中的group_chat
        self.assertIsInstance(context["config"], Config)  # context字典中的config

        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertEqual(
            cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance
        )

        mock_app.run_async.assert_called_once()

    @patch("linhai.agent.create.create_agent_from_config")
    @patch("linhai.main.CLIApp")
    def test_agent_command_with_file_option_file_not_found(
        self, mock_cli_app, mock_create_agent
    ):
        """测试使用-f选项时文件不存在的错误处理"""
        # 模拟create_agent_from_config抛出FileNotFoundError
        mock_create_agent.side_effect = FileNotFoundError("文件未找到")
        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        test_args = ["linhai", "-f", "nonexistent.txt"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(FileNotFoundError):
                main()

        mock_create_agent.assert_called_once()
        mock_cli_app.assert_not_called()

    @patch("linhai.agent.create.create_agent_from_config")
    @patch("linhai.main.CLIApp")
    def test_agent_command_with_file_option_read_error(
        self, mock_cli_app, mock_create_agent
    ):
        """测试使用-f选项时文件读取错误的处理"""
        # 模拟create_agent_from_config抛出Exception
        mock_create_agent.side_effect = Exception("读取错误")
        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        test_args = ["linhai", "-f", "corrupted.txt"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(Exception):
                main()

        mock_create_agent.assert_called_once()
        mock_cli_app.assert_not_called()

    @patch("linhai.agent.create.create_agent_build_context")
    @patch("linhai.agent.create.create_agent_from_config")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    def test_agent_command_with_llm_option(
        self, mock_group_chat, mock_cli_app, mock_create_agent, mock_create_context
    ):
        """测试使用--llm选项时LLM名称被正确传递"""
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        # 模拟create_agent_build_context返回有效的context
        mock_context = {
            "group_chat": mock_group_chat_instance,
            "config": MagicMock(spec=Config),
            "config_basedir": Path("."),
            "llm_name": "test_llm",
            "checklist_path": None,
            "git_diff_reviewer": False,
            "violation_checker": False,
        }
        mock_create_context.return_value = mock_context

        test_args = ["linhai", "--llm", "test_llm"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertIsInstance(cm.exception, SystemExit)

        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        self.assertEqual(len(call_args[0]), 1)  # 现在只有一个参数：context字典
        context = call_args[0][0]
        self.assertEqual(
            context["group_chat"], mock_group_chat_instance
        )  # context字典中的group_chat
        self.assertIsInstance(context["config"], Config)  # context字典中的config
        context = call_args[0][0]
        self.assertEqual(
            context.get("llm_name"), "test_llm"
        )  # llm_name 在context字典中

        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertEqual(
            cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance
        )

        mock_app.run_async.assert_called_once()

    @patch("linhai.agent.create.create_agent_build_context")
    @patch("linhai.agent.create.create_agent_from_config")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    def test_agent_command_with_llm_and_message_options(
        self, mock_group_chat, mock_cli_app, mock_create_agent, mock_create_context
    ):
        """测试同时使用--llm和-m选项"""
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        # 模拟create_agent_build_context返回有效的context
        mock_context = {
            "group_chat": mock_group_chat_instance,
            "config": MagicMock(spec=Config),
            "config_basedir": Path("."),
            "llm_name": "test_llm",
            "checklist_path": None,
            "git_diff_reviewer": False,
            "violation_checker": False,
        }
        mock_create_context.return_value = mock_context

        test_args = ["linhai", "--llm", "test_llm", "-m", "测试消息"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertIsInstance(cm.exception, SystemExit)

        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        self.assertEqual(len(call_args[0]), 1)  # 现在只有一个参数：context字典
        context = call_args[0][0]
        self.assertEqual(
            context["group_chat"], mock_group_chat_instance
        )  # context字典中的group_chat
        self.assertIsInstance(context["config"], Config)  # context字典中的config
        context = call_args[0][0]
        self.assertEqual(
            context.get("llm_name"), "test_llm"
        )  # llm_name 在context字典中

        mock_cli_app.assert_called_once()
        cli_call_args = mock_cli_app.call_args
        self.assertEqual(
            cli_call_args.kwargs.get("group_chat"), mock_group_chat_instance
        )

        mock_app.run_async.assert_called_once()

    @patch("linhai.agent.create.create_agent_build_context")
    @patch("linhai.agent.create.create_agent_from_config")
    @patch("linhai.main.CLIApp")
    @patch("linhai.main.GroupChat")
    def test_agent_command_with_checklist_option(
        self, mock_group_chat, mock_cli_app, mock_create_agent, mock_create_context
    ):
        """测试使用--checklist选项时checklist路径被正确传递"""
        mock_group_chat_instance = MagicMock()
        mock_group_chat.return_value = mock_group_chat_instance

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        # 模拟create_agent_build_context返回有效的context
        mock_context = {
            "group_chat": mock_group_chat_instance,
            "config": MagicMock(spec=Config),
            "config_basedir": Path("."),
            "llm_name": None,
            "checklist_path": Path("requirements.txt"),
        }
        mock_create_context.return_value = mock_context

        test_args = ["linhai", "--checklist", "requirements.txt"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertIsInstance(cm.exception, SystemExit)

        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        context = call_args[0][0]
        self.assertEqual(
            context.get("checklist_path"), Path("requirements.txt")
        )  # checklist_path在context字典中


class TestClawDirectory(unittest.TestCase):
    """测试claw目录相关功能"""

    def test_init_claw_creates_new(self):
        """测试init_claw创建新目录"""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                from linhai.agent.create import init_claw

                init_claw()

                claw_dir = Path(temp_dir) / ".local" / "share" / "linhai" / "claw"
                self.assertTrue(claw_dir.exists())
                self.assertTrue(claw_dir.is_dir())

    def test_init_claw_existing_ok(self):
        """测试init_claw处理已存在目录"""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                # 预先创建目录
                claw_dir = Path(temp_dir) / ".local" / "share" / "linhai" / "claw"
                claw_dir.mkdir(parents=True, exist_ok=True)

                from linhai.agent.create import init_claw

                init_claw()  # 不应出错

                self.assertTrue(claw_dir.exists())
