"""Unit tests for agent workflow functionality."""

import asyncio
import reprlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import cast

# 创建自定义repr函数，限制长度为200字符
r = reprlib.Repr()
r.maxstring = 200
custom_repr = r.repr

def format_messages_for_assert(messages):
    """格式化消息列表用于断言错误信息"""
    return f"Messages: {[f'{type(msg).__name__}: {custom_repr(msg)}' for msg in messages]}"

from linhai.agent import Agent, AgentConfig
from linhai.agent_base import RuntimeMessage
from linhai.agent_workflow import compress_history_range
from linhai.llm import ChatMessage
from linhai.tool.main import ToolManager


class TestAgentWorkflow(unittest.IsolatedAsyncioTestCase):
    """Test cases for agent workflow integration and functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock()

        config: AgentConfig = {
            "system_prompt": "Test system prompt",
            "model": self.mock_llm,
            "compress_threshold_soft": 500,
            "compress_threshold_hard": 800,
            "tool_confirmation": {
                "skip_confirmation": True,
                "whitelist": [],
            },
        }

        self.user_input_queue = asyncio.Queue()
        self.user_output_queue = asyncio.Queue()
        self.tool_request_queue = asyncio.Queue()
        self.tool_confirmation_queue = asyncio.Queue()
        self.tool_manager = ToolManager()

        self.agent = Agent(
            config=config,
            init_messages=[],
            user_input_queue=cast(asyncio.Queue, self.user_input_queue),
            user_output_queue=cast(asyncio.Queue, self.user_output_queue),
            tool_request_queue=cast(asyncio.Queue, self.tool_request_queue),
            tool_confirmation_queue=cast(asyncio.Queue, self.tool_confirmation_queue),
            tool_manager=self.tool_manager,
        )

    async def test_workflow_registration(self):
        """Test that compress_history_range workflow is properly registered."""
        # Register the workflow
        self.tool_manager.register_workflow(
            "compress_history_range",
            "压缩指定范围的历史消息：总结并删除指定范围内的消息。调用这个工具来开始压缩指定范围的流程。",
            compress_history_range,
        )

        # Check if workflow is registered
        workflow = self.tool_manager.get_workflow("compress_history_range")
        self.assertIsNotNone(workflow)
        assert workflow is not None  # 确保类型检查器知道workflow不是None
        self.assertEqual(workflow["func"], compress_history_range)
        self.assertIn("压缩指定范围的历史消息", workflow["desc"])

    async def test_workflow_call_via_tool(self):
        """Test calling workflow through tool call mechanism."""
        # Create a mock workflow function
        mock_workflow = AsyncMock(return_value=True)

        # Register the workflow with the mock function
        self.tool_manager.register_workflow(
            "compress_history_range",
            "Test workflow",
            mock_workflow,
        )

        # Mock the tool call
        mock_tool_call = MagicMock()
        mock_tool_call.function_name = "compress_history_range"

        # Call the tool
        result = await self.agent.call_tool(mock_tool_call)

        # Verify workflow was called
        mock_workflow.assert_called_once_with(self.agent)
        self.assertTrue(result)

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

    async def test_compress_threshold_trigger(self):
        """Test that compression is triggered when token threshold is exceeded."""
        # Set token usage above hard threshold
        self.agent.last_token_usage = 60000  # Above default hard threshold (52428)

        # Mock the compress_history_range function
        with patch(
            "linhai.agent.compress_history_range", AsyncMock(return_value=True)
        ) as mock_compress:
            # Mock generate_response to avoid errors
            with patch.object(self.agent, "generate_response", AsyncMock()):
                # Call state_working which should trigger compression
                await self.agent.state_working()

                # Verify compression was triggered
                mock_compress.assert_called_once()

    async def test_workflow_with_invalid_range(self):
        """Test compress_history_range with invalid range parameters."""
        mock_agent = MagicMock()
        mock_agent.messages = [RuntimeMessage(f"Message {i}") for i in range(20)]

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

    async def test_tool_manager_workflow_registration(self):
        """Test ToolManager workflow registration functionality."""
        # Test registering a workflow
        mock_workflow = AsyncMock(return_value=True)

        self.tool_manager.register_workflow(
            "test_workflow", "A test workflow", mock_workflow
        )

        # Verify workflow is registered
        workflow = self.tool_manager.get_workflow("test_workflow")
        self.assertIsNotNone(workflow)
        assert workflow is not None
        self.assertEqual(workflow["func"], mock_workflow)
        self.assertEqual(workflow["desc"], "A test workflow")

        # Test getting non-existent workflow
        self.assertIsNone(self.tool_manager.get_workflow("non_existent_workflow"))

    async def test_tool_manager_get_tools_info_includes_workflows(self):
        """Test that get_tools_info includes both global tools and workflows."""
        # Register a workflow
        mock_workflow = AsyncMock(return_value=True)
        self.tool_manager.register_workflow(
            "test_workflow", "A test workflow", mock_workflow
        )

        # Get tools info
        tools_info = self.tool_manager.get_tools_info()

        # Should include both global tools and workflows
        workflow_names = [tool["function"]["name"] for tool in tools_info]

        # Check that our workflow is included
        self.assertIn("test_workflow", workflow_names)

        # Also check that some global tools are present
        self.assertTrue(any("safe_calculator" in name for name in workflow_names))

    async def test_workflow_priority_over_global_tool(self):
        """Test that workflow takes priority over global tool with same name."""
        # Register a workflow with a name that might conflict with global tools
        mock_workflow = AsyncMock(return_value=True)
        self.tool_manager.register_workflow(
            "add_numbers",  # This name exists in global tools
            "Workflow version of add_numbers",
            mock_workflow,
        )

        # Get the workflow (should get the workflow, not the global tool)
        workflow = self.tool_manager.get_workflow("add_numbers")
        self.assertIsNotNone(workflow)
        assert workflow is not None
        self.assertEqual(workflow["func"], mock_workflow)
        self.assertEqual(workflow["desc"], "Workflow version of add_numbers")

    async def test_workflow_in_tools_info_has_correct_structure(self):
        """Test that workflows in tools info have correct OpenAI tool structure."""
        # Register a workflow
        mock_workflow = AsyncMock(return_value=True)
        self.tool_manager.register_workflow(
            "test_workflow", "A test workflow description", mock_workflow
        )

        # Get tools info
        tools_info = self.tool_manager.get_tools_info()

        # Find our workflow
        workflow_info = None
        for tool in tools_info:
            if tool["function"]["name"] == "test_workflow":
                workflow_info = tool
                break

        self.assertIsNotNone(workflow_info)
        assert workflow_info is not None

        # Check structure
        self.assertEqual(workflow_info["type"], "function")
        self.assertEqual(workflow_info["function"]["name"], "test_workflow")
        self.assertEqual(
            workflow_info["function"]["description"], "A test workflow description"
        )
        self.assertEqual(workflow_info["function"]["parameters"]["type"], "object")
        self.assertEqual(workflow_info["function"]["parameters"]["properties"], {})
        self.assertEqual(workflow_info["function"]["parameters"]["required"], [])

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
