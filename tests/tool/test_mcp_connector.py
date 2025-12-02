"""Unit tests for MCP connector."""

import unittest
import unittest.mock
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.tool.mcp_connector import MCPConnector
from linhai.group_chat import GroupChat
from linhai.tool.base import ToolErrorMessage, ToolResultMessage


class TestMCPConnector(unittest.IsolatedAsyncioTestCase):
    """Test cases for the MCPConnector class."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.group_chat = GroupChat()
        self.connector = MCPConnector(self.group_chat)

    async def test_initialization(self):
        """测试MCP连接器初始化。"""
        self.assertEqual(self.connector.group_chat, self.group_chat)
        self.assertEqual(self.connector.sessions, {})
        self.assertIsNotNone(self.connector.connector_toolset)

    @patch('linhai.tool.mcp_connector.stdio_client')
    @patch('linhai.tool.mcp_connector.ClientSession')
    @patch('os.path.exists')
    async def test_connect_mcp_server_success(self, mock_exists, mock_session_class, mock_stdio_client):
        """测试成功连接MCP服务器。"""
        mock_exists.return_value = True

        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_stdio_client.return_value.__aenter__.return_value = (mock_reader, mock_writer)

        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object", "properties": {}}
        mock_session.list_tools.return_value.tools = [mock_tool]

        await self.connector.connect_mcp_server("test_server", "test_server.py")

        self.assertIn("test_server", self.connector.sessions)
        session, _, toolset = self.connector.sessions["test_server"]
        self.assertEqual(session, mock_session)
        self.assertIsNotNone(toolset)

        self.assertTrue(toolset.has_tool("mcp_test_server_test_tool"))

    @patch('linhai.tool.mcp_connector.stdio_client')
    @patch('linhai.tool.mcp_connector.ClientSession')
    @patch('os.path.exists')
    async def test_connect_mcp_server_duplicate_name(
        self, mock_exists, mock_session_class, mock_stdio_client
    ):
        """测试连接重复名称的MCP服务器。"""
        mock_exists.return_value = True

        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_stdio_client.return_value.__aenter__.return_value = (mock_reader, mock_writer)
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = []

        await self.connector.connect_mcp_server("test_server", "test_server.py")

        with self.assertRaises(RuntimeError) as context:
            await self.connector.connect_mcp_server("test_server", "another_server.py")

        self.assertIn("Duplicate name", str(context.exception))

    @patch('os.path.exists')
    async def test_connect_mcp_server_file_not_exists(self, mock_exists):
        """测试连接不存在的MCP服务器文件。"""
        mock_exists.return_value = False

        with self.assertRaises(RuntimeError) as context:
            await self.connector.connect_mcp_server("test_server", "nonexistent.py")

        self.assertIn("Not exists", str(context.exception))

    async def test_disconnect_success(self):
        """测试成功断开连接。"""
        mock_session = AsyncMock()
        mock_exit_stack = AsyncMock()
        mock_toolset = MagicMock()

        self.connector.sessions["test_server"] = (mock_session, mock_exit_stack, mock_toolset)

        await self.connector.disconnect_mcp_server("test_server")

        self.assertNotIn("test_server", self.connector.sessions)

    async def test_disconnect_not_exists(self):
        """测试断开不存在的连接。"""
        with self.assertRaises(RuntimeError) as context:
            await self.connector.disconnect_mcp_server("nonexistent")

        self.assertIn("not exists", str(context.exception))

    async def test_disconnect_all(self):
        """测试断开所有连接。"""
        mock_exit_stack1 = AsyncMock()
        mock_exit_stack2 = AsyncMock()

        self.connector.sessions["server1"] = (AsyncMock(), mock_exit_stack1, MagicMock())
        self.connector.sessions["server2"] = (AsyncMock(), mock_exit_stack2, MagicMock())

        await self.connector.disconnect_all_mcp_servers()

        self.assertEqual(self.connector.sessions, {})

    async def test_get_server_success(self):
        """测试成功获取服务器。"""
        mock_session = AsyncMock()
        self.connector.sessions["test_server"] = (mock_session, AsyncMock(), MagicMock())

        result = self.connector.get_server("test_server")
        self.assertEqual(result, mock_session)

    async def test_get_server_not_exists(self):
        """测试获取不存在的服务器。"""
        with self.assertRaises(RuntimeError) as context:
            self.connector.get_server("nonexistent")

        self.assertIn("not exists", str(context.exception))

    async def test_call_tool_raw_success(self):
        """测试成功调用MCP工具。"""
        mock_session = AsyncMock()
        mock_session.call_tool.return_value = {"result": "success"}
        self.connector.sessions["test_server"] = (mock_session, AsyncMock(), MagicMock())

        result = await self.connector.call_tool_raw("test_server", "test_tool", {"arg": "value"})

        mock_session.call_tool.assert_called_once_with("test_tool", arguments={"arg": "value"})
        self.assertEqual(result, {"result": "success"})

    async def test_get_toolsets(self):
        """测试获取工具集。"""
        toolsets = self.connector.get_toolsets()
        self.assertEqual(len(toolsets), 1)
        self.assertEqual(toolsets[0], self.connector.connector_toolset)

        mock_toolset = MagicMock()
        self.connector.sessions["test_server"] = (AsyncMock(), AsyncMock(), mock_toolset)

        toolsets = self.connector.get_toolsets()
        self.assertEqual(len(toolsets), 2)
        self.assertIn(mock_toolset, toolsets)
        self.assertIn(self.connector.connector_toolset, toolsets)


class TestMCPConnectorTools(unittest.IsolatedAsyncioTestCase):
    """Test cases for MCP connector tools."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.group_chat = GroupChat()
        self.connector = MCPConnector(self.group_chat)

    @patch('linhai.tool.mcp_connector.MCPConnector.connect_mcp_server')
    async def test_connect_mcp_server_tool_success(self, mock_connect):
        """测试connect_stdio工具成功。"""
        mock_toolset = MagicMock()
        mock_toolset.tools.keys.return_value = ["tool1", "tool2"]
        mock_connect.return_value = (AsyncMock(), AsyncMock(), mock_toolset)

        result = await self.connector.connector_toolset.call_tool(
            "connect_mcp_server",
            {"name": "test_server", "server_script_path": "test.py"}
        )

        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("连接'test.py'成功", result.content)
        self.assertIn("tool1, tool2", result.content)

    @patch('linhai.tool.mcp_connector.MCPConnector.connect_mcp_server')
    async def test_connect_mcp_server_tool_failure(self, mock_connect):
        """测试connect_stdio工具失败。"""
        mock_connect.side_effect = Exception("Connection failed")

        result = await self.connector.connector_toolset.call_tool(
            "connect_mcp_server",
            {"name": "test_server", "server_script_path": "test.py"}
        )

        self.assertIsInstance(result, ToolErrorMessage)
        self.assertIn("连接'test.py'失败", result.content)
        self.assertIn("Connection failed", result.content)


