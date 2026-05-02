"""Tests for tool call manager plugins."""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from linhai.plugin.tool_call_managers import LoadImageUrlWarningPlugin
from linhai.agent import Agent, Lifecycle
from linhai.registry import Registry


class TestLoadImageUrlWarningPlugin(unittest.IsolatedAsyncioTestCase):
    """Test cases for LoadImageUrlWarningPlugin."""

    def setUp(self):
        self.mock_registry = MagicMock(spec=Registry)
        self.mock_agent = MagicMock(spec=Agent)
        self.mock_message_processor = MagicMock()
        self.mock_message_processor.add_new_message = AsyncMock()
        self.mock_lifecycle = MagicMock()

        self.mock_agent.message_processor = self.mock_message_processor
        self.mock_registry.get_member_typechecked = MagicMock(
            return_value=self.mock_agent
        )

        self.plugin = LoadImageUrlWarningPlugin(self.mock_registry)

    async def test_warning_for_http_url(self):
        """Test warning for HTTP URL in load_image parameter."""
        tool_calls = [
            {
                "name": "load_image",
                "arguments": {"image_filepath": "http://example.com/image.jpg"},
            }
        ]

        await self.plugin.after_message_generation(
            parsed_answer=MagicMock(), tool_calls=tool_calls
        )

        self.mock_message_processor.add_new_message.assert_called_once()
        call_args = self.mock_message_processor.add_new_message.call_args[0][0]
        self.assertIn(
            "警告：load_image工具的参数image_filepath看起来是一个URL", call_args.message
        )
        self.assertIn("请先下载图片到master_host", call_args.message)

    async def test_warning_for_https_url(self):
        """Test warning for HTTPS URL in load_image parameter."""
        tool_calls = [
            {
                "name": "load_image",
                "arguments": {"image_filepath": "https://example.com/image.png"},
            }
        ]

        await self.plugin.after_message_generation(
            parsed_answer=MagicMock(), tool_calls=tool_calls
        )

        self.mock_message_processor.add_new_message.assert_called_once()
        call_args = self.mock_message_processor.add_new_message.call_args[0][0]
        self.assertIn("警告", call_args.message)

    async def test_warning_for_ftp_url(self):
        """Test warning for FTP URL in load_image parameter."""
        tool_calls = [
            {
                "name": "load_image",
                "arguments": {"image_filepath": "ftp://example.com/image.gif"},
            }
        ]

        await self.plugin.after_message_generation(
            parsed_answer=MagicMock(), tool_calls=tool_calls
        )

        self.mock_message_processor.add_new_message.assert_called_once()

    async def test_no_warning_for_local_path(self):
        """Test no warning for local file path."""
        tool_calls = [
            {
                "name": "load_image",
                "arguments": {"image_filepath": "/home/user/image.jpg"},
            }
        ]

        await self.plugin.after_message_generation(
            parsed_answer=MagicMock(), tool_calls=tool_calls
        )

        self.mock_message_processor.add_new_message.assert_not_called()

    async def test_no_warning_for_relative_path(self):
        """Test no warning for relative file path."""
        tool_calls = [
            {
                "name": "load_image",
                "arguments": {"image_filepath": "./images/photo.png"},
            }
        ]

        await self.plugin.after_message_generation(
            parsed_answer=MagicMock(), tool_calls=tool_calls
        )

        self.mock_message_processor.add_new_message.assert_not_called()

    async def test_ignore_other_tools(self):
        """Test that other tools are ignored."""
        tool_calls = [
            {
                "name": "fetch_webpage",
                "arguments": {
                    "url": "http://example.com",
                    "http_downloader": "chromium",
                },
            },
            {"name": "read_file", "arguments": {"filepath": "/etc/passwd"}},
        ]

        await self.plugin.after_message_generation(
            parsed_answer=MagicMock(), tool_calls=tool_calls
        )

        self.mock_message_processor.add_new_message.assert_not_called()

    def test_register(self):
        """Test plugin registration."""
        self.plugin.register(self.mock_lifecycle)
        self.mock_lifecycle.after_message_generation.register.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()
