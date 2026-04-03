"""Unit tests for MCP with real server integration."""

import tempfile
import unittest
from pathlib import Path

from linhai.agent.create import create_agent_from_context
from linhai.agent import Agent
from linhai.config import load_config
from linhai.registry import Registry


class TestMCPRealServer(unittest.IsolatedAsyncioTestCase):
    """Test MCP integration with real servers."""

    def setUp(self):
        """Set up test fixtures."""
        import argparse

        self.temp_dir = tempfile.mkdtemp()
        self.registry = Registry()
        # Register cli_args required by create_agent_from_context
        cli_args = argparse.Namespace(afk=False)

        cli_args.checklist = False
        cli_args.message = []
        cli_args.file = []
        cli_args.claw = False
        cli_args.claw_folder = None
        cli_args.disable_waiting_marker = False
        cli_args.afk = False
        cli_args.rss = []
        cli_args.telegram = False
        self.registry.register_member("cli_args", cli_args)
        self.cli_args = cli_args

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def create_test_config(self, config_content):
        """Create a temporary config file with given content."""
        config_path = Path(self.temp_dir) / "test_config.toml"
        config_path.write_text(config_content, encoding="utf-8")
        return config_path

    async def test_mcp_real_server_integration(self):
        from pathlib import Path

        """Test full integration with real MCP server."""
        project_root = Path(__file__).parent.parent
        server_path = project_root / "tests" / "real_mcp_server.py"

        config_content = f"""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[[agent]]
compress_threshold = 80000

[[agent.mcp]]
name = "calculator"
server_script_path = "{server_path}"
"""
        config_path = self.create_test_config(config_content)

        config = load_config(config_path)
        from pathlib import Path

        context = {
            "registry": self.registry,
            "config_basedir": Path("."),
            "llms": config.llm,
            "llm_name": None,
            "max_toolcall_token_in_round": 30000,
            "checklist_path": None,
            "user_prompt": None,
            "planning": False,
            "toolsets_config": config.tools.toolsets,
            "override_toolsets": config.agent[0].override_toolsets,
            "compress_threshold": config.agent[0].compress_threshold,
            "enable_directory_change_detection": config.agent[
                0
            ].enable_directory_change_detection,
            "max_toolcall_for_llm": config.agent[0].max_toolcall_for_llm,
            "allowed_commands": config.agent[0].allowed_commands,
            "telegram_config": None,
            "mcp_configs": config.agent[0].mcp,
            "tool_config": config.tools,
            "secret_config_path": (
                config.tools.secret.config_path if config.tools.secret else None
            ),
            "rss": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "claw_enabled": False,
            "claw_folder": None,
            "message": [],
            "file": [],
            "process_sandbox": None,
        }
        agent = await create_agent_from_context(context)
        self.assertIsInstance(agent, Agent)
