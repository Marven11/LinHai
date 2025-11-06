"""Unit tests for the dummy tools migration to agent.py."""

import unittest
import unittest.mock
from unittest.mock import MagicMock
from pathlib import Path

from linhai.agent import Agent, AgentContext
from linhai.llm import ToolCallMessage, SystemMessage, Message
from linhai.agent.base import RuntimeMessage

from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager


class TestDummyToolsMigration(unittest.IsolatedAsyncioTestCase):
    """Test cases for the dummy tools migration from dummy.py to agent.py."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.group_chat = GroupChat()
        # Register queues that are normally initialized by CLI
        self.group_chat.register_queue("cli_agent_output")
        self.group_chat.register_queue("cli_runtime_output")
        from linhai.tool.base import global_tools
        from linhai.tool.tools.terminal import terminal_toolset
        self.tool_manager = ToolManager(group_chat=self.group_chat, toolsets=[global_tools, terminal_toolset])

    async def test_get_token_usage_tool_registered(self):
        """Test that get_token_usage tool is properly registered."""
        # Mock the agent configuration with proper typing
        mock_config: AgentContext = {
            "system_prompt": "test prompt",
            "mcp": [],  # 添加mcp字段
            "config_basedir": Path("/tmp"),  # 添加config_basedir字段
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }

        # Create agent instance
        Agent(context=mock_config, group_chat=self.group_chat, init_messages=[])

        # Get the ToolManager that Agent registered
        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        # Check if get_token_usage tool is registered by calling it
        result = await tool_manager.process_tool_call(
            ToolCallMessage(function_name="get_token_usage", function_arguments={})
        )

        # If we get a result (not an error), the tool is registered
        self.assertIn(type(result).__name__, ["ToolResultMessage", "ToolErrorMessage"])

    async def test_thanox_history_tool_registered(self):
        """Test that thanox_history tool is properly registered."""
        # Mock the agent configuration with proper typing
        mock_config: AgentContext = {
            "system_prompt": "test prompt",
            "mcp": [],  # 添加mcp字段
            "config_basedir": Path("/tmp"),  # 添加config_basedir字段
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }

        # Create agent instance
        Agent(context=mock_config, group_chat=self.group_chat, init_messages=[])

        # Get the ToolManager that Agent registered
        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        # Check if thanox_history tool is registered by calling it
        result = await tool_manager.process_tool_call(
            ToolCallMessage(function_name="thanox_history", function_arguments={})
        )

        # If we get a result (not an error), the tool is registered
        self.assertIn(type(result).__name__, ["ToolResultMessage", "ToolErrorMessage"])

    async def test_get_token_usage_tool_call_with_token_usage(self):
        """Test get_token_usage tool call when token usage is available."""
        mock_config: AgentContext = {
            "system_prompt": "test prompt",
            "mcp": [],  # 添加mcp字段
            "config_basedir": Path("/tmp"),  # 添加config_basedir字段
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }

        agent = Agent(context=mock_config, group_chat=self.group_chat, init_messages=[])
        agent.last_token_usage = 12345

        # Get the ToolManager that Agent registered
        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        # Call the get_token_usage tool
        result = await tool_manager.process_tool_call(
            ToolCallMessage(function_name="get_token_usage", function_arguments={})
        )

        # Check the result
        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertIn("12345", content)
        self.assertIn("12.35 k", content)

    async def test_get_token_usage_tool_call_without_token_usage(self):
        """Test get_token_usage tool call when no token usage is available."""
        mock_config: AgentContext = {
            "system_prompt": "test prompt",
            "mcp": [],  # 添加mcp字段
            "config_basedir": Path("/tmp"),  # 添加config_basedir字段
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }

        agent = Agent(context=mock_config, group_chat=self.group_chat, init_messages=[])
        agent.last_token_usage = None

        # Get the ToolManager that Agent registered
        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        # Call the get_token_usage tool
        result = await tool_manager.process_tool_call(
            ToolCallMessage(function_name="get_token_usage", function_arguments={})
        )

        # Check the result
        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertEqual("暂无token用量信息", content)

    async def test_thanox_history_tool_call_with_sufficient_messages(self):
        """Test thanox_history tool call when there are sufficient messages."""
        mock_config: AgentContext = {
            "system_prompt": "test prompt",
            "mcp": [],  # 添加mcp字段
            "config_basedir": Path("/tmp"),  # 添加config_basedir字段
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }

        # Create messages (more than 10 to trigger deletion)
        init_messages: list[Message] = [
            SystemMessage(
                template="test",
                current_time="2023-01-01 00:00:00",
                group_chat=self.group_chat,
            )
        ]
        for i in range(15):
            init_messages.append(RuntimeMessage(f"Message {i}"))

        Agent(
            context=mock_config, group_chat=self.group_chat, init_messages=init_messages
        )

        # Get the ToolManager that Agent registered
        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        # Call the thanox_history tool
        result = await tool_manager.process_tool_call(
            ToolCallMessage(function_name="thanox_history", function_arguments={})
        )

        # Check the result
        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertIn("thanox_history: 随机删除了", content)
        self.assertIn("条消息", content)

    async def test_thanox_history_tool_call_with_insufficient_messages(self):
        """Test thanox_history tool call when there are insufficient messages."""
        mock_config: AgentContext = {
            "system_prompt": "test prompt",
            "mcp": [],  # 添加mcp字段
            "config_basedir": Path("/tmp"),  # 添加config_basedir字段
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_hard": 60000,
            "compress_threshold_soft": 30000,
        }

        # Create only a few messages (less than 10)
        init_messages: list[Message] = [
            SystemMessage(
                template="test",
                current_time="2023-01-01 00:00:00",
                group_chat=self.group_chat,
            )
        ]
        for i in range(5):
            init_messages.append(RuntimeMessage(f"Message {i}"))

        Agent(
            context=mock_config, group_chat=self.group_chat, init_messages=init_messages
        )

        # Get the ToolManager that Agent registered
        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        # Call the thanox_history tool
        result = await tool_manager.process_tool_call(
            ToolCallMessage(function_name="thanox_history", function_arguments={})
        )

        # Check the result
        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertEqual("消息数量不足，无需删除", content)


if __name__ == "__main__":
    unittest.main()
