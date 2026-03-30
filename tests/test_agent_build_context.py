"""测试AgentBuildContext中rss/telegram/disable_waiting_marker的传递"""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import argparse

from linhai.agent.create import create_agent_build_context
from linhai.registry import Registry


class TestAgentBuildContextParameters(unittest.TestCase):
    """测试AgentBuildContext中cli_args参数迁移"""

    def setUp(self):
        """测试前置设置"""
        self.registry = Mock(spec=Registry)
        self.config = Mock()

        mock_llm_config = Mock()
        mock_llm_config.name = "test_llm"
        mock_llm_config.base_url = "http://test.com"
        mock_llm_config.api_key = "test_key"
        mock_llm_config.model = "test-model"
        mock_llm_config.model_dump.return_value = {
            "client_options": {},
            "completion_options": {},
            "token_limit": 1000,
            "compatibility": "openai",
        }

        self.config.llm = [mock_llm_config]
        self.config.agent = Mock()
        self.config.agent.default_llm = "test_llm"
        self.config.agent.override_toolsets = None
        self.config.agent.compress_threshold = 0.8
        self.config.agent.enable_directory_change_detection = False
        self.config.agent.max_toolcall_for_llm = {}
        self.config.agent.allowed_commands = []
        self.config.agent.mcp = []
        self.config.tools = Mock()
        self.config.tools.toolsets = "defaults"
        self.config.tools.max_toolcall_token_in_round = 0.3
        self.config.tools.secret = Mock()
        self.config.tools.secret.config_path = None
        self.config.user_prompt = None
        self.config.remote_control = Mock()
        self.config.remote_control.telegram = None

    def test_agent_build_context_with_rss(self):
        """测试rss参数从cli_args传递到AgentBuildContext"""
        cli_args = argparse.Namespace(
            rss=["http://example.com/rss1", "http://example.com/rss2"],
            telegram=False,
            disable_waiting_marker=False,
            message=None,
            file=None,
            claw=False,
        )

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            cli_args=cli_args,
        )

        self.assertEqual(
            context["rss"], ["http://example.com/rss1", "http://example.com/rss2"]
        )

    def test_agent_build_context_with_telegram(self):
        """测试telegram参数从cli_args传递到AgentBuildContext"""
        cli_args = argparse.Namespace(
            rss=[],
            telegram=True,
            disable_waiting_marker=False,
            message=None,
            file=None,
            claw=False,
        )

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            cli_args=cli_args,
        )

        self.assertEqual(context["telegram"], True)

    def test_agent_build_context_with_disable_waiting_marker(self):
        """测试disable_waiting_marker参数从cli_args传递到AgentBuildContext"""
        cli_args = argparse.Namespace(
            rss=[],
            telegram=False,
            disable_waiting_marker=True,
            message=None,
            file=None,
            claw=False,
        )

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            cli_args=cli_args,
        )

        self.assertEqual(context["disable_waiting_marker"], True)

    def test_agent_build_context_with_all_parameters(self):
        """测试所有参数同时传递"""
        cli_args = argparse.Namespace(
            rss=["http://example.com/rss"],
            telegram=True,
            disable_waiting_marker=True,
            message=None,
            file=None,
            claw=False,
        )

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            cli_args=cli_args,
        )

        self.assertEqual(context["rss"], ["http://example.com/rss"])
        self.assertEqual(context["telegram"], True)
        self.assertEqual(context["disable_waiting_marker"], True)

    def test_agent_build_context_with_default_values(self):
        """测试默认值"""
        cli_args = argparse.Namespace(
            rss=[],
            telegram=False,
            disable_waiting_marker=False,
            message=None,
            file=None,
            claw=False,
        )

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            cli_args=cli_args,
        )

        self.assertEqual(context["rss"], [])
        self.assertEqual(context["telegram"], False)
        self.assertEqual(context["disable_waiting_marker"], False)


if __name__ == "__main__":
    unittest.main()
