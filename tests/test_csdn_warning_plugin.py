import unittest
import asyncio

from linhai.plugin.message_checkers import CsdnWarningPlugin
from linhai.agent.lifecycle import AfterToolcallResult
from linhai.tool.base import ToolCallResultMessage, SuccessfulToolResult
from linhai.agent.messages import RuntimeMessage


class MockRegistry:
    def __init__(self):
        self.members = {}

    def register_member(self, name, obj):
        self.members[name] = obj

    def get_member_typechecked(self, name, _type=None):
        return self.members.get(name)


class TestCsdnWarningPlugin(unittest.TestCase):
    def setUp(self):
        pass

    def test_plugin_initialization(self):
        registry = MockRegistry()
        plugin = CsdnWarningPlugin(registry)
        self.assertIsNotNone(plugin)

    def test_after_toolcall_skipped_status(self):
        registry = MockRegistry()
        plugin = CsdnWarningPlugin(registry)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="web_search",
                tool_index=0,
                status="skipped",
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
        plugin = CsdnWarningPlugin(registry)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="web_search",
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

    def test_after_toolcall_null_message(self):
        registry = MockRegistry()
        plugin = CsdnWarningPlugin(registry)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="web_search",
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

    def test_after_toolcall_no_csdn(self):
        registry = MockRegistry()
        plugin = CsdnWarningPlugin(registry)

        message = ToolCallResultMessage(
            tool_name="web_search",
            tool_index=0,
            result=SuccessfulToolResult(content="some normal search result"),
            toolcall_arguments={},
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="web_search",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()
        self.assertIsNone(result)

    def test_after_toolcall_has_csdn(self):
        registry = MockRegistry()
        plugin = CsdnWarningPlugin(registry)

        message = ToolCallResultMessage(
            tool_name="web_search",
            tool_index=0,
            result=SuccessfulToolResult(content="CSDN blog article about Python"),
            toolcall_arguments={},
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="web_search",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertEqual(len(result.warnings), 1)
        self.assertIsInstance(result.warnings[0], RuntimeMessage)
        self.assertIn("CSDN", result.warnings[0].message)
        self.assertIn("csdn.net", result.warnings[0].message)

    def test_after_toolcall_csdn_lowercase(self):
        registry = MockRegistry()
        plugin = CsdnWarningPlugin(registry)

        message = ToolCallResultMessage(
            tool_name="web_search",
            tool_index=0,
            result=SuccessfulToolResult(content="check out this csdn article"),
            toolcall_arguments={},
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="web_search",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertEqual(len(result.warnings), 1)

    def test_after_toolcall_csdn_in_url_content(self):
        registry = MockRegistry()
        plugin = CsdnWarningPlugin(registry)

        message = ToolCallResultMessage(
            tool_name="web_search",
            tool_index=0,
            result=SuccessfulToolResult(
                content="https://blog.csdn.net/article/details/12345"
            ),
            toolcall_arguments={},
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="web_search",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()
        self.assertIsInstance(result, AfterToolcallResult)


if __name__ == "__main__":
    unittest.main()
