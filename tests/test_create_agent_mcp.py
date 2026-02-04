"""测试create_agent函数中的MCP配置功能"""

import unittest
import sys
import os
import tempfile
import asyncio
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linhai.group_chat import GroupChat
from linhai.agent.create import create_agent_from_config
from linhai.agent import Agent
from linhai.config import load_config


class TestCreateAgentMCP(unittest.TestCase):
    """测试create_agent函数中的MCP配置功能"""

    def setUp(self):
        """设置测试fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.group_chat = GroupChat()
        import argparse

        self.cli_args = argparse.Namespace()
        self.cli_args.checklist = None

        self.cli_args.message = []
        self.cli_args.file = []
        self.group_chat.register_member("cli_args", self.cli_args)

        project_root = os.path.dirname(os.path.abspath(__file__))
        source_file = os.path.join(project_root, "real_mcp_server.py")
        dest_file = os.path.join(self.temp_dir, "real_mcp_server.py")
        import shutil

        shutil.copy2(source_file, dest_file)

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

[agent]
compress_threshold = 80000

[[agent.mcp]]
name = "calculator"
server_script_path = "{server_script_path}"
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
        result = asyncio.run(create_agent_from_config(context))

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

[agent]
compress_threshold = 80000
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
        result = asyncio.run(create_agent_from_config(context))

        self.assertIsInstance(result, Agent)

        agent = self.group_chat.get_members("agent", Agent)
        self.assertIsNotNone(agent)


if __name__ == "__main__":
    unittest.main()
