"""Unit tests for LLM switching functionality."""

import unittest
from unittest.mock import MagicMock, AsyncMock


from linhai.agent import Agent
from pathlib import Path
from linhai.base import SystemMessage, ToolCallMessage
from linhai.tool.base import (
    ToolCallResultMessage,
    SuccessfulToolResult,
    FailedToolResult,
)
from linhai.registry import Registry
from linhai.tool.main import ToolManager
from linhai.tool.base import utils_tools


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

        self.registry = Registry()

        # 注册machine_control
        from linhai.machine_control.main import MachineControl

        MachineControl(self.registry, remote_machines=[])

        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            registry=self.registry,
            config=ToolConfig(),
            mcp_connector=None,
        )
        self.tool_manager.register_toolset("utils", utils_tools)

        init_messages = [
            SystemMessage(
                registry=self.registry,
            )
        ]

        # 配置mock对象的get_name方法
        self.mock_llm1.get_name = MagicMock(return_value="primary")
        self.mock_llm2.get_name = MagicMock(return_value="secondary")

        from linhai.llm_manager import LlmManager

        llm_manager = LlmManager(
            registry=self.registry,
            llms=config["llms"],
            default_llm_name=config["llm_names"][config["current_llm_index"]],
            llm_fallback_map={"primary": None, "secondary": None},
            llm_fallback_duration_map={"primary": 120, "secondary": 120},
        )
        self.agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=config["compress_threshold"],
            registry=self.registry,
            pinned_messages=init_messages,
        )
        self.tool_manager = self.registry.get_member_typechecked(
            "tool_manager", ToolManager
        )
        # 显式注册LLM工具集
        self.tool_manager.register_toolset(
            "llm", self.agent.toolcall_processor.calculate_llm_toolset()
        )

    async def test_current_llm_tool(self):
        """Test current_llm tool functionality."""
        tool_call = ToolCallMessage(
            function_name="current_llm",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )

        result = await self.tool_manager.process_tool_call(tool_call, tool_index=1)

        if isinstance(result, FailedToolResult):
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

        if isinstance(result, FailedToolResult):
            self.fail(f"switch_llm tool failed: {result.content}")

        self.assertIsInstance(result, ToolCallResultMessage)
        self.assertIn("已切换到LLM: secondary", str(result))

        self.assertEqual(self.agent.llm_manager.get_current_llm(), self.mock_llm2)

    async def test_switch_llm_tool_failure(self):
        """Test LLM switching with non-existent LLM."""
        tool_call = ToolCallMessage(
            function_name="switch_llm",
            function_arguments={"llm_name": "nonexistent"},
            assert_success=True,
            with_secret=None,
        )

        result = await self.tool_manager.process_tool_call(tool_call, tool_index=1)

        if isinstance(result, FailedToolResult):
            self.fail(f"switch_llm tool failed: {result.content}")

        self.assertIsInstance(result, ToolCallResultMessage)
        self.assertIn("错误：LLM名称 'nonexistent' 不存在", str(result))
        self.assertIn("可用的LLM包括: primary, secondary", str(result))

        self.assertEqual(self.agent.llm_manager.get_current_llm(), self.mock_llm1)

    async def test_llm_selection(self):
        """Test LLM selection based on current_llm_index."""
        selected_llm = self.agent.get_current_model()
        self.assertEqual(selected_llm, self.mock_llm1)

        await self.agent.llm_manager.switch_to_llm("secondary")
        selected_llm = self.agent.get_current_model()
        self.assertEqual(selected_llm, self.mock_llm2)

    async def test_list_llm_tool(self):
        """Test list_llm tool functionality."""
        # Configure mock LLMs with get_model method
        self.mock_llm1.get_model = MagicMock(return_value="gpt-4")
        self.mock_llm2.get_model = MagicMock(return_value="gpt-3.5")
        self.mock_llm1.get_token_limit = MagicMock(return_value=8000)
        self.mock_llm2.get_token_limit = MagicMock(return_value=4000)
        self.mock_llm1.support_image = MagicMock(return_value=False)
        self.mock_llm2.support_image = MagicMock(return_value=False)

        tool_call = ToolCallMessage(
            function_name="list_llm",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )

        result = await self.tool_manager.process_tool_call(tool_call, tool_index=1)

        if isinstance(result, FailedToolResult):
            self.fail(f"list_llm tool failed: {result.content}")

        self.assertIsInstance(result, ToolCallResultMessage)
        result_str = str(result)

        # Check that the result contains expected information
        self.assertIn("找到 2 个LLM", result_str)
        self.assertIn("primary", result_str)
        self.assertIn("secondary", result_str)
        # Note: model names may be 'unknown' in mock environment
        # 检查token限制是否显示
        self.assertIn("token限制: 8000", result_str)
        self.assertIn("token限制: 4000", result_str)


if __name__ == "__main__":
    unittest.main()
