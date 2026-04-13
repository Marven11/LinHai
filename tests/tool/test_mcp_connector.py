"""Unit tests for MCP connector."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.tool.mcp_connector import MCPConnector, MCPServerConnection
from linhai.registry import Registry
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.sandbox import NoSandbox, ProcessSandboxProtocol


def _make_mock_conn() -> MagicMock:
    conn = MagicMock(spec=MCPServerConnection)
    conn._session = AsyncMock()
    conn.toolset = MagicMock()
    conn.close = AsyncMock()
    return conn


class TestMCPServerConnection(unittest.IsolatedAsyncioTestCase):
    @patch("linhai.tool.mcp_connector.stdio_client")
    @patch("linhai.tool.mcp_connector.ClientSession")
    async def test_run_success(self, mock_session_class, mock_stdio_client):
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_stdio_client.return_value.__aenter__.return_value = (
            mock_reader,
            mock_writer,
        )

        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object", "properties": {}}
        mock_session.list_tools.return_value.tools = [mock_tool]

        registry = Registry()
        connector = MCPConnector(registry)
        conn = MCPServerConnection("test_server", "test_server.py", connector)
        conn.start()
        await conn.wait_ready(timeout=5.0)

        assert conn._session is not None
        assert conn.toolset is not None
        self.assertTrue(conn.toolset.has_tool("mcp_test_server_test_tool"))

        await conn.close()

    @patch("linhai.tool.mcp_connector.stdio_client")
    @patch("linhai.tool.mcp_connector.ClientSession")
    async def test_wait_ready_timeout(self, mock_session_class, mock_stdio_client):
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_stdio_client.return_value.__aenter__.return_value = (
            mock_reader,
            mock_writer,
        )
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        async def hang_forever():
            await asyncio.Event().wait()

        mock_session.initialize.side_effect = hang_forever

        registry = Registry()
        connector = MCPConnector(registry)
        conn = MCPServerConnection("test_server", "test_server.py", connector)
        conn.start()

        with self.assertRaises(asyncio.TimeoutError):
            await conn.wait_ready(timeout=0.1)


class TestMCPConnector(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.registry = Registry()
        self.connector = MCPConnector(self.registry)

    async def test_initialization(self):
        self.assertEqual(self.connector.registry, self.registry)
        self.assertEqual(self.connector.sessions, {})
        self.assertIsNotNone(self.connector.connector_toolset)

    @patch("linhai.tool.mcp_connector.MCPServerConnection")
    async def test_connect_mcp_server_success(self, mock_conn_class):
        mock_conn = _make_mock_conn()
        mock_conn_class.return_value = mock_conn

        await self.connector.connect_mcp_server("test_server", "test_server.py")

        self.assertIn("test_server", self.connector.sessions)
        self.assertEqual(self.connector.sessions["test_server"], mock_conn)
        mock_conn.start.assert_called_once()
        mock_conn.wait_ready.assert_called_once()

    @patch("linhai.tool.mcp_connector.MCPServerConnection")
    async def test_connect_mcp_server_duplicate_name(self, mock_conn_class):
        mock_conn = _make_mock_conn()
        mock_conn_class.return_value = mock_conn

        await self.connector.connect_mcp_server("test_server", "test_server.py")

        with self.assertRaises(RuntimeError) as context:
            await self.connector.connect_mcp_server("test_server", "another_server.py")

        self.assertIn("Duplicate name", str(context.exception))

    async def test_disconnect_success(self):
        mock_conn = _make_mock_conn()
        self.connector.sessions["test_server"] = mock_conn

        await self.connector.disconnect_mcp_server("test_server")

        self.assertNotIn("test_server", self.connector.sessions)
        mock_conn.close.assert_called_once()

    async def test_disconnect_not_exists(self):
        with self.assertRaises(RuntimeError) as context:
            await self.connector.disconnect_mcp_server("nonexistent")

        self.assertIn("not exists", str(context.exception))

    async def test_get_server_success(self):
        mock_conn = _make_mock_conn()
        self.connector.sessions["test_server"] = mock_conn

        result = self.connector.get_server("test_server")
        self.assertEqual(result, mock_conn)

    async def test_get_server_not_exists(self):
        with self.assertRaises(RuntimeError) as context:
            self.connector.get_server("nonexistent")

        self.assertIn("not exists", str(context.exception))

    async def test_call_tool_raw_success(self):
        mock_conn = _make_mock_conn()
        mock_data = MagicMock()
        mock_data.meta = {}
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "success"
        mock_data.content = [mock_content]
        mock_conn._session.call_tool.return_value = mock_data
        self.connector.sessions["test_server"] = mock_conn

        result = await self.connector.call_tool_raw(
            "test_server", "test_tool", {"arg": "value"}
        )

        mock_conn._session.call_tool.assert_called_once_with(
            "test_tool", arguments={"arg": "value"}
        )
        self.assertIsInstance(result, ToolResultSuccess)
        self.assertEqual(result.content, "data.meta={}\nsuccess")

    async def test_call_tool_raw_failure(self):
        mock_conn = _make_mock_conn()
        mock_conn._session.call_tool.side_effect = ConnectionError("boom")
        self.connector.sessions["test_server"] = mock_conn

        result = await self.connector.call_tool_raw(
            "test_server", "test_tool", {"arg": "value"}
        )

        self.assertIsInstance(result, ToolResultFailed)

    async def test_get_toolsets_empty(self):
        toolsets = self.connector.get_toolsets()
        self.assertEqual(len(toolsets), 1)
        self.assertEqual(toolsets[0], self.connector.connector_toolset)

    async def test_get_toolsets_with_session(self):
        mock_conn = _make_mock_conn()
        mock_toolset = MagicMock()
        mock_conn.toolset = mock_toolset
        self.connector.sessions["test_server"] = mock_conn

        toolsets = self.connector.get_toolsets()
        self.assertEqual(len(toolsets), 2)
        self.assertIn(mock_toolset, toolsets)
        self.assertIn(self.connector.connector_toolset, toolsets)


class TestMCPConnectorTools(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.registry = Registry()
        self.registry.register_member("process_sandbox", NoSandbox())
        self.connector = MCPConnector(self.registry)

    @patch("linhai.tool.mcp_connector.MCPConnector.connect_mcp_server")
    async def test_connect_mcp_server_tool_success(self, mock_connect):
        mock_conn = _make_mock_conn()
        mock_conn.toolset.tools.keys.return_value = ["tool1", "tool2"]
        mock_connect.return_value = mock_conn

        result = await self.connector.connector_toolset.call_tool(
            "connect_mcp_server",
            {"name": "test_server", "command": "test.py"},
        )

        self.assertIsInstance(result, ToolResultSuccess)
        self.assertIn("连接'test.py'成功", result.content)
        self.assertIn("tool1, tool2", result.content)

    @patch("linhai.tool.mcp_connector.MCPConnector.connect_mcp_server")
    async def test_connect_mcp_server_tool_failure(self, mock_connect):
        mock_connect.side_effect = RuntimeError("Connection failed")

        result = await self.connector.connector_toolset.call_tool(
            "connect_mcp_server",
            {"name": "test_server", "command": "test.py"},
        )

        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("连接'test.py'失败", result.content)
        self.assertIn("Connection failed", result.content)

    async def test_disconnect_tool_success(self):
        mock_conn = _make_mock_conn()
        self.connector.sessions["test_server"] = mock_conn

        result = await self.connector.connector_toolset.call_tool(
            "disconnect_mcp_server", {"name": "test_server"}
        )

        self.assertIsInstance(result, ToolResultSuccess)
        self.assertIn("成功断开MCP服务器: 'test_server'", result.content)
        self.assertNotIn("test_server", self.connector.sessions)

    async def test_disconnect_tool_failure(self):
        result = await self.connector.connector_toolset.call_tool(
            "disconnect_mcp_server", {"name": "nonexistent"}
        )

        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("断开失败", result.content)
        self.assertIn("'nonexistent' not exists", result.content)

    async def test_list_mcp_servers_tool_with_servers(self):
        self.connector.sessions["server1"] = _make_mock_conn()
        self.connector.sessions["server2"] = _make_mock_conn()

        result = await self.connector.connector_toolset.call_tool(
            "list_mcp_servers", {}
        )

        self.assertIsInstance(result, ToolResultSuccess)
        self.assertIn("已连接的MCP服务器 (2个)", result.content)
        self.assertIn("- server1", result.content)
        self.assertIn("- server2", result.content)

    async def test_list_mcp_servers_tool_empty(self):
        self.connector.sessions = {}

        result = await self.connector.connector_toolset.call_tool(
            "list_mcp_servers", {}
        )

        self.assertIsInstance(result, ToolResultSuccess)
        self.assertIn("当前没有已连接的MCP服务器", result.content)


class TestMCPSandbox(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.registry = Registry()
        self.connector = MCPConnector(self.registry)

    @patch("linhai.tool.mcp_connector.MCPConnector.connect_mcp_server")
    async def test_connect_wrapped_with_sandbox(self, mock_connect):
        mock_sandbox = MagicMock(spec=ProcessSandboxProtocol)
        mock_sandbox.wrap_argv.return_value = ["sandbox-exec", "test.py"]
        self.registry.register_member("process_sandbox", mock_sandbox)

        mock_conn = _make_mock_conn()
        mock_conn.toolset.tools.keys.return_value = ["tool1"]
        mock_connect.return_value = mock_conn

        result = await self.connector.connector_toolset.call_tool(
            "connect_mcp_server",
            {"name": "test_server", "command": "test.py"},
        )

        self.assertIsInstance(result, ToolResultSuccess)
        mock_sandbox.wrap_argv.assert_called_once_with(["test.py"])
        mock_connect.assert_called_once_with("test_server", "sandbox-exec test.py")

    @patch("linhai.tool.mcp_connector.MCPConnector.connect_mcp_server")
    async def test_connect_allowed_with_no_sandbox(self, mock_connect):
        self.registry.register_member("process_sandbox", NoSandbox())
        mock_conn = _make_mock_conn()
        mock_conn.toolset.tools.keys.return_value = ["tool1"]
        mock_connect.return_value = mock_conn

        result = await self.connector.connector_toolset.call_tool(
            "connect_mcp_server",
            {"name": "test_server", "command": "test.py"},
        )
        self.assertIsInstance(result, ToolResultSuccess)

    async def test_disconnect_not_blocked_by_sandbox(self):
        self.registry.register_member(
            "process_sandbox", MagicMock(spec=ProcessSandboxProtocol)
        )
        result = await self.connector.connector_toolset.call_tool(
            "disconnect_mcp_server", {"name": "nonexistent"}
        )
        self.assertIsInstance(result, ToolResultFailed)
        self.assertNotIn("沙箱", result.content)

    async def test_list_not_blocked_by_sandbox(self):
        self.registry.register_member(
            "process_sandbox", MagicMock(spec=ProcessSandboxProtocol)
        )
        result = await self.connector.connector_toolset.call_tool(
            "list_mcp_servers", {}
        )
        self.assertIsInstance(result, ToolResultSuccess)


if __name__ == "__main__":
    unittest.main()
