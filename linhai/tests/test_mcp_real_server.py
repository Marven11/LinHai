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
        
        # Verify MCP connector is registered and has tools
        connector = self.group_chat.get_members("mcp_connector", MCPConnector)
        self.assertIsNotNone(connector)
        
        # Verify toolsets are registered
        toolsets = connector.get_toolsets()
        self.assertTrue(len(toolsets) >= 2)  # At least connector + server toolsets
        
        # Check that server tools are available
        server_toolset = None
        for ts in toolsets:
            if any("mcp_calculator" in tool_name for tool_name in ts.tools.keys()):
                server_toolset = ts
                break
        
        self.assertIsNotNone(server_toolset, "No server toolset found")
        self.assertIn("mcp_calculator_add", server_toolset.tools)
        self.assertIn("mcp_calculator_multiply", server_toolset.tools)
        
        # Test tool calling - MCP returns CallToolResult, so we check the content
        result = await connector.call_tool_raw("calculator", "add", {"a": 5, "b": 3})
        # CallToolResult has a content attribute with list of TextContent objects
        # FastMCP returns float as string with decimal point, so we accept both "8" and "8.0"
        self.assertIsNotNone(result.content)
        self.assertEqual(len(result.content), 1)
        self.assertIn(result.content[0].text, ["8", "8.0"])