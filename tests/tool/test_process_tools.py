#!/usr/bin/env python3
"""测试process工具"""

import asyncio
import inspect
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from linhai.base import ToolCallMessage
from linhai.tool.base import ToolCallResultMessage
from linhai.tool.base import SuccessfulToolResult, FailedToolResult
from linhai.machine_control.process import ProcessIOError
from linhai.machine_control.tools import register_machine_control_tools
from linhai.machine_control import MachineControl
from linhai.tool.main import ToolManager
from linhai.registry import Registry
from linhai.config import ToolConfig


class TestProcessTools(unittest.IsolatedAsyncioTestCase):
    """测试process工具"""

    def test_process_create_tool_definition(self):
        """测试process_create工具定义是否存在于工具列表中"""
        mock_machine_control = Mock()
        mock_machine_control.machines = {"master_host": Mock()}
        mock_machine_control.target_machine = "master_host"

        toolset = register_machine_control_tools(mock_machine_control)

        self.assertTrue(toolset.has_tool("process_create"))

        tool_func = toolset.get_tool("process_create")
        self.assertIsNotNone(tool_func)

        import asyncio

        self.assertTrue(inspect.iscoroutinefunction(tool_func))

    def test_process_stdio_write_tool_definition(self):
        """测试process_stdio_write工具定义"""
        mock_machine_control = Mock()
        mock_machine_control.machines = {"master_host": Mock()}
        mock_machine_control.target_machine = "master_host"

        toolset = register_machine_control_tools(mock_machine_control)

        self.assertTrue(toolset.has_tool("process_stdio_write"))

        tool_func = toolset.get_tool("process_stdio_write")
        self.assertIsNotNone(tool_func)

        import asyncio

        self.assertTrue(inspect.iscoroutinefunction(tool_func))

        signature = inspect.signature(tool_func)
        self.assertIn("with_enter", signature.parameters)
        param = signature.parameters["with_enter"]
        self.assertEqual(param.default, inspect.Parameter.empty)

    def test_process_stdio_read_tool_definition(self):
        """测试process_stdio_read工具定义"""
        mock_machine_control = Mock()
        mock_machine_control.machines = {"master_host": Mock()}
        mock_machine_control.target_machine = "master_host"

        toolset = register_machine_control_tools(mock_machine_control)

        self.assertTrue(toolset.has_tool("process_stdio_read"))

        tool_func = toolset.get_tool("process_stdio_read")
        self.assertIsNotNone(tool_func)

        import asyncio

        self.assertTrue(inspect.iscoroutinefunction(tool_func))

        signature = inspect.signature(tool_func)
        self.assertIn("timeout", signature.parameters)
        param = signature.parameters["timeout"]
        self.assertEqual(param.default, 60.0)

    def test_process_wait_tool_definition(self):
        """测试process_wait工具定义"""
        mock_machine_control = Mock()
        mock_machine_control.machines = {"master_host": Mock()}
        mock_machine_control.target_machine = "master_host"

        toolset = register_machine_control_tools(mock_machine_control)

        self.assertTrue(toolset.has_tool("process_wait"))

        tool_func = toolset.get_tool("process_wait")
        self.assertIsNotNone(tool_func)

        import asyncio

        self.assertTrue(inspect.iscoroutinefunction(tool_func))

    def test_process_kill_tool_definition(self):
        """测试process_kill工具定义"""
        mock_machine_control = Mock()
        mock_machine_control.machines = {"master_host": Mock()}
        mock_machine_control.target_machine = "master_host"

        toolset = register_machine_control_tools(mock_machine_control)

        self.assertTrue(toolset.has_tool("process_kill"))

        tool_func = toolset.get_tool("process_kill")
        self.assertIsNotNone(tool_func)

        import asyncio

        self.assertTrue(inspect.iscoroutinefunction(tool_func))

    def test_process_create_pty_parameter(self):
        mock_machine_control = Mock()
        mock_machine_control.machines = {"master_host": Mock()}
        mock_machine_control.target_machine = "master_host"

        toolset = register_machine_control_tools(mock_machine_control)
        tool_func = toolset.get_tool("process_create")

        signature = inspect.signature(tool_func)
        self.assertIn("pty", signature.parameters)
        param = signature.parameters["pty"]
        self.assertEqual(param.default, False)

    def test_process_create_with_stdin_parameter(self):
        mock_machine_control = Mock()
        mock_machine_control.machines = {"master_host": Mock()}
        mock_machine_control.target_machine = "master_host"

        toolset = register_machine_control_tools(mock_machine_control)
        tool_func = toolset.get_tool("process_create")

        signature = inspect.signature(tool_func)
        self.assertIn("with_stdin", signature.parameters)
        param = signature.parameters["with_stdin"]
        self.assertEqual(param.default, None)

    def _make_io_error_toolset(self, method_name: str):
        mock_proc = AsyncMock()
        getattr(mock_proc, method_name).return_value = ProcessIOError(
            error="连接已失效"
        )
        mock_host = Mock()
        mock_host.get_process.return_value = mock_proc
        mock_mc = Mock()
        mock_mc.machines = {"master_host": mock_host}
        mock_mc.target_machine = "master_host"
        return register_machine_control_tools(mock_mc)

    async def test_stdio_write_io_error(self):
        toolset = self._make_io_error_toolset("stdio_write")
        tool_func = toolset.get_tool("process_stdio_write")
        result = await tool_func(pid="123", content="hello", with_enter=True)
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("连接已失效", result.content)

    async def test_stdio_read_io_error(self):
        toolset = self._make_io_error_toolset("stdio_read")
        tool_func = toolset.get_tool("process_stdio_read")
        result = await tool_func(pid="123", timeout=1.0)
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("连接已失效", result.content)

    async def test_wait_io_error(self):
        toolset = self._make_io_error_toolset("wait")
        tool_func = toolset.get_tool("process_wait")
        result = await tool_func(pid="123", timeout=1.0)
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("连接已失效", result.content)

    async def test_kill_io_error(self):
        toolset = self._make_io_error_toolset("kill")
        tool_func = toolset.get_tool("process_kill")
        result = await tool_func(pid="123")
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("连接已失效", result.content)


if __name__ == "__main__":
    unittest.main()
