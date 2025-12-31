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

    def test_mcp_config_relative_path_conversion(self):
        """测试相对路径转换为绝对路径。"""
        config_content = """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[agent]
compress_threshold = 80000

[[agent.mcp]]
name = "calculator"
server_script_path = "mcp_server_example.py"

[[agent.mcp]]
name = "another_server"
server_script_path = "../another_server.py"
"""
        config_path = self.create_test_config(config_content)

        config = load_config(config_path)

        assert config.agent is not None
        agent = config.agent
        self.assertEqual(len(agent.mcp), 2)

        calculator_path = agent.mcp[0].server_script_path
        self.assertTrue(os.path.isabs(calculator_path))
        self.assertEqual(
            calculator_path, str(config_path.parent / "mcp_server_example.py")
        )

        another_path = agent.mcp[1].server_script_path
        self.assertTrue(os.path.isabs(another_path))
        expected_path = os.path.normpath(
            str(config_path.parent.parent / "another_server.py")
        )
        self.assertEqual(os.path.normpath(another_path), expected_path)

    def test_mcp_config_absolute_path_unchanged(self):
        """测试绝对路径保持不变。"""
        absolute_path = "/usr/local/bin/mcp_server"
        config_content = f"""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[agent]
compress_threshold = 80000

[[agent.mcp]]
name = "absolute_server"
server_script_path = "{absolute_path}"
"""
        config_path = self.create_test_config(config_content)

        config = load_config(config_path)

        assert config.agent is not None
        agent = config.agent
        self.assertEqual(len(agent.mcp), 1)
        self.assertEqual(agent.mcp[0].server_script_path, absolute_path)

    def test_mcp_config_no_mcp_servers(self):
        """测试没有MCP服务器配置的情况。"""
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

        assert config.agent is not None
        agent = config.agent
        self.assertEqual(len(agent.mcp), 0)

    def test_mcp_config_invalid_name(self):
        """测试无效的MCP服务器名称。"""
        config_content = """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[agent]
compress_threshold = 80000

[[agent.mcp]]
name = "invalid name!"
server_script_path = "server.py"
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

        self.assertIsNotNone(config.agent)  # 现在有默认值，不再为None


if __name__ == "__main__":
    unittest.main()
