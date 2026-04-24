"""测试AgentBuildContext中rss/telegram/disable_waiting_marker/afk的传递"""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from linhai.agent.create import (
    create_agent_build_context,
    _resolve_process_sandbox,
    AgentBuildArguments,
)
from linhai.config import (
    BubblewrapConfig,
    MacOsSandboxConfig,
    ProcessSandboxConfig,
)
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
        self.config.agent = [Mock()]
        self.config.agent[0].default_llm = "test_llm"
        self.config.agent[0].enable_toolsets = None
        self.config.agent[0].disable_toolsets = None
        self.config.agent[0].compress_threshold = 0.8
        self.config.agent[0].max_toolcall_for_llm = {}
        self.config.agent[0].allowed_commands = []
        self.config.agent[0].mcp = []
        self.config.tools = Mock()
        self.config.tools.enable_toolsets = None
        self.config.tools.disable_toolsets = None
        self.config.tools.max_toolcall_token_in_round = 0.3
        self.config.agent[0].secret = Mock()
        self.config.agent[0].secret.config_path = None
        self.config.user_prompt = None
        self.config.remote_control = Mock()
        self.config.remote_control.telegram = None
        self.config.agent[0].process_sandbox = None
        self.config.agent[0].planning = False
        self.config.agent[0].claw = False

    def test_agent_build_context_with_rss(self):
        """测试rss参数从build_args传递到AgentBuildContext"""
        build_args: AgentBuildArguments = {
            "rss": ["http://example.com/rss1", "http://example.com/rss2"],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "message": [],
            "file": [],
            "claw_enabled": False,
            "claw_folder": None,
            "planning": False,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": None,
        }

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            build_args=build_args,
        )

        self.assertEqual(
            context["rss"], ["http://example.com/rss1", "http://example.com/rss2"]
        )
        self.assertEqual(context["afk"], False)
        self.assertEqual(context["claw_enabled"], False)
        self.assertEqual(context["claw_folder"], None)
        self.assertIsNone(context["process_sandbox"])

    def test_agent_build_context_with_telegram(self):
        """测试telegram参数从build_args传递到AgentBuildContext"""
        build_args: AgentBuildArguments = {
            "rss": [],
            "telegram": True,
            "disable_waiting_marker": False,
            "afk": False,
            "message": [],
            "file": [],
            "claw_enabled": False,
            "claw_folder": None,
            "planning": False,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": None,
        }

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            build_args=build_args,
        )

        self.assertEqual(context["telegram"], True)
        self.assertEqual(context["claw_enabled"], False)
        self.assertEqual(context["claw_folder"], None)
        self.assertIsNone(context["process_sandbox"])

    def test_agent_build_context_with_disable_waiting_marker(self):
        """测试disable_waiting_marker参数从build_args传递到AgentBuildContext"""
        build_args: AgentBuildArguments = {
            "rss": [],
            "telegram": False,
            "disable_waiting_marker": True,
            "afk": False,
            "message": [],
            "file": [],
            "claw_enabled": False,
            "claw_folder": None,
            "planning": False,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": None,
        }

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            build_args=build_args,
        )

        self.assertEqual(context["disable_waiting_marker"], True)
        self.assertEqual(context["claw_enabled"], False)
        self.assertEqual(context["claw_folder"], None)

    def test_agent_build_context_with_afk(self):
        """测试afk参数从build_args传递到AgentBuildContext"""
        build_args: AgentBuildArguments = {
            "rss": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": True,
            "message": [],
            "file": [],
            "claw_enabled": False,
            "claw_folder": None,
            "planning": False,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": None,
        }

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            build_args=build_args,
        )

        self.assertEqual(context["afk"], True)

    def test_agent_build_context_with_all_parameters(self):
        """测试所有参数同时传递"""
        build_args: AgentBuildArguments = {
            "rss": ["http://example.com/rss"],
            "telegram": True,
            "disable_waiting_marker": True,
            "afk": True,
            "message": [],
            "file": [],
            "claw_enabled": True,
            "claw_folder": Path("/custom/claw/path"),
            "planning": False,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": None,
        }

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            build_args=build_args,
        )

        self.assertEqual(context["rss"], ["http://example.com/rss"])
        self.assertEqual(context["telegram"], True)
        self.assertEqual(context["disable_waiting_marker"], True)
        self.assertEqual(context["afk"], True)
        self.assertEqual(context["claw_enabled"], True)
        self.assertEqual(context["claw_folder"], Path("/custom/claw/path"))

    def test_agent_build_context_with_default_values(self):
        """测试默认值"""
        build_args: AgentBuildArguments = {
            "rss": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "message": [],
            "file": [],
            "claw_enabled": False,
            "claw_folder": None,
            "planning": False,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": None,
        }

        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            build_args=build_args,
        )

        self.assertEqual(context["rss"], [])
        self.assertEqual(context["telegram"], False)
        self.assertEqual(context["disable_waiting_marker"], False)
        self.assertEqual(context["afk"], False)
        self.assertEqual(context["claw_enabled"], False)
        self.assertEqual(context["claw_folder"], None)

    def test_profile_planning_enables_when_cli_false(self):
        """测试profile中planning=True在CLI未传--planning时生效"""
        self.config.agent[0].planning = True
        build_args: AgentBuildArguments = {
            "rss": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "message": [],
            "file": [],
            "claw_enabled": False,
            "claw_folder": None,
            "planning": False,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": None,
        }
        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            build_args=build_args,
        )
        self.assertEqual(context["planning"], True)

    def test_profile_claw_enables_when_cli_false(self):
        """测试profile中claw=True在CLI未传--claw时生效"""
        self.config.agent[0].claw = True
        build_args: AgentBuildArguments = {
            "rss": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "message": [],
            "file": [],
            "claw_enabled": False,
            "claw_folder": None,
            "planning": False,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": None,
        }
        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            build_args=build_args,
        )
        self.assertEqual(context["claw_enabled"], True)

    def test_cli_planning_overrides_profile_false(self):
        """测试CLI --planning覆盖profile中planning=False"""
        build_args: AgentBuildArguments = {
            "rss": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "message": [],
            "file": [],
            "claw_enabled": False,
            "claw_folder": None,
            "planning": True,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": None,
        }
        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            build_args=build_args,
        )
        self.assertEqual(context["planning"], True)

    def test_both_cli_and_profile_enabled(self):
        """测试CLI和profile同时启用时结果为True"""
        self.config.agent[0].planning = True
        self.config.agent[0].claw = True
        build_args: AgentBuildArguments = {
            "rss": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "message": [],
            "file": [],
            "claw_enabled": True,
            "claw_folder": Path("/custom/claw"),
            "planning": True,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": None,
        }
        context = create_agent_build_context(
            registry=self.registry,
            config=self.config,
            config_basedir=Path("."),
            build_args=build_args,
        )
        self.assertEqual(context["planning"], True)
        self.assertEqual(context["claw_enabled"], True)


