"""测试create_agent函数的基本功能"""

import unittest
from unittest.mock import patch, AsyncMock, Mock
import sys
import os
import asyncio
from pathlib import Path


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linhai.registry import Registry
from linhai.agent.create import create_agent_from_config
from linhai.agent.create import create_agent_build_context
from linhai.agent import Agent
from linhai.tool.main import ToolManager
from linhai.config import load_config


class TestCreateAgent(unittest.TestCase):
    """测试create_agent函数"""

    @patch("linhai.tool.mcp_connector.MCPConnector")
    def test_create_agent_basic_functionality(self, mock_mcp_connector):
        """测试create_agent基本功能：创建agent并返回registry"""
        mock_mcp_instance = Mock()
        mock_mcp_instance.get_toolsets.return_value = []
        mock_mcp_connector.return_value = mock_mcp_instance

        registry = Registry()
        import argparse

        cli_args = argparse.Namespace()

        cli_args.checklist = None
        cli_args.message = []
        cli_args.file = []
        cli_args.claw = False
        cli_args.claw_folder = None
        cli_args.disable_waiting_marker = False
        cli_args.rss = []
        cli_args.telegram = False
        registry.register_member("cli_args", cli_args)
        config_path = Path(__file__).parent / "test_config.toml"

        config = load_config(Path(config_path))
        context = create_agent_build_context(
            registry=registry,
            config=config,
            config_basedir=Path("."),
            llm_name=None,
            cli_args=cli_args,
            checklist_path=None,
        )
        result = asyncio.run(create_agent_from_config(context))
        self.assertIsInstance(result, Agent)

        try:
            agent = registry.get_member_typechecked("agent", Agent)
            self.assertIsNotNone(agent)
        except RuntimeError:
            self.fail("agent成员未在registry中注册")

        try:
            tool_manager = registry.get_member_typechecked("tool_manager", ToolManager)
            self.assertIsNotNone(tool_manager)
        except RuntimeError:
            self.fail("tool_manager成员未在registry中注册")

    @patch("linhai.tool.mcp_connector.MCPConnector")
    def test_create_agent_with_llm_name(self, mock_mcp_connector):
        """测试使用llm_name参数创建agent"""
        mock_mcp_instance = Mock()
        mock_mcp_instance.get_toolsets.return_value = []
        mock_mcp_connector.return_value = mock_mcp_instance

        registry = Registry()
        import argparse

        cli_args = argparse.Namespace()

        cli_args.checklist = None
        cli_args.message = []
        cli_args.file = []
        cli_args.claw = False
        cli_args.claw_folder = None
        cli_args.disable_waiting_marker = False
        cli_args.rss = []
        cli_args.telegram = False
        registry.register_member("cli_args", cli_args)
        config_path = Path(__file__).parent / "test_config.toml"

        config = load_config(Path(config_path))
        context = create_agent_build_context(
            registry=registry,
            config=config,
            config_basedir=Path("."),
            llm_name="test",
            cli_args=cli_args,
            checklist_path=None,
        )
        result = asyncio.run(create_agent_from_config(context))
        self.assertIsInstance(result, Agent)

        agent = registry.get_member_typechecked("agent", Agent)
        current_llm = agent.llm_manager.get_current_llm()
        self.assertEqual(current_llm.get_name(), "test")

    def test_create_agent_with_invalid_llm_name(self):
        """测试使用无效的llm_name参数应抛出错误"""
        registry = Registry()
        import argparse

        cli_args = argparse.Namespace()

        cli_args.checklist = None
        cli_args.message = []
        cli_args.file = []
        cli_args.claw = False
        cli_args.claw_folder = None
        registry.register_member("cli_args", cli_args)
        config_path = Path(__file__).parent / "test_config.toml"

        from linhai.config import load_config

        config = load_config(Path(config_path))
        with self.assertRaises(ValueError) as context_error:
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                llm_name="invalid_llm",
                cli_args=cli_args,
                checklist_path=None,
            )
            asyncio.run(create_agent_from_config(context))

        self.assertIn("LLM名称 'invalid_llm' 不存在", str(context_error.exception))


if __name__ == "__main__":
    unittest.main()
