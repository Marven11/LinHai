"""测试create_agent函数中的MCP配置功能"""

import unittest
import sys
import os
import tempfile
import asyncio
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linhai.registry import Registry
from linhai.agent.create import create_agent_from_context
from linhai.agent import Agent
from linhai.config import load_config, AVAILABLE_TOOLSETS


class TestCreateAgentMCP(unittest.TestCase):
    """测试create_agent函数中的MCP配置功能"""

    def setUp(self):
        """设置测试fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = Registry()
        import argparse

        self.cli_args = argparse.Namespace()
        self.cli_args.checklist = None

        self.cli_args.message = []
        self.cli_args.file = []
        self.cli_args.claw = False
        self.cli_args.claw_folder = None
        self.cli_args.disable_waiting_marker = False
        self.cli_args.afk = False
        self.cli_args.rss = []
        self.cli_args.telegram = False
        self.registry.register_member("cli_args", self.cli_args)

        project_root = os.path.dirname(os.path.abspath(__file__))
        source_file = os.path.join(project_root, "real_mcp_server.py")
        dest_file = os.path.join(self.temp_dir, "real_mcp_server.py")
        import shutil

        shutil.copy2(source_file, dest_file)
        os.chmod(dest_file, 0o755)

    def tearDown(self):
        """清理测试fixtures"""
        import shutil

        shutil.rmtree(self.temp_dir)

    def create_test_config(self, config_content):
        """创建临时配置文件"""
        config_path = Path(self.temp_dir) / "test_config.toml"
        config_path.write_text(config_content, encoding="utf-8")
        return config_path

    def test_create_agent_with_real_mcp_server(self):
        """测试create_agent函数与真实MCP服务器的集成"""
        server_script_path = os.path.join(self.temp_dir, "real_mcp_server.py")
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
server_script_path = "{server_script_path}"
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
            "enabled_toolsets": list(AVAILABLE_TOOLSETS),
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
        result = asyncio.run(create_agent_from_context(context))

        self.assertIsInstance(result, Agent)

        self.assertIsInstance(result, Agent)

        self.assertIsInstance(result, Agent)

    def test_create_agent_without_mcp_config(self):
        """测试没有MCP配置时create_agent函数正常工作"""
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
            "enabled_toolsets": list(AVAILABLE_TOOLSETS),
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
        result = asyncio.run(create_agent_from_context(context))

        self.assertIsInstance(result, Agent)

        agent = self.registry.get_member_typechecked("agent", Agent)
        self.assertIsNotNone(agent)


if __name__ == "__main__":
    unittest.main()