class TestResolveProcessSandbox(unittest.TestCase):
    """测试_resolve_process_sandbox平台选择逻辑"""

    def test_none_input_returns_none(self):
        result = _resolve_process_sandbox(None)
        self.assertIsNone(result)

    @patch("linhai.agent.create.platform.system", return_value="Darwin")
    def test_macos_platform_selects_macos_sandbox(self, mock_system):
        macos_config = MacOsSandboxConfig(sandbox_profile="sandbox.sb")
        bubblewrap_config = BubblewrapConfig(argv_template=["bwrap"])
        sandbox = ProcessSandboxConfig(
            macos_sandbox=macos_config, bubblewrap=bubblewrap_config
        )
        result = _resolve_process_sandbox(sandbox)
        self.assertIsInstance(result, MacOsSandboxConfig)
        self.assertEqual(result.sandbox_profile, "sandbox.sb")

    @patch("linhai.agent.create.platform.system", return_value="Linux")
    def test_linux_platform_selects_bubblewrap(self, mock_system):
        macos_config = MacOsSandboxConfig(sandbox_profile="sandbox.sb")
        bubblewrap_config = BubblewrapConfig(argv_template=["bwrap"])
        sandbox = ProcessSandboxConfig(
            macos_sandbox=macos_config, bubblewrap=bubblewrap_config
        )
        result = _resolve_process_sandbox(sandbox)
        self.assertIsInstance(result, BubblewrapConfig)
        self.assertEqual(result.argv_template, ["bwrap"])

    @patch("linhai.agent.create.platform.system", return_value="Darwin")
    def test_macos_platform_returns_none_when_no_macos_config(self, mock_system):
        sandbox = ProcessSandboxConfig(
            macos_sandbox=None, bubblewrap=BubblewrapConfig(argv_template=["bwrap"])
        )
        result = _resolve_process_sandbox(sandbox)
        self.assertIsNone(result)

    @patch("linhai.agent.create.platform.system", return_value="Linux")
    def test_linux_platform_returns_none_when_no_bubblewrap_config(self, mock_system):
        sandbox = ProcessSandboxConfig(
            macos_sandbox=MacOsSandboxConfig(sandbox_profile="sandbox.sb"),
            bubblewrap=None,
        )
        result = _resolve_process_sandbox(sandbox)
        self.assertIsNone(result)

    @patch("linhai.agent.create.platform.system", return_value="Windows")
    def test_unknown_platform_returns_none(self, mock_system):
        sandbox = ProcessSandboxConfig(
            macos_sandbox=MacOsSandboxConfig(sandbox_profile="sandbox.sb"),
            bubblewrap=BubblewrapConfig(argv_template=["bwrap"]),
        )
        result = _resolve_process_sandbox(sandbox)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
