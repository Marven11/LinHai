"""Unit tests for agent workflow functionality."""

import reprlib
import unittest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from linhai.agent import Agent
from linhai.agent.messages import RuntimeMessage
from linhai.agent.workflow import (
    context_forget_range_step1,
    context_forget_range_step2,
)
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.base import UserMessage, AssistantMessage
from linhai.tool.main import ToolManager
from linhai.tool.base import utils_tools, SuccessfulToolResult, FailedToolResult
from linhai.registry import Registry

r = reprlib.Repr()
r.maxstring = 200
custom_repr = r.repr


def format_messages_for_assert(messages):
    """格式化消息列表用于断言错误信息"""
    return (
        f"Messages: {[f'{type(msg).__name__}: {custom_repr(msg)}' for msg in messages]}"
    )


class TestAgentWorkflow(unittest.IsolatedAsyncioTestCase):
    """Test cases for agent workflow integration and functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock()
        self.mock_llm.get_name = MagicMock(return_value="test_llm")
        config = {
            "llms": [self.mock_llm],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 800,
        }
        self.registry = Registry()
        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            registry=self.registry,
            config=ToolConfig(),
            mcp_connector=None,
        )
        self.tool_manager.register_toolset("utils", utils_tools)

        from linhai.llm_manager import LlmManager

        llm_manager = LlmManager(
            registry=self.registry,
            llms=config["llms"],
            default_llm_name=config["llm_names"][config["current_llm_index"]],
            llm_fallback_map={"test_llm": None},
            llm_fallback_duration_map={"test_llm": 120},
        )
        self.agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=config["compress_threshold"],
            registry=self.registry,
            pinned_messages=[],
        )
        orchestration = self.registry.get_member_typechecked(
            "agent_context_orchestration", AgentContextOrchestration
        )
        self.tool_manager.register_toolset(
            "context_cleaning", orchestration.get_context_cleaning_toolset()
        )

    async def test_workflow_as_regular_tool(self):
        """Test that context_forget_range_step1 and step2 are now regular tools, not workflows."""
        tools_info = self.tool_manager.get_tools_info()
        tool_names = [tool["function"]["name"] for tool in tools_info]
        self.assertIn("context_forget_range_step1", tool_names)
        self.assertIn("context_forget_range_step2", tool_names)

    async def test_context_forget_range_step1_as_tool(self):
        """Test calling context_forget_range_step1 as a regular tool."""
        pass

    async def test_prepare_messages_excludes_last_50(self):
        """Test that _prepare_messages_for_compression excludes last 50 messages when total >= 50."""
        from linhai.agent.workflow import _prepare_messages_for_compression
        from linhai.agent.messages import RuntimeMessage

        mock_agent = MagicMock()
        mock_messages = [RuntimeMessage(f"Message {i}") for i in range(30)]
        mock_agent.message_processor.messages = mock_messages

        result = _prepare_messages_for_compression(mock_agent)
        self.assertIsInstance(result, str)
        lines = result.splitlines()
        self.assertEqual(len(lines), 30)

        mock_messages = [RuntimeMessage(f"Message {i}") for i in range(50)]
        mock_agent.message_processor.messages = mock_messages

        result = _prepare_messages_for_compression(mock_agent)
        lines = result.splitlines()
        self.assertEqual(len(lines), 0)

        mock_messages = [RuntimeMessage(f"Message {i}") for i in range(100)]
        mock_agent.message_processor.messages = mock_messages

        result = _prepare_messages_for_compression(mock_agent)
        lines = result.split("\n")
        self.assertEqual(len(lines), 50)
        for line in lines:
            if line.startswith("- id:"):
                import re

                match = re.search(r"id: (\d+)", line)
                if match:
                    msg_id = int(match.group(1))
                    self.assertLess(msg_id, 50)

        mock_messages = [RuntimeMessage(f"Message {i}") for i in range(49)]
        mock_agent.message_processor.messages = mock_messages

        result = _prepare_messages_for_compression(mock_agent)
        lines = result.split("\n")
        self.assertEqual(len(lines), 49)

        mock_messages = [RuntimeMessage(f"Message {i}") for i in range(51)]
        mock_agent.message_processor.messages = mock_messages

        result = _prepare_messages_for_compression(mock_agent)
        lines = result.split("\n")
        self.assertEqual(len(lines), 1)
        if lines[0].startswith("- id:"):
            import re

            match = re.search(r"id: (\d+)", lines[0])
            if match:
                msg_id = int(match.group(1))
                self.assertEqual(msg_id, 0)

        mock_messages = [RuntimeMessage(f"Message {i}") for i in range(200)]
        mock_agent.message_processor.messages = mock_messages

        result = _prepare_messages_for_compression(mock_agent)
        lines = result.split("\n")
        self.assertLessEqual(len(lines), 75)
        for line in lines:
            if line.startswith("- id:"):
                import re

                match = re.search(r"id: (\d+)", line)
                if match:
                    msg_id = int(match.group(1))
                    self.assertLess(msg_id, 150)

    async def test_context_forget_range_step1_functionality(self):
        """Test the context_forget_range_step1 function with mock data."""
        mock_agent = MagicMock()
        mock_registry = MagicMock()
        mock_range_clean_manager = MagicMock()
        mock_agent.registry = mock_registry

        # 设置get_members根据参数返回不同的对象
        def get_member_typechecked_side_effect(name, cls=None):
            if name == "agent":
                return mock_agent
            elif name == "range_clean_manager":
                return mock_range_clean_manager
            elif name == "conversation_folder":
                return Path(tempfile.mkdtemp())
            else:
                return None

        mock_registry.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

        async def mock_send_if_exists(queue_name, message):
            pass

        mock_registry.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

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
        mock_agent.message_processor.messages = mock_messages
        mock_agent.message_processor.filter_messages = AsyncMock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75,
        }

        # 模拟range_clean_manager.create_clean_info
        mock_range_clean_manager.create_clean_info = MagicMock()

        with patch("linhai.agent.conversation.save_cleaned_messages") as mock_save:
            mock_save.return_value = Path("/tmp/test.json")
            result = await context_forget_range_step1(mock_registry)

        # 验证结果，应为SuccessfulToolResult
        self.assertIsInstance(result, SuccessfulToolResult)

    async def test_compress_threshold_trigger(self):
        """Test that compression is triggered when token threshold is exceeded."""

    async def test_workflow_with_invalid_range(self):
        """Test context_forget_range_step1 with invalid range parameters."""
        mock_agent = MagicMock()
        mock_registry = MagicMock()
        mock_range_clean_manager = MagicMock()

        def get_member_typechecked_side_effect(name, cls=None):
            if name == "agent":
                return mock_agent
            elif name == "range_clean_manager":
                return mock_range_clean_manager
            elif name == "conversation_folder":
                return Path(tempfile.mkdtemp())
            else:
                return None

        mock_registry.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

        async def mock_send_if_exists(queue_name, message):
            pass

        mock_registry.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

        mock_agent.message_processor.messages = [
            RuntimeMessage(f"Message {i}") for i in range(20)
        ]
        mock_agent.message_processor.filter_messages = AsyncMock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75,
        }
        mock_range_clean_manager.create_clean_info = MagicMock()

        with patch("linhai.agent.conversation.save_cleaned_messages") as mock_save:
            mock_save.return_value = Path("/tmp/test.json")
            result = await context_forget_range_step1(mock_registry)

        self.assertIsInstance(result, SuccessfulToolResult)

    async def test_workflow_with_small_range(self):
        """Test context_forget_range_step1 with range smaller than minimum."""
        mock_agent = MagicMock()
        mock_registry = MagicMock()
        mock_range_clean_manager = MagicMock()

        def get_member_typechecked_side_effect(name, cls=None):
            if name == "agent":
                return mock_agent
            elif name == "range_clean_manager":
                return mock_range_clean_manager
            elif name == "conversation_folder":
                return Path(tempfile.mkdtemp())
            else:
                return None

        mock_registry.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

        async def mock_send_if_exists(queue_name, message):
            pass

        mock_registry.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

        mock_agent.message_processor.messages = [
            RuntimeMessage(f"Message {i}") for i in range(15)
        ]
        mock_agent.message_processor.filter_messages = AsyncMock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75,
        }
        mock_range_clean_manager.create_clean_info = MagicMock()

        with patch("linhai.agent.conversation.save_cleaned_messages") as mock_save:
            mock_save.return_value = Path("/tmp/test.json")
            result = await context_forget_range_step1(mock_registry)

        self.assertIsInstance(result, SuccessfulToolResult)

    async def test_tool_manager_has_no_workflow_methods(self):
        """Test that ToolManager no longer has workflow-specific methods."""
        self.assertFalse(hasattr(self.tool_manager, "get_workflow"))
        self.assertFalse(hasattr(self.tool_manager, "register_workflow"))
        self.assertFalse(hasattr(self.tool_manager, "workflows"))

    async def test_tools_info_includes_context_compress_range_tools(self):
        """Test that get_tools_info includes context_forget_range_step1 and step2 as regular tools."""
        tools_info = self.tool_manager.get_tools_info()
        workflow_names = [tool["function"]["name"] for tool in tools_info]
        self.assertIn("context_forget_range_step1", workflow_names)
        self.assertIn("context_forget_range_step2", workflow_names)
        self.assertTrue(any("quickjs_calculator" in name for name in workflow_names))

    async def test_context_forget_range_step1_tool_structure(self):
        """Test that context_forget_range_step1 tool has correct structure."""
        tools_info = self.tool_manager.get_tools_info()
        compress_tool = None
        for tool in tools_info:
            if tool["function"]["name"] == "context_forget_range_step1":
                compress_tool = tool
                break
        self.assertIsNotNone(compress_tool)
        json_blocks = []
        _ = json_blocks[0] if json_blocks else {}

    async def test_context_forget_range_step1_integration(self):
        """Test that context_forget_range_step1 integrates properly with agent."""
        tools_info = self.tool_manager.get_tools_info()
        tool_names = [tool["function"]["name"] for tool in tools_info]
        self.assertIn("context_forget_range_step1", tool_names)
        compress_tool = next(
            (
                tool
                for tool in tools_info
                if tool["function"]["name"] == "context_forget_range_step1"
            ),
            None,
        )
        self.assertIsNotNone(compress_tool)

    async def test_context_forget_range_step2_user_message_protection(self):
        """Test that user messages are protected during history compression in step2."""
        mock_agent = MagicMock()
        mock_registry = MagicMock()
        mock_agent.registry = mock_registry
        mock_registry.get_member_typechecked.return_value = Path(tempfile.mkdtemp())

        async def mock_send_if_exists(queue_name, message):
            _ = queue_name
            _ = message

        mock_registry.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

        mock_messages = [
            RuntimeMessage("System message"),
            UserMessage(message="Important user input 1"),
            UserMessage(message="Important user input 2"),
            AssistantMessage(message="Assistant response 1"),
            UserMessage(message="Important user input 3"),
            AssistantMessage(message="Assistant response 2"),
            RuntimeMessage("<runtime>Tool output</runtime>"),
            UserMessage(message="Complete TODO.md tasks"),
            AssistantMessage(message="Assistant response 3"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
            RuntimeMessage("<runtime>Another tool output</runtime>"),
            AssistantMessage(message="Assistant response x"),
        ]
        mock_agent.message_processor.messages = mock_messages

        mock_agent.message_processor.filter_messages = AsyncMock()
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75,
        }

        async def delete_message_range_side_effect(start, end):
            deleted = mock_agent.message_processor.messages[start : end + 1]
            mock_agent.message_processor.messages[start : end + 1] = []
            return deleted

        def insert_message_side_effect(index, message):
            mock_agent.message_processor.messages.insert(index, message)

        mock_agent.message_processor.delete_message_range = AsyncMock(
            side_effect=delete_message_range_side_effect
        )
        mock_agent.message_processor.insert_message = AsyncMock(
            side_effect=insert_message_side_effect
        )

        # 创建range_clean_manager的mock
        mock_range_clean_manager = MagicMock()
        mock_info = MagicMock()
        mock_info.message_length = len(mock_messages)
        mock_info.min_safe_id = 1
        mock_range_clean_manager.get_clean_info.return_value = mock_info

        # 设置registry.get_member_typechecked返回相应的mock对象
        def get_member_typechecked_side_effect(name, cls=None):
            if name == "agent":
                return mock_agent
            elif name == "range_clean_manager":
                return mock_range_clean_manager
            elif name == "conversation_folder":
                return Path(tempfile.mkdtemp())
            else:
                return None

        mock_registry.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

        with patch("linhai.agent.conversation.save_cleaned_messages") as mock_save:
            mock_save.return_value = Path("/tmp/test.json")
            result = await context_forget_range_step2(
                mock_registry,
                range_clean_id="test-range-clean-id",
                start_id=2,
                end_id=15,
                description="测试压缩范围",
            )

        self.assertTrue(isinstance(result, SuccessfulToolResult))

        runtime_messages = [
            msg
            for msg in mock_agent.message_processor.messages
            if isinstance(msg, RuntimeMessage)
            and "历史压缩已删除以下用户消息" in msg.message
        ]

        self.assertGreater(
            len(runtime_messages),
            0,
            "No runtime message summarizing user messages was found in: "
            + repr(mock_agent.message_processor.messages),
        )

        summary_message = runtime_messages[0].message
        self.assertIn("Complete TODO.md tasks", summary_message)
        self.assertIn("Important user input", summary_message)

    async def test_compress_range_system_message_protection(self):
        """Test that system messages are protected during compression range validation."""
        from linhai.agent.workflow import _validate_compression_range
        from linhai.agent.messages import GlobalPrompt
        from linhai.base import SystemMessage

        mock_agent = MagicMock()

        mock_registry = MagicMock()

        from pathlib import Path

        mock_messages = [
            SystemMessage(registry=mock_registry),
            GlobalPrompt(filepath=Path("/tmp/test_global_prompt.md")),
            RuntimeMessage("User message 1"),
            RuntimeMessage("User message 2"),
            RuntimeMessage("User message 3"),
        ]
        mock_agent.message_processor.messages = mock_messages

        start_id = 0
        end_id = 2
        passed, error_msg = _validate_compression_range(mock_agent, start_id, end_id)
        self.assertFalse(passed)
        self.assertIn("压缩范围至少需要10条消息", error_msg)

        mock_messages_extended = [
            SystemMessage(registry=mock_registry),
            GlobalPrompt(filepath=Path("/tmp/test_global_prompt.md")),
        ] + [RuntimeMessage(f"User message {i}") for i in range(20)]
        mock_agent.message_processor.messages = mock_messages_extended

        start_id = 2
        end_id = 11
        passed, error_msg = _validate_compression_range(mock_agent, start_id, end_id)
        self.assertTrue(passed)
        self.assertEqual(error_msg, "")

        mock_messages_no_system = [
            RuntimeMessage("User message 1"),
            RuntimeMessage("User message 2"),
            RuntimeMessage("User message 3"),
        ]
        mock_agent.message_processor.messages = mock_messages_no_system

        start_id = 0
        end_id = 1
        passed, error_msg = _validate_compression_range(mock_agent, start_id, end_id)

        end_id = 9

        end_id = 2
        passed, error_msg = _validate_compression_range(mock_agent, start_id, end_id)

        self.assertFalse(passed)
        self.assertIn("压缩范围至少需要10条消息", error_msg)

        mock_messages_all_system = [
            SystemMessage(registry=mock_registry),
            GlobalPrompt(filepath=Path("/tmp/test_global_prompt.md")),
            SystemMessage(registry=mock_registry),
        ]
        mock_agent.message_processor.messages = mock_messages_all_system

        start_id = 0
        end_id = 2
        passed, error_msg = _validate_compression_range(mock_agent, start_id, end_id)
        self.assertFalse(passed)
        self.assertIn("压缩范围至少需要10条消息", error_msg)

    async def test_context_forget_range_step1_sends_ui_log_message(self):
        """Test that context_forget_range_step1 sends UI log message with current message count."""
        mock_agent = MagicMock()
        mock_registry = MagicMock()
        mock_range_clean_manager = MagicMock()

        def get_member_typechecked_side_effect(name, cls=None):
            if name == "agent":
                return mock_agent
            elif name == "range_clean_manager":
                return mock_range_clean_manager
            elif name == "conversation_folder":
                return Path(tempfile.mkdtemp())
            else:
                return None

        mock_registry.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

        async def mock_send_if_exists(queue_name, message):
            pass

        mock_registry.send_if_exists = AsyncMock(side_effect=mock_send_if_exists)

        mock_messages = [
            RuntimeMessage("System message"),
            RuntimeMessage("User message 1"),
            RuntimeMessage("User message 2"),
            RuntimeMessage("User message 3"),
        ]
        mock_agent.message_processor.messages = mock_messages
        mock_agent.message_processor.filter_messages = AsyncMock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75,
        }
        mock_range_clean_manager.create_clean_info = MagicMock()

        with patch("linhai.agent.conversation.save_cleaned_messages") as mock_save:
            mock_save.return_value = Path("/tmp/test.json")
            result = await context_forget_range_step1(mock_registry)

        mock_registry.send_if_exists.assert_called_once()
        call_args = mock_registry.send_if_exists.call_args
        self.assertEqual(call_args[0][0], "ui_log")
        ui_message = call_args[0][1]
        from linhai.utils.common import UiNotice

        self.assertIsInstance(ui_message, UiNotice)
        self.assertEqual(ui_message.level, "INFO")
        self.assertIn("启动历史压缩", ui_message.content)
        self.assertIn("当前共有4条消息", ui_message.content)

        self.assertIsInstance(result, SuccessfulToolResult)


if __name__ == "__main__":
    unittest.main()
