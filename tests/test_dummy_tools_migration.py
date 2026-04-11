"""Unit tests for the dummy tools migration to agent.py."""

import unittest
import unittest.mock
from unittest.mock import MagicMock
from pathlib import Path

from linhai.agent import Agent
from linhai.base import ToolCallMessage, SystemMessage, Message
from linhai.agent.messages import RuntimeMessage

from linhai.registry import Registry
from linhai.tool.main import ToolManager


class TestDummyToolsMigration(unittest.IsolatedAsyncioTestCase):
    """Test cases for the dummy tools migration from dummy.py to agent.py."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.registry = Registry()

        # 注册conversation_folder
        from linhai.agent.conversation import register_conversation_folder

        register_conversation_folder(self.registry)

        # 注册token_manager
        from linhai.token_manager import TokenManager

        TokenManager(self.registry)

        # 注册machine_control
        from linhai.machine_control.main import MachineControl

        MachineControl(self.registry)

        from linhai.tool.base import utils_tools
        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            registry=self.registry,
            config=ToolConfig(),
            mcp_connector=None,
        )
        self.tool_manager.register_toolset("utils", utils_tools)

    async def test_get_token_usage_tool_registered(self):
        """Test that get_token_usage tool is properly registered."""
        mock_config = {
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 60000,
        }
        mock_config["llms"][0].get_name = MagicMock(return_value="test_llm")

        from linhai.llm_manager import LlmManager

        llm_manager = LlmManager(
            registry=self.registry,
            llms=mock_config["llms"],
            default_llm_name=mock_config["llm_names"][mock_config["current_llm_index"]],
            llm_fallback_map={"test_llm": None},
            llm_fallback_duration_map={"test_llm": 120},
        )
        Agent(
            llm_manager=llm_manager,
            compress_threshold=mock_config["compress_threshold"],
            registry=self.registry,
            pinned_messages=[],
        )

        tool_manager = self.registry.get_member_typechecked("tool_manager", ToolManager)

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
