"""Unit tests for MCP configuration and path conversion."""

import os
import tempfile
import unittest
from pathlib import Path

from linhai.config import load_config, ConfigValidationError


class TestMCPConfig(unittest.TestCase):
    """Test cases for MCP configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def create_test_config(self, config_content):
        """Create a temporary config file with given content."""
        config_path = Path(self.temp_dir) / "test_config.toml"
        config_path.write_text(config_content, encoding="utf-8")
        return config_path

    def test_mcp_config_command_stored_as_is(self):
        """测试command字段原样存储。"""
        config_content = """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[[agent]]
compress_threshold = 80000

[[agent.mcp]]
name = "calculator"
command = "python mcp_server_example.py"

[[agent.mcp]]
name = "another_server"
command = "uv run ../another_server.py"
"""
        config_path = self.create_test_config(config_content)

        config = load_config(config_path)

        assert config.agent is not None
        agent = config.agent[0]
        self.assertEqual(len(agent.mcp), 2)
        self.assertEqual(agent.mcp[0].command, "python mcp_server_example.py")
        self.assertEqual(agent.mcp[1].command, "uv run ../another_server.py")

    def test_mcp_config_absolute_path_unchanged(self):
        """测试绝对路径保持不变。"""
        config_content = """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[[agent]]
compress_threshold = 80000

[[agent.mcp]]
name = "absolute_server"
command = "uv run /usr/local/bin/mcp_server"
"""
        config_path = self.create_test_config(config_content)

        config = load_config(config_path)

        assert config.agent is not None
        agent = config.agent[0]
        self.assertEqual(len(agent.mcp), 1)
        self.assertEqual(agent.mcp[0].command, "uv run /usr/local/bin/mcp_server")

    def test_mcp_config_no_mcp_servers(self):
        """测试没有MCP服务器配置的情况。"""
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

        assert config.agent is not None
        agent = config.agent[0]
        self.assertEqual(len(agent.mcp), 0)

    def test_mcp_config_invalid_name(self):
        """测试无效的MCP服务器名称。"""
        config_content = """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[[agent]]
compress_threshold = 80000

[[agent.mcp]]
name = "invalid name!"
command = "python server.py"
"""
        config_path = self.create_test_config(config_content)

        with self.assertRaises(ConfigValidationError):
            load_config(config_path)

    def test_mcp_config_missing_agent_section(self):
        """测试没有agent部分的情况。"""
        config_content = """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"
"""
        config_path = self.create_test_config(config_content)

        config = load_config(config_path)

        self.assertIsNotNone(config.agent)  # 现在有默认值
        self.assertEqual(config.agent, [])


if __name__ == "__main__":
    unittest.main()
