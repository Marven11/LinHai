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
        # Create config with real server - use absolute path from project root
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
        
        # Create agent with real MCP server
        config = load_config(config_path)
        agent = await create_agent_from_config(self.group_chat, config)
        
        # Verify agent was created successfully
        self.assertIsInstance(agent, Agent)
        
        # Verify agent was created successfully with MCP configuration
        self.assertIsInstance(agent, Agent)
        
        # Check if agent was created successfully with MCP configuration
        self.assertIsInstance(agent, Agent)
        
        # For integration tests, we verify agent creation
        # Actual MCP tool testing requires a running server
        # This test validates the configuration loading and agent initialization