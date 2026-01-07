"""Unit tests for the dummy tools migration to agent.py."""

import unittest
import unittest.mock
from unittest.mock import MagicMock
from pathlib import Path

from linhai.agent import Agent
from linhai.llm import ToolCallMessage, SystemMessage, Message
from linhai.agent.base import RuntimeMessage

from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager


class TestDummyToolsMigration(unittest.IsolatedAsyncioTestCase):
    """Test cases for the dummy tools migration from dummy.py to agent.py."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.group_chat = GroupChat()
        self.group_chat.register_queue("agent_answer")
        from linhai.tool.base import global_tools
        from linhai.machine_control.master_host import terminal_toolset
        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            group_chat=self.group_chat,
            toolsets=[global_tools, terminal_toolset],
            config=ToolConfig(),
            mcp_config=[],
            mcp_basedir=Path("/tmp"),
        )

    async def test_get_token_usage_tool_registered(self):
        """Test that get_token_usage tool is properly registered."""
        mock_config = {
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 60000,
        }
        mock_config["llms"][0].get_name = MagicMock(return_value="test_llm")

        # 将llms和llm_names合并为llms_with_names
        llms_with_names = list(zip(mock_config["llms"], mock_config["llm_names"]))

        Agent(
            llms=mock_config["llms"],
            compress_threshold=mock_config["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=[],
            llm_name=mock_config["llm_names"][mock_config["current_llm_index"]],
        )

        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        result = await tool_manager.process_tool_call(
            ToolCallMessage(
                function_name="get_token_usage",
                function_arguments={},
                assert_success=True,
                with_secret=None,
            )
        )

        self.assertIn(type(result).__name__, ["ToolResultMessage", "ToolErrorMessage"])

    async def test_context_thanox_tool_registered(self):
        """Test that context_thanox tool is properly registered."""
        mock_config = {
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 60000,
        }
        mock_config["llms"][0].get_name = MagicMock(return_value="test_llm")

        # 将llms和llm_names合并为llms_with_names
        llms_with_names = list(zip(mock_config["llms"], mock_config["llm_names"]))

        Agent(
            llms=mock_config["llms"],
            compress_threshold=mock_config["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=[],
            llm_name=mock_config["llm_names"][mock_config["current_llm_index"]],
        )

        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        result = await tool_manager.process_tool_call(
            ToolCallMessage(
                function_name="context_thanox",
                function_arguments={},
                assert_success=True,
                with_secret=None,
            )
        )

        self.assertIn(type(result).__name__, ["ToolResultMessage", "ToolErrorMessage"])

    async def test_get_token_usage_tool_call_with_token_usage(self):
        """Test get_token_usage tool call when token usage is available."""
        mock_config = {
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 60000,
        }
        mock_config["llms"][0].get_name = MagicMock(return_value="test_llm")

        # 将llms和llm_names合并为llms_with_names
        llms_with_names = list(zip(mock_config["llms"], mock_config["llm_names"]))

        agent = Agent(
            llms=mock_config["llms"],
            compress_threshold=mock_config["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=[],
            llm_name=mock_config["llm_names"][mock_config["current_llm_index"]],
        )
        agent.last_token_usage = 12345

        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        result = await tool_manager.process_tool_call(
            ToolCallMessage(
                function_name="get_token_usage",
                function_arguments={},
                assert_success=True,
                with_secret=None,
            )
        )

        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertIn("12345", content)
        self.assertIn("12.35 k", content)

    async def test_get_token_usage_tool_call_without_token_usage(self):
        """Test get_token_usage tool call when no token usage is available."""
        mock_config = {
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 60000,
        }
        mock_config["llms"][0].get_name = MagicMock(return_value="test_llm")

        # 将llms和llm_names合并为llms_with_names
        llms_with_names = list(zip(mock_config["llms"], mock_config["llm_names"]))

        agent = Agent(
            llms=mock_config["llms"],
            compress_threshold=mock_config["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=[],
            llm_name=mock_config["llm_names"][mock_config["current_llm_index"]],
        )
        agent.last_token_usage = None

        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        result = await tool_manager.process_tool_call(
            ToolCallMessage(
                function_name="get_token_usage",
                function_arguments={},
                assert_success=True,
                with_secret=None,
            )
        )

        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertEqual("暂无token用量信息", content)

    async def test_context_thanox_tool_call_with_sufficient_messages(self):
        """Test context_thanox tool call when there are sufficient messages."""
        mock_config = {
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 60000,
        }
        mock_config["llms"][0].get_name = MagicMock(return_value="test_llm")

        init_messages: list[Message] = [
            SystemMessage(
                group_chat=self.group_chat,
            )
        ]
        for i in range(15):
            init_messages.append(RuntimeMessage(f"Message {i}"))

        # 将llms和llm_names合并为llms_with_names
        llms_with_names = list(zip(mock_config["llms"], mock_config["llm_names"]))

        Agent(
            llms=mock_config["llms"],
            compress_threshold=mock_config["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=init_messages,
            llm_name=mock_config["llm_names"][mock_config["current_llm_index"]],
        )

        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        result = await tool_manager.process_tool_call(
            ToolCallMessage(
                function_name="context_thanox",
                function_arguments={},
                assert_success=True,
                with_secret=None,
            )
        )

        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertIn("context_thanox: 随机删除了", content)
        self.assertIn("条消息", content)

    async def test_context_thanox_tool_call_with_insufficient_messages(self):
        """Test context_thanox tool call when there are insufficient messages."""
        mock_config = {
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 60000,
        }
        mock_config["llms"][0].get_name = MagicMock(return_value="test_llm")

        init_messages: list[Message] = [
            SystemMessage(
                group_chat=self.group_chat,
            )
        ]
        for i in range(5):
            init_messages.append(RuntimeMessage(f"Message {i}"))

        # 将llms和llm_names合并为llms_with_names
        llms_with_names = list(zip(mock_config["llms"], mock_config["llm_names"]))

        Agent(
            llms=mock_config["llms"],
            compress_threshold=mock_config["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=init_messages,
            llm_name=mock_config["llm_names"][mock_config["current_llm_index"]],
        )

        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        result = await tool_manager.process_tool_call(
            ToolCallMessage(
                function_name="context_thanox",
                function_arguments={},
                assert_success=True,
                with_secret=None,
            )
        )

        self.assertEqual(type(result).__name__, "ToolResultMessage")
        content = getattr(result, "content", "")
        self.assertEqual("消息数量不足，无需删除", content)


if __name__ == "__main__":
    unittest.main()
