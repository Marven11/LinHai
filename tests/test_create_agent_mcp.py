"""测试create_agent函数中MCP配置的行为"""

import unittest
import sys
import os
import tempfile
import asyncio
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linhai.registry import Registry
from linhai.agent.create import (
    create_agent_from_context,
    create_agent_build_context,
    AgentBuildArguments,
)
from linhai.agent import Agent
from linhai.config import load_config


class TestCreateAgentMCP(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.registry = Registry()
        import argparse

        self.cli_args = argparse.Namespace()
        self.cli_args.message = []
        self.cli_args.file = []
        self.cli_args.claw = False
        self.cli_args.claw_folder = None
        self.cli_args.disable_waiting_marker = False
        self.cli_args.afk = False
        self.cli_args.rss = []
        self.cli_args.telegram = False
        self.registry.register_member("cli_args", self.cli_args)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def create_test_config(self, config_content):
        config_path = Path(self.temp_dir) / "test_config.toml"
        config_path.write_text(config_content, encoding="utf-8")
        return config_path

    def test_create_agent_with_real_mcp_server(self):
        project_root = os.path.dirname(os.path.abspath(__file__))
        server_script_path = os.path.join(project_root, "real_mcp_server.py")
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
command = "python {server_script_path}"
"""
        config_path = self.create_test_config(config_content)

        config = load_config(config_path)
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
        }
        context = create_agent_build_context(
            registry=self.registry,
            config=config,
            config_basedir=Path("."),
            build_args=build_args,
        )
        result = asyncio.run(create_agent_from_context(context))
        self.assertIsInstance(result, Agent)

        agent = self.registry.get_member_typechecked("agent", Agent)
        self.assertIsNotNone(agent)
        self.assertTrue(self.registry.has_member("mcp_connector"))

    def test_create_agent_without_mcp_config(self):
        config_content = """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[[agent]]
compress_threshold = 80000
"""
        config_path = self.create_test_config(config_content)

        config = load_config(config_path)
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
        }
        context = create_agent_build_context(
            registry=self.registry,
            config=config,
            config_basedir=Path("."),
            build_args=build_args,
        )
        result = asyncio.run(create_agent_from_context(context))
        self.assertIsInstance(result, Agent)

        agent = self.registry.get_member_typechecked("agent", Agent)
        self.assertIsNotNone(agent)

    def test_create_agent_with_multiple_mcp_servers(self):
        project_root = os.path.dirname(os.path.abspath(__file__))
        server_script = os.path.join(project_root, "real_mcp_server.py")
        config_content = f"""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[[agent]]
compress_threshold = 80000

[[agent.mcp]]
name = "calc1"
command = "python {server_script}"

[[agent.mcp]]
name = "calc2"
command = "python {server_script}"
"""
        config_path = self.create_test_config(config_content)

        config = load_config(config_path)
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
        }
        context = create_agent_build_context(
            registry=self.registry,
            config=config,
            config_basedir=Path("."),
            build_args=build_args,
        )
        result = asyncio.run(create_agent_from_context(context))
        self.assertIsInstance(result, Agent)

        self.assertTrue(self.registry.has_member("mcp_connector"))


if __name__ == "__main__":
    unittest.main()
