#!/usr/bin/env python3
"""测试create.py中的CommandWhitelistPlugin注册逻辑。"""
import unittest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import argparse
from linhai.agent.create import create_agent_build_context, create_agent_from_config
from linhai.config import Config
from linhai.group_chat import GroupChat


class TestCreateCommandWhitelist(unittest.IsolatedAsyncioTestCase):
    """测试create.py中的命令白名单插件注册。"""

    async def test_plugin_registered_when_allowed_commands_present(self):
        """测试当配置中有allowed_commands时插件被注册。"""

        group_chat = Mock(spec=GroupChat)
        config_data = {
            "llm": [
                {
                    "name": "test",
                    "base_url": "https://example.com",
                    "api_key": "key",
                    "model": "model",
                }
            ],
            "agent": {
                "allowed_commands": [["ls"], ["git", "status"]],
                "compress_threshold": 0.8,
            },
        }
        config = Config(**config_data)
        config_basedir = Path("/tmp")
        cli_args = argparse.Namespace()
        cli_args.claw = False
        cli_args.disable_waiting_marker = False
        cli_args.rss = []

        context = create_agent_build_context(
            group_chat=group_chat,
            config=config,
            config_basedir=config_basedir,
            cli_args=cli_args,
            llm_name="test",
        )

        with (
            patch("linhai.agent.create._create_llm_instances") as mock_create_llms,
            patch("linhai.agent.create._create_tool_manager") as mock_create_tools,
            patch("linhai.agent.create._create_pinned_messages") as mock_create_msgs,
        ):

            mock_llm = Mock()
            mock_llm.get_name.return_value = "test"
            mock_create_llms.return_value = [mock_llm]

            mock_tool_manager = Mock()
            mock_machine_control = Mock()
            mock_create_tools.return_value = (mock_tool_manager, mock_machine_control)

            mock_create_msgs.return_value = []

            mock_agent = Mock()
            mock_agent.lifecycle = Mock()

            with patch("linhai.agent.create.Agent", return_value=mock_agent):

                await create_agent_from_config(context)

                from unittest.mock import ANY

                mock_machine_control.register_plugin.assert_called_once_with(ANY)

                mock_tool_manager.register_lifecycle.assert_called_once()

    async def test_plugin_not_registered_when_no_allowed_commands(self):
        """测试当配置中没有allowed_commands时插件不被注册。"""

        group_chat = Mock(spec=GroupChat)
        config_data = {
            "llm": [
                {
                    "name": "test",
                    "base_url": "https://example.com",
                    "api_key": "key",
                    "model": "model",
                }
            ],
            "agent": {
                "compress_threshold": 0.8,
            },
        }
        config = Config(**config_data)
        config_basedir = Path("/tmp")
        cli_args = argparse.Namespace()
        cli_args.claw = False
        cli_args.disable_waiting_marker = False
        cli_args.rss = []

        context = create_agent_build_context(
            group_chat=group_chat,
            config=config,
            config_basedir=config_basedir,
            cli_args=cli_args,
            llm_name="test",
        )

        with (
            patch("linhai.agent.create._create_llm_instances") as mock_create_llms,
            patch("linhai.agent.create._create_tool_manager") as mock_create_tools,
            patch("linhai.agent.create._create_pinned_messages") as mock_create_msgs,
        ):

            mock_llm = Mock()
            mock_llm.get_name.return_value = "test"
            mock_create_llms.return_value = [mock_llm]

            mock_tool_manager = Mock()
            mock_machine_control = Mock()
            mock_create_tools.return_value = (mock_tool_manager, mock_machine_control)

            mock_create_msgs.return_value = []

            mock_agent = Mock()
            mock_agent.lifecycle = Mock()

            with patch("linhai.agent.create.Agent", return_value=mock_agent):

                await create_agent_from_config(context)

                from unittest.mock import ANY

                mock_machine_control.register_plugin.assert_called_once_with(ANY)

                mock_tool_manager.register_lifecycle.assert_called_once()


if __name__ == "__main__":
    unittest.main()
