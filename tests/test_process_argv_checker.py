#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from linhai.plugin.security_config import ProcessArgvCheckerPlugin
from linhai.agent.lifecycle import AfterToolcallResult
from linhai.agent.messages import RuntimeMessage
from linhai.tool.base import FailedToolResult


class TestProcessArgvCheckerPlugin(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.registry = Mock()
        self.plugin = ProcessArgvCheckerPlugin(self.registry)

    def test_initialization(self):
        self.assertEqual(self.plugin.registry, self.registry)
        self.assertTrue(hasattr(ProcessArgvCheckerPlugin, "BASH_OPERATOR_PATTERNS"))
        self.assertIsInstance(ProcessArgvCheckerPlugin.BASH_OPERATOR_PATTERNS, list)
        self.assertGreater(len(ProcessArgvCheckerPlugin.BASH_OPERATOR_PATTERNS), 0)

        sample_patterns = ProcessArgvCheckerPlugin.BASH_OPERATOR_PATTERNS
        self.assertTrue(any(p.search("&&") for p in sample_patterns))
        self.assertTrue(any(p.search("|") for p in sample_patterns))
        self.assertTrue(any(p.search(">") for p in sample_patterns))
        self.assertTrue(any(p.search(";") for p in sample_patterns))

    async def test_before_tool_call_no_argv(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={},
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_before_tool_call_not_process_create(self):
        result = await self.plugin.before_tool_call(
            tool_name="other_tool",
            toolcall_arguments={"argv": ["echo", "test"]},
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_before_tool_call_clean_argv(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["echo", "test", "123"]},
            with_secret=None,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_bash_operator(self):
        test_cases = [
            (["echo", "test", "&&", "ls"], ["&&"]),
            (["echo", "test", "|", "grep", "hello"], ["|"]),
            (["echo", "test", ">", "output.txt"], [">"]),
            (["ls", ";", "pwd"], [";"]),
            (["ls", "-la", "2>&1"], ["2>&1"]),
            (["echo", "$(pwd)"], ["$("]),
        ]

        for argv, expected_operators in test_cases:
            with self.subTest(argv=argv):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message=None,
                    toolcall_arguments={"argv": argv},
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

                self.assertIsInstance(result, AfterToolcallResult)
                self.assertEqual(len(result.warnings), 1)
                self.assertIsInstance(result.warnings[0], RuntimeMessage)
                warning_text = result.warnings[0].get_content()
                for operator in expected_operators:
                    self.assertIn(operator, warning_text)

    async def test_after_toolcall_mixed_argv(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["echo", "test", "&&", "ls", ">", "out.txt"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )

        self.assertIsInstance(result, AfterToolcallResult)
        warning_text = result.warnings[0].get_content()
        self.assertIn("&&", warning_text)
        self.assertIn(">", warning_text)

    async def test_after_toolcall_no_false_positive_python_semicolon(self):
        false_positive_cases = [
            [
                "python3",
                "-c",
                "import sqlite3; conn = sqlite3.connect('/path/db.sqlite')",
            ],
            ["python3", "-c", "x = 1; y = 2; print(x + y)"],
            ["python3", "-c", "import os; print(os.getcwd())"],
        ]

        for argv in false_positive_cases:
            with self.subTest(argv=argv):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message=None,
                    toolcall_arguments={"argv": argv},
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )
                self.assertIsNone(result)

    async def test_after_toolcall_standalone_semicolon_detected(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["ls", ";", "pwd"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )

        self.assertIsInstance(result, AfterToolcallResult)
        warning_text = result.warnings[0].get_content()
        self.assertIn(";", warning_text)

    async def test_after_toolcall_no_false_positive_compound_operators(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["echo", "a>>b"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )

        self.assertIsInstance(result, AfterToolcallResult)
        warning_text = result.warnings[0].get_content()
        self.assertIn(">>", warning_text)

    def test_register_method(self):
        mock_lifecycle = Mock()
        mock_lifecycle.before_tool_call.register = Mock()
        mock_lifecycle.after_toolcall.register = Mock()

        self.plugin.register(mock_lifecycle)

        mock_lifecycle.before_tool_call.register.assert_called_once_with(
            self.plugin.before_tool_call
        )
        mock_lifecycle.after_toolcall.register.assert_called_once_with(
            self.plugin.after_toolcall
        )

    async def test_plugin_rejects_non_list_argv(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": "ls -lah"},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是列表类型", result.content)

        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": 123},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是列表类型", result.content)

    async def test_plugin_rejects_non_string_elements(self):
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["ls", 123, "-lah"]},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是字符串类型", result.content)
        self.assertIn("第1个元素", result.content)


if __name__ == "__main__":
    unittest.main()
