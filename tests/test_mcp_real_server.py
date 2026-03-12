"""Unit tests for MCP with real server integration."""

import tempfile
import unittest
from pathlib import Path

from linhai.agent.create import create_agent_from_config
from linhai.agent import Agent
from linhai.config import load_config
from linhai.group_chat import GroupChat


class TestMCPRealServer(unittest.IsolatedAsyncioTestCase):
    """Test MCP integration with real servers."""

    def setUp(self):
        """Set up test fixtures."""
        import argparse

        self.temp_dir = tempfile.mkdtemp()
        self.group_chat = GroupChat()
        # Register cli_args required by create_agent_from_config
        cli_args = argparse.Namespace()

        cli_args.checklist = False
        cli_args.message = []
        cli_args.file = []
        cli_args.claw = False
        cli_args.disable_waiting_marker = False
        self.group_chat.register_member("cli_args", cli_args)
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
        project_root = Path(__file__).parent.parent.parent
        server_path = project_root / "linhai" / "tests" / "real_mcp_server.py"

        config_content = f"""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[agent]
compress_threshold = 80000

[[agent.mcp]]
name = "calculator"
server_script_path = "{server_path}"
"""
        config_path = self.create_test_config(config_content)

        config = load_config(config_path)
        from pathlib import Path

        context = {
            "group_chat": self.group_chat,
            "config": config,
            "config_basedir": Path("."),
            "llm_name": None,
            "max_toolcall_token_in_round": 30000,
            "checklist_path": None,
            "cli_args": self.cli_args,
        }
        agent = await create_agent_from_config(context)
        self.assertIsInstance(agent, Agent)
