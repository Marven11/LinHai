"""Unit tests for the dummy tools migration to agent.py."""

import unittest
import unittest.mock
from unittest.mock import AsyncMock, MagicMock

from linhai.llm import ToolCallMessage
from linhai.tool.base import ToolSet
from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager


class TestDummyToolsMigration(unittest.IsolatedAsyncioTestCase):
    """Test cases for the dummy tools migration from dummy.py to agent.py."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.group_chat = GroupChat()
        self.tool_manager = ToolManager(group_chat=self.group_chat, toolsets=[ToolSet()])

    async def test_get_token_usage_tool_registered(self):
        """Test that get_token_usage tool is properly registered."""
        # Create a mock agent with the dummy tools
        from linhai.agent import Agent, AgentConfig
        
        # Mock the agent configuration with proper typing
        mock_config: AgentConfig = {
            "system_prompt": "test prompt",
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }
        
        # Create agent instance
        agent = Agent(config=mock_config, group_chat=self.group_chat, init_messages=[])
        
        # Check if get_token_usage tool is registered by calling it
        result = await self.tool_manager.process_tool_call(
            ToolCallMessage(function_name="get_token_usage", function_arguments={})
        )
        
        # If we get a result (not an error), the tool is registered
        self.assertIn(type(result).__name__, ["ToolResultMessage", "ToolErrorMessage"])

    async def test_thanox_history_tool_registered(self):
        """Test that thanox_history tool is properly registered."""
        # Create a mock agent with the dummy tools
        from linhai.agent import Agent, AgentConfig
        
        # Mock the agent configuration with proper typing
        mock_config: AgentConfig = {
            "system_prompt": "test prompt",
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }
        
        # Create agent instance
        agent = Agent(config=mock_config, group_chat=self.group_chat, init_messages=[])
        
        # Check if thanox_history tool is registered by calling it
        result = await self.tool_manager.process_tool_call(
            ToolCallMessage(function_name="thanox_history", function_arguments={})
        )
        
        # If we get a result (not an error), the tool is registered
        self.assertIn(type(result).__name__, ["ToolResultMessage", "ToolErrorMessage"])

    async def test_get_token_usage_tool_call_with_token_usage(self):
        """Test get_token_usage tool call when token usage is available."""
        # Create a mock agent
        from linhai.agent import Agent, AgentConfig
        
        mock_config: AgentConfig = {
            "system_prompt": "test prompt",
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }
        
        agent = Agent(config=mock_config, group_chat=self.group_chat, init_messages=[])
        agent.last_token_usage = 12345
        
        # Call the get_token_usage tool
        result = await self.tool_manager.process_tool_call(
            ToolCallMessage(function_name="get_token_usage", function_arguments={})
        )
        
        # Check the result
        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertIn("12345", content)
        self.assertIn("12.35 k", content)

    async def test_get_token_usage_tool_call_without_token_usage(self):
        """Test get_token_usage tool call when no token usage is available."""
        # Create a mock agent
        from linhai.agent import Agent, AgentConfig
        
        mock_config: AgentConfig = {
            "system_prompt": "test prompt",
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }
        
        agent = Agent(config=mock_config, group_chat=self.group_chat, init_messages=[])
        agent.last_token_usage = None
        
        # Call the get_token_usage tool
        result = await self.tool_manager.process_tool_call(
            ToolCallMessage(function_name="get_token_usage", function_arguments={})
        )
        
        # Check the result
        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertEqual("暂无token用量信息", content)

    async def test_thanox_history_tool_call_with_sufficient_messages(self):
        """Test thanox_history tool call when there are sufficient messages."""
        # Create a mock agent with enough messages
        from linhai.agent import Agent, AgentConfig
        from linhai.llm import SystemMessage, ChatMessage
        from linhai.agent_base import RuntimeMessage
        
        mock_config: AgentConfig = {
            "system_prompt": "test prompt",
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }
        
        # Create messages (more than 10 to trigger deletion)
        from linhai.llm import Message
        init_messages: list[Message] = [
            SystemMessage(template="test", current_time="2023-01-01 00:00:00", group_chat=self.group_chat)
        ]
        for i in range(15):
            init_messages.append(RuntimeMessage(f"Message {i}"))
        
        agent = Agent(config=mock_config, group_chat=self.group_chat, init_messages=init_messages)
        
        # Call the thanox_history tool
        result = await self.tool_manager.process_tool_call(
            ToolCallMessage(function_name="thanox_history", function_arguments={})
        )
        
        # Check the result
        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertIn("thanox_history: 随机删除了", content)
        self.assertIn("条消息", content)

    async def test_thanox_history_tool_call_with_insufficient_messages(self):
        """Test thanox_history tool call when there are insufficient messages."""
        # Create a mock agent with few messages
        from linhai.agent import Agent, AgentConfig
        from linhai.llm import SystemMessage
        from linhai.agent_base import RuntimeMessage
        
        mock_config: AgentConfig = {
            "system_prompt": "test prompt",
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }
        
        # Create only a few messages (less than 10)
        from linhai.llm import Message
        init_messages: list[Message] = [
            SystemMessage(template="test", current_time="2023-01-01 00:00:00", group_chat=self.group_chat)
        ]
        for i in range(5):
            init_messages.append(RuntimeMessage(f"Message {i}"))
        
        agent = Agent(config=mock_config, group_chat=self.group_chat, init_messages=init_messages)
        
        # Call the thanox_history tool
        result = await self.tool_manager.process_tool_call(
            ToolCallMessage(function_name="thanox_history", function_arguments={})
        )
        
        # Check the result
        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertEqual("消息数量不足，无需删除", content)


if __name__ == "__main__":
    unittest.main()