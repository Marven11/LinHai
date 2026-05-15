import unittest
import asyncio
from unittest.mock import Mock

from linhai.plugin.message_checkers import HackerNewsPlugin
from linhai.agent.lifecycle import AfterToolcallResult
from linhai.tool.base import (
    ToolCallResultMessage,
    WebpageFetchToolResult,
    SuccessfulToolResult,
)


class MockRegistry:
    def __init__(self):
        self.members = {}

    def register_member(self, name, obj):
        self.members[name] = obj

    def get_member_typechecked(self, name, _type=None):
        return self.members.get(name)


class TestHackerNewsPlugin(unittest.TestCase):
    def setUp(self):
        pass

    def test_plugin_initialization(self):
        registry = MockRegistry()
        plugin = HackerNewsPlugin(registry)
        self.assertIsNotNone(plugin)

    def test_after_toolcall_non_fetch_webpage(self):
        registry = MockRegistry()
        plugin = HackerNewsPlugin(registry)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="read_file",
                tool_index=0,
                status="success",
                message=None,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()
        self.assertIsNone(result)

    def test_after_toolcall_failed_status(self):
        registry = MockRegistry()
        plugin = HackerNewsPlugin(registry)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="fetch_webpage",
                tool_index=0,
                status="failed",
                message=None,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()
        self.assertIsNone(result)

    def test_after_toolcall_non_webpage_result(self):
        registry = MockRegistry()
        plugin = HackerNewsPlugin(registry)

        message = ToolCallResultMessage(
            tool_name="fetch_webpage",
            tool_index=0,
            result=SuccessfulToolResult(content="test"),
            toolcall_arguments={"url": "https://news.ycombinator.com/item?id=1"},
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="fetch_webpage",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={"url": "https://news.ycombinator.com/item?id=1"},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()
        self.assertIsNone(result)

    def test_after_toolcall_non_hacker_news_url(self):
        registry = MockRegistry()
        plugin = HackerNewsPlugin(registry)

        message = ToolCallResultMessage(
            tool_name="fetch_webpage",
            tool_index=0,
            result=WebpageFetchToolResult(
                html_path="/tmp/test.html",
                md_path="/tmp/test.md",
                content="test content",
            ),
            toolcall_arguments={"url": "https://example.com"},
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="fetch_webpage",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={"url": "https://example.com"},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()
        self.assertIsNone(result)

    def test_after_toolcall_hacker_news_url(self):
        registry = MockRegistry()
        plugin = HackerNewsPlugin(registry)

        message = ToolCallResultMessage(
            tool_name="fetch_webpage",
            tool_index=0,
            result=WebpageFetchToolResult(
                html_path="/tmp/test.html",
                md_path="/tmp/test.md",
                content="test content",
            ),
            toolcall_arguments={"url": "https://news.ycombinator.com/item?id=47994012"},
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="fetch_webpage",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={
                    "url": "https://news.ycombinator.com/item?id=47994012"
                },
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertEqual(len(result.warnings), 1)
        warning_content = result.warnings[0].message
        self.assertIn("hacker news", warning_content)
        self.assertIn("/tmp/test.html", warning_content)

    def test_after_toolcall_skipped_status(self):
        registry = MockRegistry()
        plugin = HackerNewsPlugin(registry)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="fetch_webpage",
                tool_index=0,
                status="skipped",
                message=None,
                toolcall_arguments={"url": "https://news.ycombinator.com/item?id=1"},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
