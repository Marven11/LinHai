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

        # 注册conversation_folder
        from linhai.agent.conversation import register_conversation_folder

        register_conversation_folder(self.group_chat)

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
            pinned_messages=[],
            llm_name=mock_config["llm_names"][mock_config["current_llm_index"]],
        )

        tool_manager = self.group_chat.get_member_typechecked(
            "tool_manager", ToolManager
        )

        result = await tool_manager.process_tool_call(
            ToolCallMessage(
                function_name="get_token_usage",
                function_arguments={},
                assert_success=True,
                with_secret=None,
            ),
            tool_index=1,
        )

        self.assertEqual(type(result).__name__, "ToolCallResultMessage")
