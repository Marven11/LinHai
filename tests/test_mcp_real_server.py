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
        self.temp_dir = tempfile.mkdtemp()
        self.group_chat = GroupChat()

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
        """Test full integration with real MCP server."""
        project_root = Path(__file__).parent.parent.parent
        server_path = project_root / "linhai" / "tests" / "real_mcp_server.py"
        
        config_content = f'''
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[agent]
compress_threshold_soft = 40000
compress_threshold_hard = 80000

[[agent.mcp]]
name = "calculator"
server_script_path = "{server_path}"
'''
        config_path = self.create_test_config(config_content)
        
        config = load_config(config_path)
        agent = await create_agent_from_config(self.group_chat, config)
        
        self.assertIsInstance(agent, Agent)
        
        self.assertIsInstance(agent, Agent)
        
        self.assertIsInstance(agent, Agent)
        
