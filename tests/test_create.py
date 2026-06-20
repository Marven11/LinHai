"""测试Agent创建模块 - LLM实例创建和DefaultLlmConfig"""

import asyncio
import unittest

from pathlib import Path
from unittest.mock import Mock, patch

from linhai.agent.create import (
    _create_llm_instances,
    create_agent_build_context,
    AgentBuildArguments,
)
from linhai.config import AVAILABLE_TOOLSETS
from linhai.llm_manager import LlmManager


class TestCreateLLMInstances(unittest.TestCase):

    def test_create_llm_instances(self):
        llm_configs = [
            Mock(
                api_key="test_key",
                base_url="http://test.com",
                model="test-model",
                client_options={},
                completion_options={"temperature": 0.7},
                token_limit=1000,
                compatibility="openai",
                name="test-llm",
                compress_threshold=None,
                support_image=False,
                native_toolcall_format=None,
                fallback=None,
                fallback_duration=120,
                explicit_cache=None,
                type="openai",
            )
        ]

        mock_registry = Mock()
        mock_config = Mock()
        mock_config.agent = [Mock()]
        mock_config.agent[0].mcp = []
        mock_config.tools = Mock()
        mock_config.agent[0].secret = Mock()
        mock_config.agent[0].secret.config_path = None
        context = {
            "registry": mock_registry,
            "llms": llm_configs,
            "llm_name": "test-llm",
            "config_basedir": Path("."),
            "user_prompt": None,
            "max_toolcall_token_in_round": 0.3,
            "planning": False,
            "enabled_toolsets": list(AVAILABLE_TOOLSETS),
            "compress_threshold": 0.8,
            "max_toolcall_for_llm": {},
            "allowed_commands": [],
            "telegram_config": None,
            "mcp_configs": mock_config.agent[0].mcp,
            "tool_config": mock_config.tools,
            "secret_config_path": mock_config.agent[0].secret.config_path,
            "message": [],
            "file": [],
        }

        from linhai.llm import OpenAi

        mock_llm = Mock(spec=OpenAi)
        mock_llm.model = "test-model"
        mock_llm.token_limit = 1000
        mock_llm.compatibility = "openai"
        mock_llm.get_name = Mock(return_value="test-llm")

        from unittest.mock import AsyncMock

        with patch(
            "linhai.agent.create._create_llm_instances", new_callable=AsyncMock
        ) as mock_create_llm:
            llm_manager = LlmManager(
                registry=mock_registry,
                llms=[mock_llm],
                default_llm_name="test-llm",
                llm_fallback_map={"test-llm": None},
                llm_fallback_duration_map={"test-llm": 120},
            )
            mock_create_llm.return_value = llm_manager

            import linhai.agent.create as create_module

            result = asyncio.run(create_module._create_llm_instances(context))

            self.assertIsInstance(result, LlmManager)
            self.assertEqual(len(result.llms), 1)
            llm = result.llms[0]
            self.assertEqual(llm.get_name(), "test-llm")
            self.assertEqual(llm.model, "test-model")
            self.assertEqual(llm.token_limit, 1000)
            self.assertEqual(llm.compatibility, "openai")


