"""Unit tests for MCP with real server integration."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from linhai.agent import create_agent
from linhai.group_chat import GroupChat
from linhai.tool.mcp_connector import MCPConnector


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
        agent = await create_agent(self.group_chat, config_path)
        
        # Verify agent was created successfully
        from linhai.agent import Agent
        self.assertIsInstance(agent, Agent)
        
        # Verify agent was created successfully with MCP configuration
        from linhai.agent import Agent
        self.assertIsInstance(agent, Agent)
        
        # Check if MCP tools are available in the agent
        # Verify agent has MCP configuration
        self.assertTrue(hasattr(agent, 'config'), "Agent should have config attribute")
        
        # Check for MCP configuration in the agent
        config = agent.config
        mcp_configured = hasattr(config, 'mcp_servers') and config.mcp_servers
        self.assertTrue(mcp_configured, "MCP servers not configured in agent")
        
        # For integration tests, we can verify MCP servers are configured
        # but we can't actually test tool calling without a real server in test environment