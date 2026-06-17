"""Unit tests for LLM switching functionality."""

import unittest

from linhai.agent import Agent
from linhai.base import SystemMessage, ToolCallMessage
from linhai.tool.base import (
    ToolCallResultMessage,
    FailedToolResult,
)
from linhai.registry import Registry
from linhai.tool.main import ToolManager
from linhai.tool.base import utils_tools

from tests.test_llm_manager import FakeLLM


class TestLLMSwitching(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.llm1 = FakeLLM(
            name="primary",
            token_limit=8000,
            support_image=True,
        )
        self.llm2 = FakeLLM(
            name="secondary",
            token_limit=4000,
            support_image=False,
        )

        config = {
            "llms": [self.llm1, self.llm2],
            "llm_names": ["primary", "secondary"],
            "current_llm_index": 0,
            "compress_threshold": 800,
        }

        self.registry = Registry()

        from linhai.machine_control.main import MachineControl

        MachineControl(self.registry)

        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            registry=self.registry,
            config=ToolConfig(),
            mcp_connector=None,
        )
        self.tool_manager.register_toolset("utils", utils_tools)

        init_messages = [
            SystemMessage(registry=self.registry),
        ]

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
        self.tool_manager.register_toolset(
            "llm", self.agent.toolcall_processor.calculate_llm_toolset()
        )

    async def test_switch_llm_tool_success(self):
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
        result_str = str(result)
        self.assertIn("已切换到LLM: secondary", result_str)

        current = self.agent.llm_manager.get_current_llm()
        self.assertIs(current, self.llm2)
        self.assertEqual(current.get_name(), "secondary")
        self.assertEqual(current.get_token_limit(), 4000)
        self.assertFalse(current.support_image())

    async def test_switch_llm_tool_failure(self):
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
        result_str = str(result)
        self.assertIn("nonexistent", result_str)
        self.assertIn("primary, secondary", result_str)

        current = self.agent.llm_manager.get_current_llm()
        self.assertIs(current, self.llm1)

    async def test_llm_selection(self):
        selected = self.agent.get_current_model()
        self.assertIs(selected, self.llm1)

        await self.agent.llm_manager.switch_to_llm("secondary")
        selected = self.agent.get_current_model()
        self.assertIs(selected, self.llm2)

    async def test_list_llm_tool(self):
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
        self.assertIn("2 个LLM", result_str)
        self.assertIn("primary", result_str)
        self.assertIn("secondary", result_str)
        self.assertIn("token限制: 8000", result_str)
        self.assertIn("token限制: 4000", result_str)


if __name__ == "__main__":
    unittest.main()
