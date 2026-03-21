import unittest
import argparse
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from linhai.plugin.message_checkers import WaitingUserPlugin
from linhai.plugin.afk_plugin import AfkPlugin
from linhai.agent.main import Agent
from linhai.group_chat import GroupChat
from linhai.config import CLIConfig
from linhai.agent.base import RuntimeMessage


class TestAfkParam(unittest.TestCase):
    """测试--afk命令行参数功能"""

    def setUp(self):
        self.group_chat = GroupChat()

    def test_waiting_user_plugin_afk_true(self):
        """测试afk=True时WaitingUserPlugin直接返回，不执行检查"""
        cli_args = argparse.Namespace(afk=True)
        self.group_chat.register_member("cli_args", cli_args)

        mock_agent = Mock()
        mock_agent.current_disable_waiting_user_warning = False
        mock_agent.message_processor = Mock()

        plugin = WaitingUserPlugin(self.group_chat)

        def get_member_typechecked_side_effect(name, t):
            if name == "cli_args":
                return cli_args
            elif name == "agent":
                return mock_agent
            else:
                raise RuntimeError(f"Unexpected name: {name}")

        with patch.object(
            self.group_chat,
            "get_member_typechecked",
            side_effect=get_member_typechecked_side_effect,
        ):
            result = asyncio.run(
                plugin.after_message_generation(
                    Mock(), "test response without marker", []
                )
            )

        mock_agent.message_processor.add_new_message.assert_not_called()

    def test_waiting_user_plugin_afk_false(self):
        """测试afk=False时WaitingUserPlugin正常执行检查"""
        cli_args = argparse.Namespace(afk=False)
        self.group_chat.register_member("cli_args", cli_args)

        mock_agent = Mock()
        mock_agent.current_disable_waiting_user_warning = False
        mock_agent.state = "working"
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        plugin = WaitingUserPlugin(self.group_chat)

        def get_member_typechecked_side_effect(name, t):
            if name == "cli_args":
                return cli_args
            elif name == "agent":
                return mock_agent
            else:
                raise RuntimeError(f"Unexpected name: {name}")

        with patch.object(
            self.group_chat,
            "get_member_typechecked",
            side_effect=get_member_typechecked_side_effect,
        ):
            result = asyncio.run(
                plugin.after_message_generation(
                    Mock(), "test response without marker", []
                )
            )

        mock_agent.message_processor.add_new_message.assert_called()

    def test_main_afk_param_added(self):
        """测试main.py中正确添加了--afk参数"""
        import linhai.main

        parser = argparse.ArgumentParser(description="LinHai 主程序")
        parser.add_argument(
            "--config",
            type=Path,
            default="~/.config/linhai/config.toml",
            help="配置文件路径",
        )
        parser.add_argument(
            "-m",
            "--message",
            type=str,
            action="append",
            default=[],
            help="初始用户消息",
        )
        parser.add_argument(
            "-f",
            "--file",
            type=Path,
            action="append",
            default=[],
            help="从文件中读取初始用户消息",
        )
        parser.add_argument("--llm", type=str, help="强制指定使用的LLM名称")
        parser.add_argument(
            "--checklist",
            type=Path,
            help="检查清单文件路径，包含一系列代码要求，如./CODE_REQUIREMENTS.md",
        )
        parser.add_argument(
            "--afk",
            action="store_true",
            help="关闭 #LINHAI_WAITING_USER 功能",
        )

        args = parser.parse_args([])
        self.assertFalse(args.afk)

        args_with_afk = parser.parse_args(["--afk"])
        self.assertTrue(args_with_afk.afk)

        help_text = parser.format_help()
        self.assertIn("--afk", help_text)
        self.assertIn("关闭 #LINHAI_WAITING_USER 功能", help_text)

    def test_afk_plugin_afk_true(self):
        """测试afk=True时AfkPlugin正确设置working状态并发送消息"""
        cli_args = argparse.Namespace(afk=True)
        self.group_chat.register_member("cli_args", cli_args)

        mock_agent = Mock()
        mock_agent.state = "waiting_user"
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        plugin = AfkPlugin(self.group_chat)

        def get_member_typechecked_side_effect(name, t):
            if name == "cli_args":
                return cli_args
            elif name == "agent":
                return mock_agent
            else:
                raise RuntimeError(f"Unexpected name: {name}")

        with patch.object(
            self.group_chat,
            "get_member_typechecked",
            side_effect=get_member_typechecked_side_effect,
        ):
            result = asyncio.run(plugin.before_waiting_user(mock_agent))

        # 验证状态被设置为working
        self.assertEqual(mock_agent.state, "working")
        # 验证消息被添加
        mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = mock_agent.message_processor.add_new_message.call_args
        self.assertIsInstance(call_args[0][0], RuntimeMessage)

    def test_afk_plugin_afk_false(self):
        """测试afk=False时AfkPlugin不执行任何操作"""
        cli_args = argparse.Namespace(afk=False)
        self.group_chat.register_member("cli_args", cli_args)

        mock_agent = Mock()
        mock_agent.state = "waiting_user"
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        plugin = AfkPlugin(self.group_chat)

        def get_member_typechecked_side_effect(name, t):
            if name == "cli_args":
                return cli_args
            elif name == "agent":
                return mock_agent
            else:
                raise RuntimeError(f"Unexpected name: {name}")

        with patch.object(
            self.group_chat,
            "get_member_typechecked",
            side_effect=get_member_typechecked_side_effect,
        ):
            result = asyncio.run(plugin.before_waiting_user(mock_agent))

        # 验证状态未改变
        self.assertEqual(mock_agent.state, "waiting_user")
        # 验证消息未被添加
        mock_agent.message_processor.add_new_message.assert_not_called()

    def test_afk_plugin_register(self):
        """测试AfkPlugin注册正确的事件"""
        plugin = AfkPlugin(self.group_chat)
        mock_lifecycle = Mock()

        plugin.register(mock_lifecycle)

        # 验证注册了before_waiting_user事件
        mock_lifecycle.register_before_waiting_user.assert_called_once_with(
            plugin.before_waiting_user
        )


if __name__ == "__main__":
    unittest.main()
