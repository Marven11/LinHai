#!/usr/bin/env python3
"""SudoStdioCheckerPlugin的单元测试"""

import unittest
from unittest.mock import Mock, AsyncMock
from linhai.plugin.sudo_stdio_checker import SudoStdioCheckerPlugin
from linhai.tool.base import ToolResultFailed


class TestSudoStdioCheckerPlugin(unittest.IsolatedAsyncioTestCase):
    """SudoStdioCheckerPlugin测试类"""

    def setUp(self):
        """测试前准备"""
        self.registry = Mock()
        self.plugin = SudoStdioCheckerPlugin(self.registry)

    def test_initialization(self):
        """测试插件初始化"""
        self.assertEqual(self.plugin.registry, self.registry)
        self.assertIsInstance(self.plugin, SudoStdioCheckerPlugin)

    async def test_before_tool_call_not_process_create(self):
        """测试不是process_create工具时不处理"""
        toolcall_arguments = {"argv": ["sudo", "ls"]}
        result = await self.plugin.before_tool_call(
            tool_name="other_tool",
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_before_tool_call_no_argv(self):
        """测试argv参数不存在时不处理"""
        toolcall_arguments = {}
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_before_tool_call_argv_not_list(self):
        """测试argv不是列表类型时返回错误"""
        test_cases = [
            ("sudo ls", "str"),
            (123, "int"),
            ({"command": "sudo"}, "dict"),
        ]
        for argv, type_name in test_cases:
            with self.subTest(argv=argv):
                toolcall_arguments = {"argv": argv}
                result = await self.plugin.before_tool_call(
                    tool_name="process_create",
                    toolcall_arguments=toolcall_arguments,
                    with_secret=None,
                )
                self.assertIsInstance(result, ToolResultFailed)
                self.assertIn("必须是列表类型", result.content)

    async def test_before_tool_call_first_arg_not_sudo(self):
        """测试argv第一个元素不是sudo时不处理"""
        toolcall_arguments = {"argv": ["ls", "-lah"]}
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_before_tool_call_sudo_missing_S_flag(self):
        """测试包含sudo但缺少-S标志时返回失败"""
        test_cases = [
            ["sudo", "ls"],
            ["sudo", "-u", "root", "whoami"],
            ["sudo", "--user", "root", "cat", "/etc/passwd"],
        ]
        for argv in test_cases:
            with self.subTest(argv=argv):
                toolcall_arguments = {"argv": argv}
                result = await self.plugin.before_tool_call(
                    tool_name="process_create",
                    toolcall_arguments=toolcall_arguments,
                    with_secret=None,
                )
                self.assertIsInstance(result, ToolResultFailed)
                self.assertIn("sudo命令必须使用-S标志", result.content)
                self.assertIn("connect_posix_shell_as_machine", result.content)

    async def test_before_tool_call_sudo_with_S_flag(self):
        """测试包含sudo且有-S标志时通过"""
        test_cases = [
            ["sudo", "-S", "ls"],
            ["sudo", "--stdin", "-u", "root", "whoami"],
            ["sudo", "-S", "--user", "root", "cat", "/etc/passwd"],
            ["sudo", "-Sabc", "ls"],
        ]
        for argv in test_cases:
            with self.subTest(argv=argv):
                toolcall_arguments = {"argv": argv}
                result = await self.plugin.before_tool_call(
                    tool_name="process_create",
                    toolcall_arguments=toolcall_arguments,
                    with_secret=None,
                )
                self.assertIsNone(result)

    def test_register_method(self):
        """测试插件的register方法"""
        mock_lifecycle = Mock()
        mock_lifecycle.before_tool_call.register = Mock()

        self.plugin.register(mock_lifecycle)

        mock_lifecycle.before_tool_call.register.assert_called_once_with(
            self.plugin.before_tool_call
        )


if __name__ == "__main__":
    unittest.main()
