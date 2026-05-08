"""PkillCheckerPlugin的单元测试"""

import unittest
from unittest.mock import Mock
from linhai.plugin.command_hints import PkillCheckerPlugin
from linhai.tool.base import FailedToolResult


class TestPkillCheckerPlugin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Mock()
        self.plugin = PkillCheckerPlugin(self.registry)

    async def test_not_process_create(self):
        result = await self.plugin.before_tool_call(
            tool_name="other_tool",
            toolcall_arguments={"argv": ["pkill"]},
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_no_argv(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={},
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_argv_not_list(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": "pkill"},
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_empty_argv(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": []},
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_block_pkill(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["pkill", "-f", "python"]},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("禁止使用pkill", result.content)

    async def test_block_pkill_full_path(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["/usr/bin/pkill", "python"]},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("禁止使用pkill", result.content)

    async def test_allow_kill(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["kill", "12345"]},
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_allow_other_commands(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["ps", "aux"]},
            with_secret=None,
        )
        self.assertIsNone(result)

    def test_register(self):
        mock_lifecycle = Mock()
        mock_lifecycle.before_tool_call.register = Mock()
        self.plugin.register(mock_lifecycle)
        mock_lifecycle.before_tool_call.register.assert_called_once_with(
            self.plugin.before_tool_call
        )


if __name__ == "__main__":
    unittest.main()
