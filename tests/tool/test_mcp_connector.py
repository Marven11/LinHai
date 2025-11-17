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
        # 模拟文件存在
        mock_exists.return_value = True

        # 模拟stdio_client和ClientSession
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_stdio_client.return_value.__aenter__.return_value = (mock_reader, mock_writer)

        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        # 模拟list_tools返回
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object", "properties": {}}
        mock_session.list_tools.return_value.tools = [mock_tool]

        # 测试连接
        await self.connector.connect_mcp_server("test_server", "test_server.py")

        # 验证连接成功
        self.assertIn("test_server", self.connector.sessions)
        session, _, toolset = self.connector.sessions["test_server"]
        self.assertEqual(session, mock_session)
        self.assertIsNotNone(toolset)

        # 验证工具被正确注册
        self.assertTrue(toolset.has_tool("mcp_test_server_test_tool"))

    @patch('linhai.tool.mcp_connector.stdio_client')
    @patch('linhai.tool.mcp_connector.ClientSession')
    @patch('os.path.exists')
    async def test_connect_mcp_server_duplicate_name(
        self, mock_exists, mock_session_class, mock_stdio_client
    ):
        """测试连接重复名称的MCP服务器。"""
        # 模拟文件存在
        mock_exists.return_value = True

        # 第一次连接
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_stdio_client.return_value.__aenter__.return_value = (mock_reader, mock_writer)
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = []

        await self.connector.connect_mcp_server("test_server", "test_server.py")

        # 第二次连接相同名称
        with self.assertRaises(RuntimeError) as context:
            await self.connector.connect_mcp_server("test_server", "another_server.py")

        self.assertIn("Duplicate name", str(context.exception))

    @patch('os.path.exists')
    async def test_connect_mcp_server_file_not_exists(self, mock_exists):
        """测试连接不存在的MCP服务器文件。"""
        # 模拟文件不存在
        mock_exists.return_value = False

        with self.assertRaises(RuntimeError) as context:
            await self.connector.connect_mcp_server("test_server", "nonexistent.py")

        self.assertIn("Not exists", str(context.exception))

    async def test_disconnect_success(self):
        """测试成功断开连接。"""
        # 模拟一个会话
        mock_session = AsyncMock()
        mock_exit_stack = AsyncMock()
        mock_toolset = MagicMock()

        self.connector.sessions["test_server"] = (mock_session, mock_exit_stack, mock_toolset)

        await self.connector.disconnect_mcp_server("test_server")

        # 验证会话已被移除
        self.assertNotIn("test_server", self.connector.sessions)

    async def test_disconnect_not_exists(self):
        """测试断开不存在的连接。"""
        with self.assertRaises(RuntimeError) as context:
            await self.connector.disconnect_mcp_server("nonexistent")

        self.assertIn("not exists", str(context.exception))

    async def test_disconnect_all(self):
        """测试断开所有连接。"""
        # 模拟多个会话
        mock_exit_stack1 = AsyncMock()
        mock_exit_stack2 = AsyncMock()

        self.connector.sessions["server1"] = (AsyncMock(), mock_exit_stack1, MagicMock())
        self.connector.sessions["server2"] = (AsyncMock(), mock_exit_stack2, MagicMock())

        await self.connector.disconnect_all_mcp_servers()

        # 验证所有会话已被移除
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

        # 验证工具被正确调用
        mock_session.call_tool.assert_called_once_with("test_tool", arguments={"arg": "value"})
        self.assertEqual(result, {"result": "success"})

    async def test_get_toolsets(self):
        """测试获取工具集。"""
        # 初始状态下只有连接器工具集
        toolsets = self.connector.get_toolsets()
        self.assertEqual(len(toolsets), 1)
        self.assertEqual(toolsets[0], self.connector.connector_toolset)

        # 添加一个会话后
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
        # 模拟连接成功
        mock_toolset = MagicMock()
        mock_toolset.tools.keys.return_value = ["tool1", "tool2"]
        mock_connect.return_value = (AsyncMock(), AsyncMock(), mock_toolset)

        # 使用工具集调用工具
        result = await self.connector.connector_toolset.call_tool(
            "connect_mcp_server",
            {"name": "test_server", "server_script_path": "test.py"}
        )

        # 验证返回成功消息
        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("连接'test.py'成功", result.content)
        self.assertIn("tool1, tool2", result.content)

    @patch('linhai.tool.mcp_connector.MCPConnector.connect_mcp_server')
    async def test_connect_mcp_server_tool_failure(self, mock_connect):
        """测试connect_stdio工具失败。"""
        # 模拟连接失败
        mock_connect.side_effect = Exception("Connection failed")

        # 使用工具集调用工具
        result = await self.connector.connector_toolset.call_tool(
            "connect_mcp_server",
            {"name": "test_server", "server_script_path": "test.py"}
        )

        # 验证返回错误消息
        self.assertIsInstance(result, ToolErrorMessage)
        self.assertIn("连接'test.py'失败", result.content)
        self.assertIn("Connection failed", result.content)


