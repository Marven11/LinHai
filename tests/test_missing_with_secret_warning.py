import unittest
from unittest.mock import Mock, AsyncMock

from linhai.plugin.security_config import MissingWithSecretWarningPlugin
from linhai.utils import CliRuntimeNotice


class TestMissingWithSecretWarningPlugin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.group_chat = Mock()
        self.group_chat.send_if_exists = AsyncMock(return_value=None)
        self.plugin = MissingWithSecretWarningPlugin(self.group_chat)
        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.group_chat.get_member_typechecked = Mock(
            side_effect=lambda name, t: self.agent
        )

    async def test_warning_when_secret_in_argument_without_with_secret_skipped(self):
        tool_name = "write_file"
        tool_index = 1
        status = "skipped"
        message = None
        toolcall_arguments = {
            "filepath": "config.py",
            "content": "api_key = '<$DEEPSEEK_API_KEY$>'",
        }
        with_secret = None
        is_tool_failed_duplicated_error = False

        result = await self.plugin.on_tool_result(
            tool_name,
            tool_index,
            status,
            message,
            toolcall_arguments,
            with_secret,
            is_tool_failed_duplicated_error,
        )

        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0][0]
        self.assertIn(
            "警告：检测到工具调用参数中包含`<$KEY$>`占位符", call_args.message
        )

    async def test_no_warning_when_secret_in_argument_with_with_secret_skipped(self):
        tool_name = "write_file"
        tool_index = 1
        status = "skipped"
        message = None
        toolcall_arguments = {
            "filepath": "config.py",
            "content": "api_key = '<$DEEPSEEK_API_KEY$>'",
        }
        with_secret = ["DEEPSEEK_API_KEY"]
        is_tool_failed_duplicated_error = False

        result = await self.plugin.on_tool_result(
            tool_name,
            tool_index,
            status,
            message,
            toolcall_arguments,
            with_secret,
            is_tool_failed_duplicated_error,
        )

        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_no_warning_when_no_secret_in_argument_skipped(self):
        tool_name = "write_file"
        tool_index = 1
        status = "skipped"
        message = None
        toolcall_arguments = {"filepath": "config.py", "content": "api_key = '123456'"}
        with_secret = None
        is_tool_failed_duplicated_error = False

        result = await self.plugin.on_tool_result(
            tool_name,
            tool_index,
            status,
            message,
            toolcall_arguments,
            with_secret,
            is_tool_failed_duplicated_error,
        )

        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_warning_when_secret_in_argument_without_with_secret_success(self):
        self.agent.message_processor.reset_mock()
        tool_name = "write_file"
        tool_index = 1
        status = "success"
        message = None
        toolcall_arguments = {
            "filepath": "config.py",
            "content": "api_key = '<$DEEPSEEK_API_KEY$>'",
        }
        with_secret = None
        is_tool_failed_duplicated_error = False

        result = await self.plugin.on_tool_result(
            tool_name,
            tool_index,
            status,
            message,
            toolcall_arguments,
            with_secret,
            is_tool_failed_duplicated_error,
        )

        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0][0]
        self.assertIn(
            "警告：检测到工具调用参数中包含`<$KEY$>`占位符", call_args.message
        )

    async def test_warning_when_secret_in_argument_without_with_secret_failed(self):
        self.agent.message_processor.reset_mock()
        tool_name = "write_file"
        tool_index = 1
        status = "failed"
        message = None
        toolcall_arguments = {
            "filepath": "config.py",
            "content": "api_key = '<$DEEPSEEK_API_KEY$>'",
        }
        with_secret = None
        is_tool_failed_duplicated_error = False

        result = await self.plugin.on_tool_result(
            tool_name,
            tool_index,
            status,
            message,
            toolcall_arguments,
            with_secret,
            is_tool_failed_duplicated_error,
        )

        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0][0]
        self.assertIn(
            "警告：检测到工具调用参数中包含`<$KEY$>`占位符", call_args.message
        )

    def test_register(self):
        lifecycle = Mock()
        self.plugin.register(lifecycle)
        lifecycle.register_on_tool_result.assert_called_once_with(
            self.plugin.on_tool_result
        )


if __name__ == "__main__":
    unittest.main()
