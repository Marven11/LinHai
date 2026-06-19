import unittest
from unittest.mock import Mock, AsyncMock

from linhai.plugin.security_config import ProcessArgvCheckerPlugin
from linhai.plugin.command_hints import (
    StdioCommandCheckerPlugin,
    PkillCheckerPlugin,
    _is_shell_command,
)
from linhai.agent.lifecycle import AfterToolcallResult
from linhai.agent.messages import RuntimeMessage
from linhai.tool.base import FailedToolResult


class TestIsShellCommand(unittest.TestCase):
    def test_echo(self):
        self.assertTrue(_is_shell_command("echo hello"))

    def test_sed(self):
        self.assertTrue(_is_shell_command("sed -i 's/old/new/g' file.txt"))

    def test_cat(self):
        self.assertTrue(_is_shell_command("cat /etc/hosts"))

    def test_bash_with_path(self):
        self.assertTrue(_is_shell_command("/bin/bash -c 'echo hi'"))

    def test_python3(self):
        self.assertTrue(_is_shell_command("python3 -c 'print(1)'"))

    def test_leading_whitespace(self):
        self.assertTrue(_is_shell_command("  grep pattern file"))

    def test_empty_string(self):
        self.assertFalse(_is_shell_command(""))

    def test_whitespace_only(self):
        self.assertFalse(_is_shell_command("   "))

    def test_non_command(self):
        self.assertFalse(_is_shell_command("some random text"))

    def test_password_input(self):
        self.assertFalse(_is_shell_command("my_secret_password"))


class TestProcessArgvCheckerPlugin(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.registry = Mock()
        self.plugin = ProcessArgvCheckerPlugin(self.registry)

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
            (["ls", ";", "pwd"], [";"]),
            (["echo", "test", "||", "ls"], ["||"]),
            (["sleep", "1", "&", "echo", "bg"], ["&"]),
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
            toolcall_arguments={"argv": ["echo", "test", "&&", "ls", "||", "pwd"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )

        self.assertIsInstance(result, AfterToolcallResult)
        warning_text = result.warnings[0].get_content()
        self.assertIn("&&", warning_text)
        self.assertIn("||", warning_text)

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

    async def test_after_toolcall_no_false_positive_substring_match(self):
        false_positive_cases = [
            [
                "bash",
                "-c",
                "export TMPDIR=/tmp && cd crates/safeline2_skynet && cbindgen",
            ],
            ["echo", "a>>b"],
            ["ls", "-la", "2>&1"],
            ["echo", "$(pwd)"],
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


class TestStdioCommandCheckerPlugin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Mock()
        self.plugin = StdioCommandCheckerPlugin(self.registry)

    async def test_not_process_stdio_write(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={
                "pid": "123",
                "content": "echo hello",
                "with_enter": True,
            },
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_no_content(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_stdio_write",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"pid": "123", "with_enter": True},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_content_not_string(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_stdio_write",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"pid": "123", "content": 123, "with_enter": True},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_non_command_content(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_stdio_write",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={
                "pid": "123",
                "content": "some non-command input",
                "with_enter": True,
            },
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_shell_command_sends_warning(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="process_stdio_write",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={
                "pid": "123",
                "content": "sed -i 's/old/new/g' file.txt",
                "with_enter": True,
            },
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("connect_posix_shell_as_machine", result.warnings[0].message)

    async def test_time_window_suppresses_repeat(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result1 = await self.plugin.after_toolcall(
            tool_name="process_stdio_write",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={
                "pid": "123",
                "content": "echo hello",
                "with_enter": True,
            },
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNotNone(result1)
        self.assertEqual(len(result1.warnings), 1)

        result2 = await self.plugin.after_toolcall(
            tool_name="process_stdio_write",
            tool_index=1,
            status="success",
            message=None,
            toolcall_arguments={
                "pid": "123",
                "content": "cat /etc/hosts",
                "with_enter": True,
            },
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result2)

    async def test_call_with_secret_unwrap_warns(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="call_with_secret",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={
                "tool_name": "process_stdio_write",
                "tool_arguments": {
                    "pid": "123",
                    "content": "sed -i 's/old/new/g' file.txt",
                    "with_enter": True,
                },
                "with_secret": {"in_arguments": [], "in_result": []},
            },
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("connect_posix_shell_as_machine", result.warnings[0].message)

    async def test_call_with_secret_other_tool_no_warn(self):
        result = await self.plugin.after_toolcall(
            tool_name="call_with_secret",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={
                "tool_name": "write_file",
                "tool_arguments": {"filepath": "/tmp/test", "content": "hello"},
                "with_secret": {"in_arguments": [], "in_result": []},
            },
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)


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

    async def test_mixed_safe_and_unsafe_toolcalls_in_one_generation(self):
        result_safe = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["echo", "hello"]},
            with_secret=None,
        )
        self.assertIsNone(result_safe)

        result_unsafe = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["pkill", "-f", "test"]},
            with_secret=None,
        )
        self.assertIsInstance(result_unsafe, FailedToolResult)
        self.assertIn("禁止使用pkill", result_unsafe.content)

    async def test_call_with_secret_block_pkill(self):
        result = await self.plugin.before_tool_call(
            tool_name="call_with_secret",
            toolcall_arguments={
                "tool_name": "process_create",
                "tool_arguments": {"argv": ["pkill", "-f", "python"]},
                "with_secret": {"in_arguments": [], "in_result": []},
            },
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("禁止使用pkill", result.content)

    async def test_call_with_secret_other_tool_allowed(self):
        result = await self.plugin.before_tool_call(
            tool_name="call_with_secret",
            toolcall_arguments={
                "tool_name": "write_file",
                "tool_arguments": {"filepath": "/tmp/test", "content": "hello"},
                "with_secret": {"in_arguments": [], "in_result": []},
            },
            with_secret=None,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
