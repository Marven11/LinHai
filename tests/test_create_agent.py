"""测试create_agent函数的基本功能"""

import unittest
from unittest.mock import patch, AsyncMock
import sys
import os
import asyncio
from pathlib import Path


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linhai.group_chat import GroupChat
from linhai.agent.create import create_agent_from_config
from linhai.agent.create import create_agent_build_context
from linhai.agent import Agent
from linhai.tool.main import ToolManager
from linhai.config import load_config


class TestCreateAgent(unittest.TestCase):
    """测试create_agent函数"""

    @patch("linhai.tool.mcp_connector.MCPConnector")
    def test_create_agent_basic_functionality(self, mock_mcp_connector):
        """测试create_agent基本功能：创建agent并返回group_chat"""
        mock_mcp_instance = AsyncMock()
        mock_mcp_instance.get_toolsets.return_value = []
        mock_mcp_connector.return_value = mock_mcp_instance

        group_chat = GroupChat()
        import argparse

        cli_args = argparse.Namespace()
        cli_args.git_diff_reviewer = False
        cli_args.violation_checker = False
        cli_args.checklist = None
        cli_args.message = []
        cli_args.file = []
        group_chat.register_member("cli_args", cli_args)
        config_path = Path(__file__).parent / "test_config.toml"

        config = load_config(Path(config_path))
        context = create_agent_build_context(
            group_chat=group_chat,
            config=config,
            config_basedir=Path("."),
            llm_name=None,
            git_diff_reviewer=cli_args.git_diff_reviewer,
            violation_checker=cli_args.violation_checker,
            cli_args=cli_args,
            checklist_path=None,
        )
        result = asyncio.run(create_agent_from_config(context))
        self.assertIsInstance(result, Agent)

        try:
            agent = group_chat.get_members("agent", Agent)
            self.assertIsNotNone(agent)
        except RuntimeError:
            self.fail("agent成员未在group_chat中注册")

        try:
            tool_manager = group_chat.get_members("tool_manager", ToolManager)
            self.assertIsNotNone(tool_manager)
        except RuntimeError:
            self.fail("tool_manager成员未在group_chat中注册")

    @patch("linhai.tool.mcp_connector.MCPConnector")
    def test_create_agent_with_llm_name(self, mock_mcp_connector):
        """测试使用llm_name参数创建agent"""
        mock_mcp_instance = AsyncMock()
        mock_mcp_instance.get_toolsets.return_value = []
        mock_mcp_connector.return_value = mock_mcp_instance

        group_chat = GroupChat()
        import argparse

        cli_args = argparse.Namespace()
        cli_args.git_diff_reviewer = False
        cli_args.violation_checker = False
        cli_args.checklist = None
        cli_args.message = []
        cli_args.file = []
        group_chat.register_member("cli_args", cli_args)
        config_path = Path(__file__).parent / "test_config.toml"

        config = load_config(Path(config_path))
        context = create_agent_build_context(
            group_chat=group_chat,
            config=config,
            config_basedir=Path("."),
            llm_name="test",
            git_diff_reviewer=cli_args.git_diff_reviewer,
            violation_checker=cli_args.violation_checker,
            cli_args=cli_args,
            checklist_path=None,
        )
        result = asyncio.run(create_agent_from_config(context))
        self.assertIsInstance(result, Agent)

        agent = group_chat.get_members("agent", Agent)
        self.assertEqual(agent.current_llm_index, 0)  # test是第一个LLM

    def test_create_agent_with_invalid_llm_name(self):
        """测试使用无效的llm_name参数应抛出错误"""
        group_chat = GroupChat()
        import argparse

        cli_args = argparse.Namespace()
        cli_args.git_diff_reviewer = False
        cli_args.violation_checker = False
        cli_args.checklist = None
        cli_args.message = []
        cli_args.file = []
        group_chat.register_member("cli_args", cli_args)
        config_path = Path(__file__).parent / "test_config.toml"

        from linhai.config import load_config

        config = load_config(Path(config_path))
        with self.assertRaises(ValueError) as context_error:
            context = create_agent_build_context(
                group_chat=group_chat,
                config=config,
                config_basedir=Path("."),
                llm_name="invalid_llm",
                git_diff_reviewer=cli_args.git_diff_reviewer,
                violation_checker=cli_args.violation_checker,
                cli_args=cli_args,
                checklist_path=None,
            )
            asyncio.run(create_agent_from_config(context))

        self.assertIn("LLM名称 'invalid_llm' 不存在", str(context_error.exception))


if __name__ == "__main__":
    unittest.main()