class TestDefaultLlmConfig(unittest.TestCase):

    def setUp(self):
        self.registry = Mock()

    def _create_mock_llm_config(self, name):
        mock_llm_config = Mock()
        mock_llm_config.name = name
        mock_llm_config.base_url = f"http://{name}.com"
        mock_llm_config.api_key = f"test_key_{name}"
        mock_llm_config.model = f"test-model-{name}"
        mock_llm_config.model_dump.return_value = {
            "client_options": {},
            "completion_options": {},
            "token_limit": 1000,
            "compatibility": "openai",
        }
        return mock_llm_config

    def _create_mock_config(self, llm_configs, default_llm=None):
        mock_config = Mock()
        mock_config.llm = llm_configs
        mock_config.agent = [Mock()]
        mock_config.agent[0].enable_toolsets = None
        mock_config.agent[0].disable_toolsets = None
        mock_config.agent[0].default_llm = default_llm
        mock_config.agent[0].process_sandbox = None
        mock_config.agent[0].planning = False
        mock_config.agent[0].claw = False
        mock_config.tools = Mock()
        mock_config.tools.enable_toolsets = None
        mock_config.tools.disable_toolsets = None
        mock_config.agent[0].secret.config_path = ""
        mock_config.user_prompt = Mock()()()
        mock_config.user_prompt.file_path = "prompt.md"
        mock_config.subagent = Mock()
        mock_config.tui = Mock()
        mock_config.remote_control = Mock()
        mock_config.remote_control.telegram = None
        mock_config.claw = Mock()
        return mock_config

    def test_default_llm_not_set_uses_first(self):
        mock_llm_config1 = self._create_mock_llm_config("llm1")
        mock_llm_config2 = self._create_mock_llm_config("llm2")
        mock_config = self._create_mock_config(
            [mock_llm_config1, mock_llm_config2], default_llm=None
        )

        build_args: AgentBuildArguments = {
            "cron": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "claw_enabled": False,
            "claw_folder": None,
            "message": [],
            "file": [],
            "planning": False,
            "llm_name": None,
            "profile_name": None,
            "git_worktree": False,
        }

        context = create_agent_build_context(
            registry=self.registry,
            config=mock_config,
            config_basedir=Path("."),
            build_args=build_args,
        )
        self.assertEqual(context["llm_name"], "llm1")

    def test_default_llm_set_uses_configured(self):
        mock_llm_config1 = self._create_mock_llm_config("llm1")
        mock_llm_config2 = self._create_mock_llm_config("llm2")
        mock_config = self._create_mock_config(
            [mock_llm_config1, mock_llm_config2], default_llm="llm2"
        )

        build_args: AgentBuildArguments = {
            "cron": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "claw_enabled": False,
            "claw_folder": None,
            "message": [],
            "file": [],
            "planning": False,
            "llm_name": None,
            "profile_name": None,
            "git_worktree": False,
        }

        context = create_agent_build_context(
            registry=self.registry,
            config=mock_config,
            config_basedir=Path("."),
            build_args=build_args,
        )
        self.assertEqual(context["llm_name"], "llm2")

    def test_default_llm_invalid_raises(self):
        mock_llm_config1 = self._create_mock_llm_config("llm1")
        mock_llm_config2 = self._create_mock_llm_config("llm2")
        mock_config = self._create_mock_config(
            [mock_llm_config1, mock_llm_config2], default_llm="invalid_llm"
        )

        build_args: AgentBuildArguments = {
            "cron": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "claw_enabled": False,
            "claw_folder": None,
            "message": [],
            "file": [],
            "planning": False,
            "llm_name": None,
            "profile_name": None,
            "git_worktree": False,
        }

        with self.assertRaises(ValueError) as ctx:
            create_agent_build_context(
                registry=self.registry,
                config=mock_config,
                config_basedir=Path("."),
                build_args=build_args,
            )
        self.assertIn("agent.default_llm", str(ctx.exception))

    def test_cli_llm_overrides_default(self):
        mock_llm_config1 = self._create_mock_llm_config("llm1")
        mock_llm_config2 = self._create_mock_llm_config("llm2")
        mock_config = self._create_mock_config(
            [mock_llm_config1, mock_llm_config2], default_llm="llm1"
        )

        build_args: AgentBuildArguments = {
            "cron": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "claw_enabled": False,
            "claw_folder": None,
            "message": [],
            "file": [],
            "planning": False,
            "llm_name": "llm2",
            "profile_name": None,
            "git_worktree": False,
        }

        context = create_agent_build_context(
            registry=self.registry,
            config=mock_config,
            config_basedir=Path("."),
            build_args=build_args,
        )
        self.assertEqual(context["llm_name"], "llm2")


if __name__ == "__main__":
    unittest.main()
