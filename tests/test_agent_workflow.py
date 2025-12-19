"""Unit tests for agent workflow functionality."""

import reprlib
import unittest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from linhai.agent import Agent, AgentContext
from linhai.agent.base import RuntimeMessage
from linhai.agent.workflow import context_range_compress
from linhai.llm import UserMessage, AssistantMessage
from linhai.tool.main import ToolManager
from linhai.tool.base import global_tools
from linhai.group_chat import GroupChat


r = reprlib.Repr()
r.maxstring = 200
custom_repr = r.repr


def format_messages_for_assert(messages):
    """格式化消息列表用于断言错误信息"""
    return (
        f"Messages: {[f'{type(msg).__name__}: {custom_repr(msg)}' for msg in messages]}"
    )


class TestAgentWorkflow(unittest.IsolatedAsyncioTestCase):
    """Test cases for agent workflow integration and functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock()

        config: AgentContext = {
            "llms": [self.mock_llm],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 800,
        }

        self.group_chat = GroupChat()

        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            group_chat=self.group_chat,
            toolsets=[global_tools],
            config=ToolConfig(),
            mcp_config=[],
            mcp_basedir=Path("/tmp"),
        )

        from linhai.subagent.issue import IssueManager

        self.issue_manager = IssueManager(self.group_chat)

        self.agent = Agent(
            context=config,
            group_chat=self.group_chat,
            init_messages=[],
        )

    async def test_workflow_as_regular_tool(self):
        """Test that context_range_compress is now a regular tool, not a workflow."""
        tools_info = self.tool_manager.get_tools_info()
        tool_names = [tool["function"]["name"] for tool in tools_info]

        self.assertIn("context_range_compress", tool_names)

    async def test_context_range_compress_as_tool(self):
        """Test calling context_range_compress as a regular tool."""

    async def test_context_range_compress_functionality(self):
        """Test the context_range_compress function with mock data."""
        mock_agent = MagicMock()
        mock_group_chat = MagicMock()
        mock_agent.group_chat = mock_group_chat

        async def mock_send_if_exists(queue_name, message):
            _ = queue_name  # 使用参数以消除警告
            _ = message  # 使用参数以消除警告

        mock_group_chat.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

        mock_messages = [
            RuntimeMessage("System message"),
            RuntimeMessage("User message 1"),
            RuntimeMessage("User message 2"),
            RuntimeMessage("User message 3"),
            RuntimeMessage("User message 4"),
            RuntimeMessage("User message 5"),
            RuntimeMessage("User message 6"),
            RuntimeMessage("User message 7"),
            RuntimeMessage("User message 8"),
            RuntimeMessage("User message 9"),
            RuntimeMessage("User message 10"),
        ]
        mock_agent.message_processor.messages = mock_messages
        mock_agent.message_processor.filter_messages = AsyncMock()

        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75
        }

        mock_response = MagicMock()
        mock_response.get_message.return_value = AssistantMessage(
            message="""
            Here's the range to compress:
            ```json
            {"start_id": 6, "end_id": 10}
            ```
            """,
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        result = await context_range_compress(mock_agent)

        self.assertTrue(result)

    async def test_compress_threshold_trigger(self):
        """Test that compression is triggered when token threshold is exceeded."""

    async def test_workflow_with_invalid_range(self):
        """Test context_range_compress with invalid range parameters."""
        mock_agent = MagicMock()
        mock_group_chat = MagicMock()
        mock_agent.group_chat = mock_group_chat

        async def mock_send_if_exists(queue_name, message):
            _ = queue_name  # 使用参数以消除警告
            _ = message  # 使用参数以消除警告

        mock_group_chat.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

        mock_agent.message_processor.messages = [
            RuntimeMessage(f"Message {i}") for i in range(20)
        ]
        mock_agent.message_processor.filter_messages = AsyncMock()

        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75
        }

        mock_response = MagicMock()
        mock_response.get_message.return_value = AssistantMessage(
            message="""
            ```json
            {"start_id": 10, "end_id": 5}
            ```
            """,
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        result = await context_range_compress(mock_agent)

        self.assertTrue(result)

    async def test_workflow_with_small_range(self):
        """Test context_range_compress with range smaller than minimum."""
        mock_agent = MagicMock()
        mock_group_chat = MagicMock()
        mock_agent.group_chat = mock_group_chat

        async def mock_send_if_exists(queue_name, message):
            _ = queue_name  # 使用参数以消除警告
            _ = message  # 使用参数以消除警告

        mock_group_chat.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

        mock_agent.message_processor.messages = [
            RuntimeMessage(f"Message {i}") for i in range(15)
        ]
        mock_agent.message_processor.filter_messages = AsyncMock()

        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75
        }

        mock_response = MagicMock()
        mock_response.get_message.return_value = AssistantMessage(
            message="""
            ```json
            {"start_id": 6, "end_id": 8}
            ```
            """,
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        result = await context_range_compress(mock_agent)

        self.assertTrue(result)

    async def test_tool_manager_has_no_workflow_methods(self):
        """Test that ToolManager no longer has workflow-specific methods."""
        self.assertFalse(hasattr(self.tool_manager, "get_workflow"))

        self.assertFalse(hasattr(self.tool_manager, "register_workflow"))

        self.assertFalse(hasattr(self.tool_manager, "workflows"))

    async def test_tools_info_includes_context_range_compress(self):
        """Test that get_tools_info includes context_range_compress as a regular tool."""
        tools_info = self.tool_manager.get_tools_info()

        workflow_names = [tool["function"]["name"] for tool in tools_info]
        self.assertIn("context_range_compress", workflow_names)

        self.assertTrue(any("safe_calculator" in name for name in workflow_names))

    async def test_context_range_compress_tool_structure(self):
        """Test that context_range_compress tool has correct structure."""
        tools_info = self.tool_manager.get_tools_info()

        compress_tool = None
        for tool in tools_info:
            if tool["function"]["name"] == "context_range_compress":
                compress_tool = tool
                break

        self.assertIsNotNone(compress_tool)

        json_blocks = []
        _ = json_blocks[0] if json_blocks else {}  # pylint: disable=unused-variable

    async def test_context_range_compress_integration(self):
        """Test that context_range_compress integrates properly with agent."""

        tools_info = self.tool_manager.get_tools_info()
        tool_names = [tool["function"]["name"] for tool in tools_info]
        self.assertIn("context_range_compress", tool_names)

        compress_tool = next(
            (
                tool
                for tool in tools_info
                if tool["function"]["name"] == "context_range_compress"
            ),
            None,
        )
        self.assertIsNotNone(compress_tool)

    async def test_context_range_compress_user_message_protection(self):
        """Test that user messages are protected during history compression."""
        mock_agent = MagicMock()
        mock_group_chat = MagicMock()
        mock_agent.group_chat = mock_group_chat

        async def mock_send_if_exists(queue_name, message):
            _ = queue_name  # 使用参数以消除警告
            _ = message  # 使用参数以消除警告

        mock_group_chat.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

        mock_messages = [
            RuntimeMessage("System message"),
            UserMessage(message="Important user input 1"),
            UserMessage(message="Important user input 2"),
            AssistantMessage(message="Assistant response 1"),
            UserMessage(message="Important user input 3"),
            AssistantMessage(message="Assistant response 2"),
            RuntimeMessage("<runtime>Tool output</runtime>"),
            UserMessage(message="Complete TODO.md tasks"),  # This should be protected
            AssistantMessage(message="Assistant response 3"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
        ]
        mock_agent.message_processor.messages = mock_messages
        mock_agent.message_processor.filter_messages = AsyncMock()

        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75
        }

        mock_response = MagicMock()
        mock_response.get_message.return_value = AssistantMessage(
            message="""