if __name__ == "__main__":
    unittest.main()
    async def test_disconnect_tool_success(self):
        """测试disconnect工具成功。"""
        mock_session = AsyncMock()
        mock_exit_stack = AsyncMock()
        mock_toolset = MagicMock()
        self.connector.sessions["test_server"] = (mock_session, mock_exit_stack, mock_toolset)

        result = await self.connector.connector_toolset.call_tool(
            "disconnect_mcp_server",
            {"name": "test_server"}
        )

        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("成功断开MCP服务器: 'test_server'", result.content)
        self.assertNotIn("test_server", self.connector.sessions)

    async def test_disconnect_tool_failure(self):
        """测试disconnect工具失败。"""
        result = await self.connector.connector_toolset.call_tool(
            "disconnect_mcp_server",
            {"name": "nonexistent"}
        )

        self.assertIsInstance(result, ToolErrorMessage)
        self.assertIn("断开失败", result.content)
        self.assertIn("'nonexistent' not exists", result.content)

    async def test_disconnect_all_tool_success(self):
        """测试disconnect_all工具成功。"""
        mock_exit_stack1 = AsyncMock()
        mock_exit_stack2 = AsyncMock()
        self.connector.sessions["server1"] = (AsyncMock(), mock_exit_stack1, MagicMock())
        self.connector.sessions["server2"] = (AsyncMock(), mock_exit_stack2, MagicMock())

        result = await self.connector.connector_toolset.call_tool("disconnect_all_mcp_servers", {})

        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("成功断开所有MCP服务器", result.content)
        self.assertEqual(self.connector.sessions, {})

    async def test_disconnect_all_tool_failure(self):
        """测试disconnect_all工具失败。"""
        with patch('linhai.tool.mcp_connector.MCPConnector.disconnect_all_mcp_servers') as mock_disconnect_all:
            mock_disconnect_all.side_effect = Exception("Disconnect error")

            result = await self.connector.connector_toolset.call_tool("disconnect_all_mcp_servers", {})

            self.assertIsInstance(result, ToolErrorMessage)
            self.assertIn("断开所有服务器失败", result.content)
            self.assertIn("Disconnect error", result.content)

    async def test_list_mcp_servers_tool_with_servers(self):
        """测试list_mcp_servers工具有服务器的情况。"""
        self.connector.sessions["server1"] = (AsyncMock(), AsyncMock(), MagicMock())
        self.connector.sessions["server2"] = (AsyncMock(), AsyncMock(), MagicMock())

        result = await self.connector.connector_toolset.call_tool("list_mcp_servers", {})

        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("已连接的MCP服务器 (2个)", result.content)
        self.assertIn("- server1", result.content)
        self.assertIn("- server2", result.content)

    async def test_list_mcp_servers_tool_empty(self):
        """测试list_mcp_servers工具无服务器的情况。"""
        self.connector.sessions = {}

        result = await self.connector.connector_toolset.call_tool("list_mcp_servers", {})

        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("当前没有已连接的MCP服务器", result.content)