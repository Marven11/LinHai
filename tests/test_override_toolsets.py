"""测试agent级别工具集配置功能"""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from linhai.config import AgentConfig, ConfigValidationError
from linhai.agent.create import create_agent_from_context, create_agent_build_context


class TestAgentToolsetConfig(unittest.TestCase):
    """测试agent级别的enable_toolsets/disable_toolsets配置"""

    def test_enable_toolsets_none(self):
        config = AgentConfig()
        self.assertIsNone(config.enable_toolsets)
        self.assertIsNone(config.disable_toolsets)

    def test_enable_toolsets_with_list(self):
        config = AgentConfig(enable_toolsets=["utils", "sleep"])
        self.assertEqual(config.enable_toolsets, ["utils", "sleep"])

    def test_disable_toolsets_with_list(self):
        config = AgentConfig(disable_toolsets=["llm"])
        self.assertEqual(config.disable_toolsets, ["llm"])

    def test_enable_and_disable_mutually_exclusive(self):
        with self.assertRaises(ConfigValidationError):
            AgentConfig(enable_toolsets=["utils"], disable_toolsets=["llm"])

    def test_enable_toolsets_invalid(self):
        with self.assertRaises(ConfigValidationError):
            AgentConfig(enable_toolsets=["invalid"])

    def test_disable_toolsets_invalid(self):
        with self.assertRaises(ConfigValidationError):
            AgentConfig(disable_toolsets=["invalid"])

    def test_enable_toolsets_in_full_config(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
enable_toolsets = ["utils", "sleep"]
"""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(config_content)
            temp_file = f.name

        try:
            from linhai.config import load_config

            config = load_config(temp_file)
            self.assertEqual(config.agent[0].enable_toolsets, ["utils", "sleep"])
        finally:
            os.unlink(temp_file)

    def test_disable_toolsets_in_full_config(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
disable_toolsets = ["llm"]
"""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(config_content)
            temp_file = f.name

        try:
            from linhai.config import load_config

            config = load_config(temp_file)
            self.assertEqual(config.agent[0].disable_toolsets, ["llm"])
        finally:
            os.unlink(temp_file)

    @patch("linhai.agent.create._create_llm_instances")
    @patch("linhai.agent.create._create_tool_manager")
    @patch("linhai.agent.create._create_pinned_messages")
    @patch("linhai.multimodal.MultimodalToolsetManager")
    @patch("linhai.agent.conversation.register_conversation_folder")
    @patch("linhai.agent.main.Agent")
    def test_enable_toolsets_applied_in_agent_creation(
        self,
        mock_agent,
        mock_register_conversation_folder,
        mock_multimodal_toolset_manager,
        mock_pinned_messages,
        mock_tool_manager,
        mock_llm_instances,
    ):
        mock_config = Mock()
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

        mock_config.llm = [mock_llm_config]
        mock_config.agent = [Mock()]
        mock_config.agent[0].enable_toolsets = ["utils", "sleep"]
        mock_config.agent[0].disable_toolsets = None
        mock_config.agent[0].process_sandbox = None
        mock_config.tools = Mock()
        mock_config.tools.enable_toolsets = None
        mock_config.tools.disable_toolsets = None
        mock_config.tools.secret.config_path = ""
        mock_config.user_prompt = Mock()()()
        mock_config.user_prompt.file_path = "prompt.md"
        mock_config.subagent = Mock()
        mock_config.tui = Mock()

        from linhai.llm import OpenAi

        mock_llm = Mock(spec=OpenAi)
        mock_llm.model = "test-model"
        mock_llm.token_limit = 1000
        mock_llm.compatibility = "openai"
        mock_llm.get_name = Mock(return_value="test_llm")
        from linhai.llm_manager import LlmManager

        mock_llm_manager = Mock(spec=LlmManager)
        mock_llm = Mock()
        mock_llm.get_name = Mock(return_value="test_llm")
        mock_llm_manager.llms = [mock_llm]
        mock_llm_manager.llm_names = ["test_llm"]
        mock_llm_manager.current_llm_index = 0
        mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)
        mock_llm_instances.return_value = mock_llm_manager

        mock_tool_manager.return_value = (Mock(), Mock())
        mock_pinned_messages.return_value = [Mock()]
        mock_multimodal_toolset_manager.return_value = Mock()
        mock_register_conversation_folder.return_value = None
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance
        mock_agent_instance.llm_manager = mock_llm_manager

        import asyncio
        import argparse

        cli_args = argparse.Namespace(
            message=None,
            file=None,
            claw=False,
            claw_folder=None,
            disable_waiting_marker=False,
            rss=[],
            telegram=False,
            afk=False,
        )

        context = create_agent_build_context(
            registry=Mock(),
            config=mock_config,
            config_basedir=Path("."),
            llm_name="test_llm",
            cli_args=cli_args,
            checklist_path=None,
        )
        result = asyncio.run(create_agent_from_context(context))

        self.assertIsNotNone(result)

    @patch("linhai.agent.create._create_llm_instances")
    @patch("linhai.agent.create._create_tool_manager")
    @patch("linhai.agent.create._create_pinned_messages")
    @patch("linhai.multimodal.MultimodalToolsetManager")
    @patch("linhai.agent.conversation.register_conversation_folder")
    @patch("linhai.agent.main.Agent")
    def test_default_uses_all_toolsets(
        self,
        mock_agent,
        mock_register_conversation_folder,
        mock_multimodal_toolset_manager,
        mock_pinned_messages,
        mock_tool_manager,
        mock_llm_instances,
    ):
        mock_config = Mock()
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

        mock_config.llm = [mock_llm_config]
        mock_config.agent = [Mock()]
        mock_config.agent[0].enable_toolsets = None
        mock_config.agent[0].disable_toolsets = None
        mock_config.agent[0].process_sandbox = None
        mock_config.tools = Mock()
        mock_config.tools.enable_toolsets = None
        mock_config.tools.disable_toolsets = None
        mock_config.tools.secret.config_path = ""
        mock_config.user_prompt = Mock()()()
        mock_config.user_prompt.file_path = "prompt.md"
        mock_config.subagent = Mock()
        mock_config.tui = Mock()

        from linhai.llm import OpenAi

        mock_llm = Mock(spec=OpenAi)
        mock_llm.model = "test-model"
        mock_llm.token_limit = 1000
        mock_llm.compatibility = "openai"
        mock_llm.get_name = Mock(return_value="test_llm")
        from linhai.llm_manager import LlmManager

        mock_llm_manager = Mock(spec=LlmManager)
        mock_llm = Mock()
        mock_llm.get_name = Mock(return_value="test_llm")
        mock_llm_manager.llms = [mock_llm]
        mock_llm_manager.llm_names = ["test_llm"]
        mock_llm_manager.current_llm_index = 0
        mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)
        mock_llm_instances.return_value = mock_llm_manager

        mock_tool_manager.return_value = (Mock(), Mock())
        mock_pinned_messages.return_value = [Mock()]
        mock_multimodal_toolset_manager.return_value = Mock()
        mock_register_conversation_folder.return_value = None
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance
        mock_agent_instance.llm_manager = mock_llm_manager

        import asyncio
        import argparse

        cli_args = argparse.Namespace(
            message=None,
            file=None,
            claw=False,
            claw_folder=None,
            disable_waiting_marker=False,
            rss=[],
            telegram=False,
            afk=False,
        )

        context = create_agent_build_context(
            registry=Mock(),
            config=mock_config,
            config_basedir=Path("."),
            llm_name="test_llm",
            cli_args=cli_args,
            checklist_path=None,
        )
        result = asyncio.run(create_agent_from_context(context))

        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
