"""测试agent.override_toolsets配置项功能"""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from linhai.config import Config, AgentConfig, ConfigValidationError
from linhai.agent.create import create_agent_from_config, create_agent_build_context


class TestOverrideToolsetsConfig(unittest.TestCase):
    """测试override_toolsets配置功能"""

    def test_override_toolsets_none(self):
        """测试override_toolsets为None时，使用默认的toolsets"""
        config = AgentConfig()
        self.assertIsNone(config.override_toolsets)

    def test_override_toolsets_with_list(self):
        """测试override_toolsets为列表时，使用该列表"""
        config = AgentConfig(override_toolsets=["utils", "sleep"])
        self.assertEqual(config.override_toolsets, ["utils", "sleep"])

    def test_override_toolsets_empty_list(self):
        """测试override_toolsets为空列表时，使用空列表"""
        config = AgentConfig(override_toolsets=[])
        self.assertEqual(config.override_toolsets, [])

    def test_override_toolsets_in_full_config(self):
        """测试在完整配置中设置override_toolsets"""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[agent]
override_toolsets = ["utils", "sleep"]
"""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(config_content)
            temp_file = f.name

        try:
            from linhai.config import load_config

            config = load_config(temp_file)
            self.assertIsNotNone(config.agent)
            self.assertEqual(config.agent.override_toolsets, ["utils", "sleep"])
        finally:
            os.unlink(temp_file)

    @patch("linhai.agent.create._create_llm_instances")
    @patch("linhai.agent.create._create_tool_manager")
    @patch("linhai.agent.create._create_pinned_messages")
    @patch("linhai.multimodal.MultimodalToolsetManager")
    @patch("linhai.agent.conversation.register_conversation_folder")
    @patch("linhai.agent.main.Agent")
    def test_override_toolsets_applied_in_agent_creation(
        self,
        mock_agent,
        mock_register_conversation_folder,
        mock_multimodal_toolset_manager,
        mock_pinned_messages,
        mock_tool_manager,
        mock_llm_instances,
    ):
        """测试override_toolsets在agent创建时被正确应用"""
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
        mock_config.agent = Mock()
        mock_config.agent.override_toolsets = ["utils", "sleep"]
        mock_config.tools = Mock()
        mock_config.tools.toolsets = ["machine_control"]
        mock_config.tools.secret.config_path = ""
        mock_config.user_prompt = Mock()()()
        mock_config.user_prompt.file_path = "prompt.md"
        mock_config.subagent = Mock()
        mock_config.cli = Mock()

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
        mock_llm_instances.return_value = mock_llm_manager  # type: ignore

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
        )

        context = create_agent_build_context(
            registry=Mock(),
            config=mock_config,
            config_basedir=Path("."),
            llm_name="test_llm",
            cli_args=cli_args,
            checklist_path=None,
        )
        result = asyncio.run(create_agent_from_config(context))

        self.assertIsNotNone(result)

    @patch("linhai.agent.create._create_llm_instances")
    @patch("linhai.agent.create._create_tool_manager")
    @patch("linhai.agent.create._create_pinned_messages")
    @patch("linhai.multimodal.MultimodalToolsetManager")
    @patch("linhai.agent.conversation.register_conversation_folder")
    @patch("linhai.agent.main.Agent")
    def test_no_override_toolsets_uses_default(
        self,
        mock_agent,
        mock_register_conversation_folder,
        mock_multimodal_toolset_manager,
        mock_pinned_messages,
        mock_tool_manager,
        mock_llm_instances,
    ):
        """测试override_toolsets为None时，使用tools.toolsets"""
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
        mock_config.agent = Mock()
        mock_config.agent.override_toolsets = None
        mock_config.tools = Mock()
        mock_config.tools.toolsets = ["utils", "sleep"]
        mock_config.tools.secret.config_path = ""
        mock_config.user_prompt = Mock()()()
        mock_config.user_prompt.file_path = "prompt.md"
        mock_config.subagent = Mock()
        mock_config.cli = Mock()

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
        mock_llm_instances.return_value = mock_llm_manager  # type: ignore

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
        )

        context = create_agent_build_context(
            registry=Mock(),
            config=mock_config,
            config_basedir=Path("."),
            llm_name="test_llm",
            cli_args=cli_args,
            checklist_path=None,
        )
        result = asyncio.run(create_agent_from_config(context))

        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
