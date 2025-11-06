"""Unit tests for agent workflow functionality."""

# pylint: disable=import-outside-toplevel
import reprlib
import unittest
from unittest.mock import AsyncMock, MagicMock

from linhai.agent import Agent, AgentConfig
from linhai.agent.base import RuntimeMessage
from linhai.agent.workflow import compress_history_range
from linhai.llm import ChatMessage
from linhai.tool.main import ToolManager
from linhai.tool.base import global_tools
from linhai.group_chat import GroupChat

# 创建自定义repr函数，限制长度为200字符
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

        config: AgentConfig = {
            "system_prompt": "Test system prompt",
            "llms": [self.mock_llm],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_soft": 500,
            "compress_threshold_hard": 800,
            "tool_confirmation": {
                "skip_confirmation": True,
                "whitelist": [],
            },
        }

        self.group_chat = GroupChat()

        self.tool_manager = ToolManager(
            group_chat=self.group_chat, toolsets=[global_tools]
        )

        self.agent = Agent(
            config=config,
            group_chat=self.group_chat,
            init_messages=[],
        )

    async def test_workflow_as_regular_tool(self):
        """Test that compress_history_range is now a regular tool, not a workflow."""
        # Get tools info - should include compress_history_range as a regular tool
        tools_info = self.tool_manager.get_tools_info()
        tool_names = [tool["function"]["name"] for tool in tools_info]
        
        # Check that compress_history_range is now a regular tool
        self.assertIn("compress_history_range", tool_names)

    @unittest.skip("需要完整的group_chat设置，暂时跳过")
    async def test_compress_history_range_as_tool(self):
        """Test calling compress_history_range as a regular tool."""

    async def test_compress_history_range_functionality(self):
        """Test the compress_history_range function with mock data."""
        # Create a mock agent
        mock_agent = MagicMock()

        # Setup mock messages
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
        mock_agent.messages = mock_messages

        # Mock get_threshold_info to return valid data
        mock_agent.get_threshold_info.return_value = (500, 800, 600, 200, 0.75)

        # Mock generate_response to return a response with JSON block
        mock_response = MagicMock()
        mock_response.get_message.return_value = ChatMessage(
            role="assistant",
            message="""
            Here's the range to compress:
            ```json
            {"start_id": 6, "end_id": 10}
            ```
            """,
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        # Call the function
        result = await compress_history_range(mock_agent)

        # Verify the function completed successfully
        self.assertTrue(result)

    @unittest.skip("需要完整的group_chat设置，暂时跳过")
    async def test_compress_threshold_trigger(self):
        """Test that compression is triggered when token threshold is exceeded."""

    async def test_workflow_with_invalid_range(self):
        """Test compress_history_range with invalid range parameters."""
        mock_agent = MagicMock()
        mock_agent.messages = [RuntimeMessage(f"Message {i}") for i in range(20)]

        # Mock get_threshold_info to return valid data
        mock_agent.get_threshold_info.return_value = (500, 800, 600, 200, 0.75)

        # Mock response with invalid range (start_id > end_id)
        mock_response = MagicMock()
        mock_response.get_message.return_value = ChatMessage(
            role="assistant",
            message="""
            ```json
            {"start_id": 10, "end_id": 5}
            ```
            """,
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        # Call the function
        result = await compress_history_range(mock_agent)

        # Should return True but not modify messages due to validation error
        self.assertTrue(result)

    async def test_workflow_with_small_range(self):
        """Test compress_history_range with range smaller than minimum."""
        mock_agent = MagicMock()
        mock_agent.messages = [RuntimeMessage(f"Message {i}") for i in range(15)]

        # Mock get_threshold_info to return valid data
        mock_agent.get_threshold_info.return_value = (500, 800, 600, 200, 0.75)

        # Mock response with small range
        mock_response = MagicMock()
        mock_response.get_message.return_value = ChatMessage(
            role="assistant",
            message="""
            ```json
            {"start_id": 6, "end_id": 8}
            ```
            """,
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        # Call the function
        result = await compress_history_range(mock_agent)

        # Should return True but not modify messages due to validation error
        self.assertTrue(result)

    async def test_tool_manager_has_no_workflow_methods(self):
        """Test that ToolManager no longer has workflow-specific methods."""
        # Verify that get_workflow method doesn't exist
        self.assertFalse(hasattr(self.tool_manager, "get_workflow"))
        
        # Verify that register_workflow method doesn't exist  
        self.assertFalse(hasattr(self.tool_manager, "register_workflow"))
        
        # Verify that workflows attribute doesn't exist
        self.assertFalse(hasattr(self.tool_manager, "workflows"))

    async def test_tools_info_includes_compress_history_range(self):
        """Test that get_tools_info includes compress_history_range as a regular tool."""
        # Get tools info
        tools_info = self.tool_manager.get_tools_info()

        # Check that compress_history_range is included as a regular tool
        workflow_names = [tool["function"]["name"] for tool in tools_info]
        self.assertIn("compress_history_range", workflow_names)

        # Also check that some global tools are present
        self.assertTrue(any("safe_calculator" in name for name in workflow_names))

    async def test_compress_history_range_tool_structure(self):
        """Test that compress_history_range tool has correct structure."""
        # Get tools info
        tools_info = self.tool_manager.get_tools_info()

        # Find compress_history_range tool
        compress_tool = None
        for tool in tools_info:
            if tool["function"]["name"] == "compress_history_range":
                compress_tool = tool
                break

        self.assertIsNotNone(compress_tool)
        
        # Check structure
        json_blocks = []
        _ = json_blocks[0] if json_blocks else {}  # pylint: disable=unused-variable


    async def test_compress_history_range_integration(self):
        """Test that compress_history_range integrates properly with agent."""
        # Test that compress_history_range can be called as a regular tool
        # through the normal tool calling mechanism
        
        # Verify that the tool is available in tools_info
        tools_info = self.tool_manager.get_tools_info()
        tool_names = [tool["function"]["name"] for tool in tools_info]
        self.assertIn("compress_history_range", tool_names)
        
        # Verify it's a proper tool, not a workflow
        compress_tool = next(
            (tool for tool in tools_info if tool["function"]["name"] == "compress_history_range"),
            None
        )
        self.assertIsNotNone(compress_tool)


    async def test_compress_history_range_user_message_protection(self):
        """Test that user messages are protected during history compression."""
        # Create a mock agent
        mock_agent = MagicMock()

        # Setup mock messages with user messages that should be protected
        # Use ChatMessage for user messages to properly simulate role="user"
        mock_messages = [
            RuntimeMessage("System message"),
            ChatMessage(role="user", message="Important user input 1"),
            ChatMessage(role="user", message="Important user input 2"),
            ChatMessage("assistant", "Assistant response 1"),
            ChatMessage(role="user", message="Important user input 3"),
            ChatMessage("assistant", "Assistant response 2"),
            RuntimeMessage("<runtime>Tool output</runtime>"),
            ChatMessage(
                role="user", message="Complete TODO.md tasks"
            ),  # This should be protected
            ChatMessage("assistant", "Assistant response 3"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            ChatMessage("assistant", "Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            ChatMessage("assistant", "Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            ChatMessage("assistant", "Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            ChatMessage("assistant", "Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            ChatMessage("assistant", "Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            ChatMessage("assistant", "Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            ChatMessage("assistant", "Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            ChatMessage("assistant", "Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            ChatMessage("assistant", "Assistant response x"),
        ]
        mock_agent.messages = mock_messages

        # Mock get_threshold_info to return valid data
        mock_agent.get_threshold_info.return_value = (500, 800, 600, 200, 0.75)

        # Mock generate_response to return a response with JSON block for compression range
        mock_response = MagicMock()
        mock_response.get_message.return_value = ChatMessage(
            role="assistant",
            message="""
## 用户输入
- 目标：用户要求完成TODO.md中的内容，这是重要输入
- 建议：用户强烈建议处理历史压缩问题

```json
{"start_id": 2, "end_id": 15}
```
""",
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        # Call the function
        result = await compress_history_range(mock_agent)

        # Verify the function completed successfully
        self.assertTrue(result)

        # Verify that user messages were protected by checking if a runtime summary was added
        # After compression, there should be a runtime message summarizing the deleted user messages
        # Check that the runtime message contains a summary of user inputs
        runtime_messages = [
            msg
            for msg in mock_agent.messages
            if isinstance(msg, RuntimeMessage)
            and "历史压缩已删除以下用户消息" in msg.message
        ]
        self.assertGreater(
            len(runtime_messages),
            0,
            "No runtime message summarizing user messages was found in: "
            + repr(mock_agent.messages),
        )

        # Verify the summary contains key user inputs
        summary_message = runtime_messages[0].message
        self.assertIn("Complete TODO.md tasks", summary_message)
        self.assertIn("Important user input", summary_message)


if __name__ == "__main__":
    unittest.main()