if __name__ == "__main__":
    unittest.main()
    async def test_disconnect_tool_success(self):
        """测试disconnect工具成功。"""
        # 模拟一个会话
        mock_session = AsyncMock()
        mock_exit_stack = AsyncMock()
        mock_toolset = MagicMock()
        self.connector.sessions["test_server"] = (mock_session, mock_exit_stack, mock_toolset)

        # 使用工具集调用工具
        result = await self.connector.connector_toolset.call_tool(
            "disconnect_mcp_server",
            {"name": "test_server"}
        )

        # 验证返回成功消息
        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("成功断开MCP服务器: 'test_server'", result.content)
        # 验证会话已被移除
        self.assertNotIn("test_server", self.connector.sessions)

    async def test_disconnect_tool_failure(self):
        """测试disconnect工具失败。"""
        # 使用工具集调用不存在的服务器
        result = await self.connector.connector_toolset.call_tool(
            "disconnect_mcp_server",
            {"name": "nonexistent"}
        )

        # 验证返回错误消息
        self.assertIsInstance(result, ToolErrorMessage)
        self.assertIn("断开失败", result.content)
        self.assertIn("'nonexistent' not exists", result.content)

    async def test_disconnect_all_tool_success(self):
        """测试disconnect_all工具成功。"""
        # 模拟多个会话
        mock_exit_stack1 = AsyncMock()
        mock_exit_stack2 = AsyncMock()
        self.connector.sessions["server1"] = (AsyncMock(), mock_exit_stack1, MagicMock())
        self.connector.sessions["server2"] = (AsyncMock(), mock_exit_stack2, MagicMock())

        # 使用工具集调用工具
        result = await self.connector.connector_toolset.call_tool("disconnect_all_mcp_servers", {})

        # 验证返回成功消息
        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("成功断开所有MCP服务器", result.content)
        # 验证所有会话已被移除
        self.assertEqual(self.connector.sessions, {})

    async def test_disconnect_all_tool_failure(self):
        """测试disconnect_all工具失败。"""
        # 模拟disconnect_all抛出异常
        with patch('linhai.tool.mcp_connector.MCPConnector.disconnect_all_mcp_servers') as mock_disconnect_all:
            mock_disconnect_all.side_effect = Exception("Disconnect error")

            # 使用工具集调用工具
            result = await self.connector.connector_toolset.call_tool("disconnect_all_mcp_servers", {})

            # 验证返回错误消息
            self.assertIsInstance(result, ToolErrorMessage)
            self.assertIn("断开所有服务器失败", result.content)
            self.assertIn("Disconnect error", result.content)

    async def test_list_mcp_servers_tool_with_servers(self):
        """测试list_mcp_servers工具有服务器的情况。"""
        # 模拟多个会话
        self.connector.sessions["server1"] = (AsyncMock(), AsyncMock(), MagicMock())
        self.connector.sessions["server2"] = (AsyncMock(), AsyncMock(), MagicMock())

        # 使用工具集调用工具
        result = await self.connector.connector_toolset.call_tool("list_mcp_servers", {})

        # 验证返回成功消息
        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("已连接的MCP服务器 (2个)", result.content)
        self.assertIn("- server1", result.content)
        self.assertIn("- server2", result.content)

    async def test_list_mcp_servers_tool_empty(self):
        """测试list_mcp_servers工具无服务器的情况。"""
        # 确保没有会话
        self.connector.sessions = {}

        # 使用工具集调用工具
        result = await self.connector.connector_toolset.call_tool("list_mcp_servers", {})

        # 验证返回成功消息
        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("当前没有已连接的MCP服务器", result.content)