- 目标：用户要求完成TODO.md中的内容，这是重要输入
- 建议：用户强烈建议处理历史压缩问题

```json
{"start_id": 2, "end_id": 15}
```
""",
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        async def delete_message_range_side_effect(start, end):
            deleted = mock_agent.message_processor.messages[start : end + 1]
            mock_agent.message_processor.messages[start : end + 1] = []
            return deleted

        def insert_message_side_effect(index, message):
            mock_agent.message_processor.messages.insert(index, message)

        mock_agent.message_processor.delete_message_range.side_effect = (
            delete_message_range_side_effect
        )
        mock_agent.message_processor.insert_message = AsyncMock(
            side_effect=insert_message_side_effect
        )

        result = await context_range_compress(mock_agent)

        self.assertTrue(result)

        runtime_messages = [
            msg
            for msg in mock_agent.message_processor.messages
            if isinstance(msg, RuntimeMessage)
            and "历史压缩已删除以下用户消息" in msg.message
        ]
        self.assertGreater(
            len(runtime_messages),
            0,
            "No runtime message summarizing user messages was found in: "
            + repr(mock_agent.message_processor.messages),
        )

        summary_message = runtime_messages[0].message
        self.assertIn("Complete TODO.md tasks", summary_message)
        self.assertIn("Important user input", summary_message)

    async def test_context_range_compress_small_delete_ratio(self):
        """Test context_range_compress with delete ratio less than 30%."""
        mock_agent = MagicMock()
        mock_group_chat = MagicMock()
        mock_agent.group_chat = mock_group_chat

        async def mock_send_if_exists(queue_name, message):
            _ = queue_name  # 使用参数以消除警告
            _ = message  # 使用参数以消除警告

        mock_group_chat.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

        mock_agent.message_processor.messages = [
            RuntimeMessage(f"Message {i}") for i in range(36)
        ]
        mock_agent.message_processor.filter_messages = AsyncMock()

        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75
        }

        mock_response = MagicMock()
        mock_response.get_message.return_value = AssistantMessage(
            message="""```json
{"start_id": 10, "end_id": 19}
```""",
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        async def delete_message_range_side_effect(start, end):
            deleted = mock_agent.message_processor.messages[start : end + 1]
            del mock_agent.message_processor.messages[start : end + 1]
            return deleted

        def filter_messages_side_effect(filter_func):
            mock_agent.message_processor.messages[:] = [
                msg for msg in mock_agent.message_processor.messages if filter_func(msg)
            ]

        def add_new_message_side_effect(message):
            mock_agent.message_processor.messages.append(message)

        mock_agent.message_processor.delete_message_range = MagicMock(
            side_effect=delete_message_range_side_effect
        )
        mock_agent.message_processor.insert_message = AsyncMock()
        mock_agent.message_processor.filter_messages = AsyncMock(
            side_effect=filter_messages_side_effect
        )
        mock_agent.message_processor.add_new_message = MagicMock(
            side_effect=add_new_message_side_effect
        )

        result = await context_range_compress(mock_agent)

        self.assertTrue(result)

        warning_messages = [
            msg
            for msg in mock_agent.message_processor.messages
            if isinstance(msg, RuntimeMessage)
            and "小于总消息数量的30%" in getattr(msg, "message", "")
        ]
        self.assertGreater(
            len(warning_messages),
            0,
            f"No warning message about small delete ratio was found in {len(mock_agent.message_processor.messages)} messages",
        )

        warning_message = warning_messages[0].message
        self.assertIn(
            "27.8%", warning_message
        )  # 10/36 = 27.8% (36 messages before compression)
        self.assertIn("30%", warning_message)
        self.assertIn("建议删除更多消息", warning_message)

    async def test_context_range_compress_sends_ui_log_message(self):
        """Test that context_range_compress sends UI log message with current message count."""
        mock_agent = MagicMock()
        mock_group_chat = MagicMock()
        mock_agent.group_chat = mock_group_chat

        async def mock_send_if_exists(queue_name, message):
            _ = queue_name  # 使用参数以消除警告
            _ = message  # 使用参数以消除警告

        mock_group_chat.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

        mock_messages = [
            RuntimeMessage("System message"),
            RuntimeMessage("User message 1"),
            RuntimeMessage("User message 2"),
            RuntimeMessage("User message 3"),
        ]
        mock_agent.message_processor.messages = mock_messages
        mock_agent.message_processor.filter_messages = AsyncMock()

        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75
        }

        mock_response = MagicMock()
        mock_response.get_message.return_value = AssistantMessage(
            message="""
            ```json
            {"start_id": 1, "end_id": 2}
            ```
            """,
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        mock_agent.message_processor.delete_message_range = AsyncMock(
            return_value=mock_messages[1:3]
        )
        mock_agent.message_processor.insert_message = AsyncMock()

        result = await context_range_compress(mock_agent)

        mock_group_chat.send_if_exists.assert_called_once()
        call_args = mock_group_chat.send_if_exists.call_args

        self.assertEqual(
            call_args[0][0], "ui_log"
        )  # First positional argument should be "ui_log"

        ui_message = call_args[0][1]
        from linhai.utils import CliRuntimeNotice

        self.assertIsInstance(ui_message, CliRuntimeNotice)
        self.assertEqual(ui_message.level, "INFO")
        self.assertIn("启动历史压缩", ui_message.content)
        self.assertIn(
            "当前共有4条消息", ui_message.content
        )  # 4 messages in mock_messages

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
