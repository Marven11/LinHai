import unittest
from unittest.mock import Mock, AsyncMock
from linhai.plugin.sudo_bash_hint import (
    StdioCommandCheckerPlugin,
    _is_shell_command,
)


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
        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = mock_agent.message_processor.add_new_message.call_args[0][0]
        self.assertIn("connect_posix_shell_as_machine", call_args.message)

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
        self.assertIsNone(result1)
        self.assertEqual(mock_agent.message_processor.add_new_message.call_count, 1)

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
        self.assertEqual(mock_agent.message_processor.add_new_message.call_count, 1)

    def test_register_method(self):
        mock_lifecycle = Mock()
        mock_lifecycle.after_toolcall.register = Mock()
        self.plugin.register(mock_lifecycle)
        mock_lifecycle.after_toolcall.register.assert_called_once_with(
            self.plugin.after_toolcall
        )


if __name__ == "__main__":
    unittest.main()
