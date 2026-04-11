"""测试工具冲突检查重构功能。"""

import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from linhai.agent.messages import RuntimeMessage
from linhai.agent.toolcall import AgentToolcall
from linhai.config import MCPConfig, ToolConfig
from linhai.base import ToolCallMessage
from linhai.tool.base import ToolSet
from linhai.tool.main import ToolManager


class TestToolConflictRefactor(unittest.TestCase):
    """测试工具冲突检查重构。"""

    def setUp(self) -> None:
        self._setup_agent_mock()
        self._setup_toolcall()
        self._setup_tool_manager()
        self._reset_called_tools()

    def _setup_agent_mock(self) -> None:
        self.mock_llm_manager = Mock()
        mock_llm = Mock()
        mock_llm.get_name = Mock(return_value="test_llm")
        mock_llm.get_token_limit = Mock(return_value=65536)
        self.mock_llm_manager.llms = [mock_llm]
        self.mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)

        self.mock_registry = Mock()

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            if member_type == "llm_manager":
                return self.mock_llm_manager
            raise RuntimeError(f"{member_type!r} not exists")

        self.mock_registry.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

    def _setup_toolcall(self) -> None:
        self.toolcall = AgentToolcall(self.mock_registry)

    def _setup_tool_manager(self) -> None:
        config = ToolConfig()
        mcp_config: list[MCPConfig] = []
        mcp_basedir = Path(".")

        tool_manager = ToolManager(
            registry=self.mock_registry,
            config=config,
            mcp_connector=None,
        )

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            if member_type == "tool_manager":
                return tool_manager
            raise RuntimeError(f"{member_type!r} not exists")

        self.mock_registry.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )
        self.toolcall.tool_manager = tool_manager

    def _reset_called_tools(self) -> None:
        self.toolcall.called_tools_in_round = []

    def _create_tool_a(self) -> ToolSet:
        toolset = ToolSet()

        @toolset.register_tool(
            name="tool_a",
            desc="工具A",
            args={},
            required_args=[],
            conflict_with=["tool_b"],
        )
        def tool_a() -> str:
            return "a"

        return toolset

    def _create_tool_b(self) -> ToolSet:
        toolset = ToolSet()

        @toolset.register_tool(
            name="tool_b",
            desc="工具B",
            args={},
            required_args=[],
            conflict_with=["tool_a"],
        )
        def tool_b() -> str:
            return "b"

        return toolset

    def _add_toolsets(self, toolsets: list[ToolSet]) -> None:
        for i, toolset in enumerate(toolsets):
            self.toolcall.tool_manager.register_toolset(f"test_{i}", toolset)

    def test_check_tool_conflict_returns_none_when_no_conflict(self) -> None:
        toolset = self._create_tool_a()
        self._add_toolsets([toolset])

        result = self.toolcall._check_tool_conflict("tool_a")
        self.assertIsNone(result)

    def test_check_tool_conflict_returns_conflicting_tool_name(self) -> None:
        toolset1 = self._create_tool_a()
        toolset2 = self._create_tool_b()
        self._add_toolsets([toolset1, toolset2])

        self.toolcall.called_tools_in_round.append("tool_a")
        result = self.toolcall._check_tool_conflict("tool_b")
        self.assertEqual(result, "tool_a")

    def test_check_tool_conflict_bidirectional(self) -> None:
        toolset1 = self._create_tool_a()
        toolset2 = self._create_tool_b()
        self._add_toolsets([toolset1, toolset2])

        self.toolcall.called_tools_in_round.append("tool_a")
        result1 = self.toolcall._check_tool_conflict("tool_b")
        self.assertEqual(result1, "tool_a")

        self.toolcall.called_tools_in_round = ["tool_b"]
        result2 = self.toolcall._check_tool_conflict("tool_a")
        self.assertEqual(result2, "tool_b")

    def test_check_tool_conflict_no_tool_definition(self) -> None:
        result = self.toolcall._check_tool_conflict("nonexistent_tool")
        self.assertIsNone(result)

    def _setup_async_mocks(self) -> None:
        self.mock_registry.send_if_exists = AsyncMock()
        self.mock_lifecycle = Mock()
        self.mock_lifecycle.after_toolcall.trigger = AsyncMock()
        self.mock_message_processor = Mock()
        self.mock_message_processor.add_new_message = AsyncMock()

        self.mock_state_machine = Mock()
        self.mock_state_machine.state = "working"
        self.mock_state_machine.transition_to_working = Mock()

        original_side_effect = self.mock_registry.get_member_typechecked.side_effect

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            extra = {
                "lifecycle": self.mock_lifecycle,
                "agent_message": self.mock_message_processor,
                "state_machine": self.mock_state_machine,
            }
            if member_type in extra:
                return extra[member_type]
            return original_side_effect(member_type, _member_class)

        self.mock_registry.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

    def _verify_error_message_content(self) -> None:
        add_new_message_calls = (
            self.mock_message_processor.add_new_message.call_args_list
        )
        self.assertGreater(len(add_new_message_calls), 0)

        conflict_messages = []
        for call in add_new_message_calls:
            args = call[0]
            if (
                len(args) > 0
                and isinstance(args[0], RuntimeMessage)
                and "工具调用冲突" in args[0].message
            ):
                conflict_messages.append(args[0].message)

        self.assertGreater(len(conflict_messages), 0)
        message_content = conflict_messages[0]
        self.assertIn("tool_a", message_content)
        self.assertIn("tool_b", message_content)
        self.assertIn("冲突", message_content)
        self.assertNotIn("called_tools_in_round", message_content)
        self.assertNotIn("['tool_a']", message_content)

    def test_error_message_shows_conflicting_tool_name(self) -> None:
        toolset1 = self._create_tool_a()
        toolset2 = self._create_tool_b()
        self._add_toolsets([toolset1, toolset2])
        self.toolcall.called_tools_in_round.append("tool_a")

        self._setup_async_mocks()

        tool_call = ToolCallMessage(
            function_name="tool_b",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )
        result = asyncio.run(self.toolcall.call_tool(tool_call, tool_index=1))

        self.assertTrue(result)
        self.assertTrue(self.toolcall.early_return)
        self.mock_lifecycle.after_toolcall.trigger.assert_called_once()
        self._verify_error_message_content()


if __name__ == "__main__":
    unittest.main()
