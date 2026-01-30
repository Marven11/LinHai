"""Unit tests for LLM switching functionality."""

import unittest
from unittest.mock import MagicMock, AsyncMock


from linhai.agent import Agent
from pathlib import Path
from linhai.llm import SystemMessage, ToolCallMessage
from linhai.tool.base import ToolCallResultMessage, ToolResultSuccess, ToolResultFailed
from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager
from linhai.tool.base import global_tools


class TestLLMSwitching(unittest.IsolatedAsyncioTestCase):
    """Test cases for LLM switching tools."""

    def setUp(self):
        self.mock_llm1 = MagicMock()
        self.mock_llm1.answer_stream = AsyncMock(return_value=AsyncMock())
        self.mock_llm2 = MagicMock()
        self.mock_llm2.answer_stream = AsyncMock(return_value=AsyncMock())

        config = {
            "llms": [self.mock_llm1, self.mock_llm2],
            "llm_names": ["primary", "secondary"],
            "current_llm_index": 0,
            "compress_threshold": 800,
        }

        self.group_chat = GroupChat()

        from linhai.machine_control.master_host import terminal_toolset
        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            group_chat=self.group_chat,
            toolsets=[global_tools, terminal_toolset],
            config=ToolConfig(),
            mcp_config=[],
            mcp_basedir=Path("/tmp"),
        )

        init_messages = [
            SystemMessage(
                group_chat=self.group_chat,
            )
        ]

        # 配置mock对象的get_name方法
        self.mock_llm1.get_name = MagicMock(return_value="primary")
        self.mock_llm2.get_name = MagicMock(return_value="secondary")

        self.agent = Agent(
            llms=config["llms"],
            compress_threshold=config["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=init_messages,
            llm_name=config["llm_names"][config["current_llm_index"]],
        )
        self.tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

    async def test_current_llm_tool(self):
        """Test current_llm tool functionality."""
        tool_call = ToolCallMessage(
            function_name="current_llm",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )

        result = await self.tool_manager.process_tool_call(tool_call, tool_index=1)

        if isinstance(result, ToolResultFailed):
            self.fail(f"current_llm tool failed: {result.content}")  # type: ignore

        self.assertIsInstance(result, ToolCallResultMessage)
        self.assertIn("primary", str(result))

    async def test_switch_llm_tool_success(self):
        """Test successful LLM switching."""
        tool_call = ToolCallMessage(
            function_name="switch_llm",
            function_arguments={"llm_name": "secondary"},
            assert_success=True,
            with_secret=None,
        )

        result = await self.tool_manager.process_tool_call(tool_call, tool_index=1)

        if isinstance(result, ToolResultFailed):
            self.fail(f"switch_llm tool failed: {result.content}")

        self.assertIsInstance(result, ToolCallResultMessage)
        self.assertIn("已切换到LLM: secondary", str(result))

        self.assertEqual(self.agent.current_llm_index, 1)

    async def test_switch_llm_tool_failure(self):
        """Test LLM switching with non-existent LLM."""
        tool_call = ToolCallMessage(
            function_name="switch_llm",
            function_arguments={"llm_name": "nonexistent"},
            assert_success=True,
            with_secret=None,
        )

        result = await self.tool_manager.process_tool_call(tool_call, tool_index=1)

        if isinstance(result, ToolResultFailed):
            self.fail(f"switch_llm tool failed: {result.content}")

        self.assertIsInstance(result, ToolCallResultMessage)
        self.assertIn("错误：LLM名称 'nonexistent' 不存在", str(result))
        self.assertIn("可用的LLM包括: primary, secondary", str(result))

        self.assertEqual(self.agent.current_llm_index, 0)

    def test_llm_selection(self):
        """Test LLM selection based on current_llm_index."""
        selected_llm = self.agent.get_current_model()
        self.assertEqual(selected_llm, self.mock_llm1)

        self.agent.current_llm_index = 1
        selected_llm = self.agent.get_current_model()
        self.assertEqual(selected_llm, self.mock_llm2)


if __name__ == "__main__":
    unittest.main()
