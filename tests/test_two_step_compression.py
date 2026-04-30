"""Unit tests for two-step compression functionality."""

import unittest
import time
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from linhai.agent import Agent
from linhai.agent.messages import RuntimeMessage, MessagesListSummerizeMessage
from linhai.agent.workflow import (
    context_forget_range_step1,
    context_forget_range_step2,
    RangeCleanManager,
    RangeCleanInfo,
    _prepare_messages_for_compression,
    _validate_compression_range,
)
from linhai.base import UserMessage, AssistantMessage, SystemMessage
from linhai.tool.main import ToolManager
from linhai.tool.base import utils_tools, SuccessfulToolResult, FailedToolResult
from linhai.registry import Registry
from linhai.agent.messages import GlobalPrompt


class TestTwoStepCompressionBasic(unittest.IsolatedAsyncioTestCase):
    """Basic tests for two-step compression functionality."""

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

        # Clear any existing clean info - not needed as tests use mock instances

    async def test_step1_creates_range_clean_id(self):
        """Test that step1 creates a valid range_clean_id."""
        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry

        # Mock get_members to return appropriate objects based on arguments
        def mock_get_member_typechecked(member_type, member_class=None):
            if member_type == "agent":
                return mock_agent
            elif member_type == "range_clean_manager":
                mock_manager = MagicMock(spec=RangeCleanManager)
                mock_manager.create_clean_info = MagicMock()
                return mock_manager
            elif member_type == "conversation_folder":
                return Path(tempfile.mkdtemp())
            else:
                raise ValueError(f"Unexpected member type: {member_type}")

        mock_registry.get_member_typechecked = MagicMock(
            side_effect=mock_get_member_typechecked
        )

        mock_registry.send_if_exists = AsyncMock()

        mock_messages = [
            SystemMessage(registry=mock_registry),
            GlobalPrompt(filepath=Path("/tmp/test.md")),
        ] + [
            RuntimeMessage(f"User message {i}") for i in range(1, 16)
        ]  # 15 user messages + 2 system = 17 total

        # Create a mutable list for messages that can be modified by mocks
        messages_list = mock_messages.copy()
        mock_agent.message_processor.messages = messages_list

        # Mock filter_messages to remove MessagesListSummerizeMessage if present
        async def mock_filter_messages(filter_func):
            nonlocal messages_list
            messages_list[:] = [msg for msg in messages_list if filter_func(msg)]

        mock_agent.message_processor.filter_messages = AsyncMock(
            side_effect=mock_filter_messages
        )

        # Mock add_new_message to add messages to the list
        async def mock_add_new_message(msg):
            messages_list.append(msg)

        mock_agent.message_processor.add_new_message = AsyncMock(
            side_effect=mock_add_new_message
        )

        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 800,
            "used_tokens": 600,
            "remaining_tokens": 200,
            "usage_ratio": 0.75,
        }

        mock_response = MagicMock()
        mock_response.get_message.return_value = AssistantMessage(
            message="""
            压缩以下消息：
            ```json
            {"start_id": 2, "end_id": 4}
            ```
            """,
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        with patch("linhai.agent.workflow.save_cleaned_messages") as mock_save:
            mock_save.return_value = Path(tempfile.mktemp(suffix=".json"))
            result = await context_forget_range_step1(mock_registry)

        self.assertIsInstance(result, SuccessfulToolResult)
        self.assertIn("已生成消息列表总结，ID:", result.content)
        self.assertIn("当前共有17条消息", result.content)

        # Verify that a MessagesListSummerizeMessage was added
        added_message = None
        for msg in messages_list:
            if isinstance(msg, MessagesListSummerizeMessage):
                added_message = msg
                break

        self.assertIsNotNone(added_message)
        self.assertTrue(added_message.is_valid())
        self.assertEqual(added_message.message_length, 17)
        self.assertTrue(added_message.range_clean_id.startswith("rangeclean_"))

        # Verify that clean info was registered - in real scenario, it would be in RangeCleanManager instance
        # Since we're using mocks, we can't verify directly; we assume the manager is called

    async def test_step2_valid_range_clean_id(self):
        """Test that step2 works with a valid range_clean_id."""
        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry

        # Mock get_members to return appropriate objects based on arguments
        def mock_get_member_typechecked(member_type, member_class=None):
            if member_type == "agent":
                return mock_agent
            elif member_type == "range_clean_manager":
                mock_manager = MagicMock(spec=RangeCleanManager)
                mock_manager.get_clean_info = MagicMock(
                    return_value=RangeCleanInfo(
                        range_clean_id="test_range_clean_id",
                        message_length=18,  # 2 system + 15 user + 1 summerize = 18
                        min_safe_id=2,
                        created_at=time.time(),
                    )
                )
                mock_manager.remove_clean_info = MagicMock()
                return mock_manager
            elif member_type == "conversation_folder":
                return Path(tempfile.mkdtemp())
            else:
                raise ValueError(f"Unexpected member type: {member_type}")

        mock_registry.get_member_typechecked = MagicMock(
            side_effect=mock_get_member_typechecked
        )

        mock_registry.send_if_exists = AsyncMock()

        # Create messages with a MessagesListSummerizeMessage
        summerize_message = MessagesListSummerizeMessage(
            messages_summerization="Test summary",
            message_length=10,
            range_clean_id="test_range_clean_id",
        )

        mock_messages = [
            SystemMessage(registry=mock_registry),
            GlobalPrompt(filepath=Path("/tmp/test.md")),
        ] + [
            RuntimeMessage(f"Message {i}") for i in range(1, 16)
        ]  # 15 user messages + 2 system = 17 total
        mock_messages.append(summerize_message)
        mock_agent.message_processor.messages = mock_messages

        mock_agent.message_processor.delete_message_range = AsyncMock(
            return_value=mock_messages[2:12]  # Delete range 2-11 (10 messages)
        )
        mock_agent.message_processor.insert_message = AsyncMock()

        with patch("linhai.agent.workflow.save_cleaned_messages") as mock_save:
            mock_save.return_value = Path("/tmp/test.json")
            result = await context_forget_range_step2(
                mock_registry,
                range_clean_id="test_range_clean_id",
                start_id=2,
                end_id=11,  # Delete 10 messages (2-11)
                description="Test compression",
            )

        self.assertIsInstance(result, SuccessfulToolResult)

        # Verify summerize message was invalidated
        self.assertFalse(summerize_message.is_valid())

    async def test_step2_invalid_range_clean_id(self):
        """Test that step2 fails with an invalid range_clean_id."""
        mock_registry = MagicMock()

        # Mock get_members to return appropriate objects based on arguments
        def mock_get_member_typechecked(member_type, member_class=None):
            if member_type == "agent":
                mock_agent = MagicMock()
                mock_agent.message_processor.messages = []
                return mock_agent
            elif member_type == "range_clean_manager":
                mock_manager = MagicMock(spec=RangeCleanManager)
                mock_manager.get_clean_info = MagicMock(return_value=None)
                return mock_manager
            else:
                raise ValueError(f"Unexpected member type: {member_type}")

        mock_registry.get_member_typechecked = MagicMock(
            side_effect=mock_get_member_typechecked
        )

        result = await context_forget_range_step2(
            mock_registry,
            range_clean_id="invalid_id",
            start_id=2,
            end_id=7,
            description="Test compression",
        )

        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("range_clean_id无效或已过期", result.content)

    async def test_step2_out_of_range(self):
        """Test that step2 fails when start_id/end_id are out of allowed range."""
        mock_registry = MagicMock()

        # Mock get_members to return appropriate objects based on arguments
        def mock_get_member_typechecked(member_type, member_class=None):
            if member_type == "agent":
                mock_agent = MagicMock()
                mock_agent.message_processor.messages = [
                    SystemMessage(registry=mock_registry),
                    GlobalPrompt(filepath=Path("/tmp/test.md")),
                    RuntimeMessage("Message 1"),
                    RuntimeMessage("Message 2"),
                    RuntimeMessage("Message 3"),
                    RuntimeMessage("Message 4"),
                    RuntimeMessage("Message 5"),
                    RuntimeMessage("Message 6"),
                ]
                return mock_agent
            elif member_type == "range_clean_manager":
                mock_manager = MagicMock(spec=RangeCleanManager)
                mock_manager.get_clean_info = MagicMock(
                    return_value=RangeCleanInfo(
                        range_clean_id="test_range_clean_id",
                        message_length=10,
                        min_safe_id=2,
                        created_at=time.time(),
                    )
                )
                return mock_manager
            else:
                raise ValueError(f"Unexpected member type: {member_type}")

        mock_registry.get_member_typechecked = MagicMock(
            side_effect=mock_get_member_typechecked
        )

        # Try to delete beyond current bounds (end_id=9, but max is 7)
        result = await context_forget_range_step2(
            mock_registry,
            range_clean_id="test_range_clean_id",
            start_id=2,
            end_id=9,  # Beyond current max of 7
            description="Test compression",
        )

        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("end_id必须在", result.content)

    async def test_range_clean_manager_functionality(self):
        """Test RangeCleanManager basic functionality."""
        mock_registry = MagicMock()
        manager = RangeCleanManager(mock_registry)

        # Test creation and retrieval
        info = manager.create_clean_info("test_id", 10, 2)
        self.assertIsInstance(info, RangeCleanInfo)
        self.assertEqual(info.range_clean_id, "test_id")
        self.assertEqual(info.message_length, 10)
        self.assertEqual(info.min_safe_id, 2)

        # Test retrieval
        retrieved = manager.get_clean_info("test_id")
        self.assertEqual(retrieved, info)

        # Test validity check
        self.assertTrue(manager.is_valid("test_id"))
        self.assertFalse(manager.is_valid("nonexistent_id"))

        # Test removal
        manager.remove_clean_info("test_id")
        self.assertIsNone(manager.get_clean_info("test_id"))
        self.assertFalse(manager.is_valid("test_id"))

    async def test_messages_list_summerize_message_format(self):
        """Test the LLM message format of MessagesListSummerizeMessage."""
        message = MessagesListSummerizeMessage(
            messages_summerization="Test summary content",
            message_length=15,
            range_clean_id="rangeclean_12345",
        )

        llm_message = message.to_llm_message()

        self.assertEqual(llm_message["role"], "user")
        content = llm_message["content"]

        # Check format markers
        self.assertIn("<<range_clean_summary>>", content)
        self.assertIn("<<range_clean_id>>rangeclean_12345<<range_clean_id>>", content)
        self.assertIn("<<message_count>>15<<message_count>>", content)
        self.assertIn("<<content>>", content)
        # Check that the prompt includes the summary content
        self.assertIn("Test summary content", content)

        # Test invalidation
        self.assertTrue(message.is_valid())
        message.invalidate()
        self.assertFalse(message.is_valid())

        # Invalid message should have different format
        invalid_message = message.to_llm_message()
        self.assertIn(
            "[消息列表已无效，ID: rangeclean_12345]", invalid_message["content"]
        )

    async def test_step1_with_few_messages(self):
        """Test step1 when there are few messages."""
        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry

        # Mock get_members to return appropriate objects
        def mock_get_member_typechecked(member_type, member_class=None):
            if member_type == "agent":
                return mock_agent
            elif member_type == "range_clean_manager":
                mock_manager = MagicMock(spec=RangeCleanManager)
                mock_manager.create_clean_info = MagicMock()
                return mock_manager
            elif member_type == "conversation_folder":
                return Path(tempfile.mkdtemp())
            else:
                raise ValueError(f"Unexpected member type: {member_type}")

        mock_registry.get_member_typechecked = MagicMock(
            side_effect=mock_get_member_typechecked
        )
        mock_registry.send_if_exists = AsyncMock()

        # Only 5 messages total
        mock_messages = [
            SystemMessage(registry=mock_registry),
            GlobalPrompt(filepath=Path("/tmp/test.md")),
            RuntimeMessage("Message 1"),
            RuntimeMessage("Message 2"),
            RuntimeMessage("Message 3"),
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

        mock_response = MagicMock()
        mock_response.get_message.return_value = AssistantMessage(
            message="""
            消息太少，无法压缩。
            """,
        )
        mock_agent.generate_response = AsyncMock(return_value=mock_response)

        with patch("linhai.agent.workflow.save_cleaned_messages") as mock_save:
            mock_save.return_value = Path(tempfile.mktemp(suffix=".json"))
            result = await context_forget_range_step1(mock_registry)

        # Should still succeed, even if LLM says there are too few messages
        self.assertIsInstance(result, SuccessfulToolResult)

    async def test_step2_user_message_protection_summary(self):
        """Test that step2 creates a summary of protected user messages."""
        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry

        # Mock get_members to return appropriate objects
        def mock_get_member_typechecked(member_type, member_class=None):
            if member_type == "agent":
                return mock_agent
            elif member_type == "range_clean_manager":
                mock_manager = MagicMock(spec=RangeCleanManager)
                mock_manager.get_clean_info = MagicMock(
                    return_value=RangeCleanInfo(
                        range_clean_id="test_range_clean_id",
                        message_length=15,  # 2 system + 12 user/runtime + 1 summerize = 15
                        min_safe_id=2,
                        created_at=time.time(),
                    )
                )
                mock_manager.remove_clean_info = MagicMock()
                return mock_manager
            elif member_type == "conversation_folder":
                return Path(tempfile.mkdtemp())
            else:
                raise ValueError(f"Unexpected member type: {member_type}")

        mock_registry.get_member_typechecked = MagicMock(
            side_effect=mock_get_member_typechecked
        )
        mock_registry.send_if_exists = AsyncMock()

        # Create messages with user messages that should be protected
        summerize_message = MessagesListSummerizeMessage(
            messages_summerization="Test summary",
            message_length=15,
            range_clean_id="test_range_clean_id",
        )

        # Create 15 total messages: 2 system + 12 user/runtime + 1 summerize = 15
        mock_messages = [
            SystemMessage(registry=mock_registry),
            GlobalPrompt(filepath=Path("/tmp/test.md")),
            UserMessage(message="Important task 1"),
            RuntimeMessage("Tool output 1"),
            RuntimeMessage("Tool output 2"),
            RuntimeMessage("Tool output 3"),
            RuntimeMessage("Tool output 4"),
            RuntimeMessage("Tool output 5"),
            RuntimeMessage("Tool output 6"),
            UserMessage(message="Important task 2"),
            RuntimeMessage("Tool output 7"),
            RuntimeMessage("Tool output 8"),
            RuntimeMessage("Tool output 9"),
            RuntimeMessage("Tool output 10"),
            summerize_message,
        ]

        # Create mutable list
        messages_list = mock_messages.copy()
        mock_agent.message_processor.messages = messages_list

        # Track deletions and insertions
        deleted_messages_list = []

        async def mock_delete_message_range(start, end):
            nonlocal messages_list
            deleted = messages_list[start : end + 1]
            messages_list[start : end + 1] = []
            deleted_messages_list.extend(deleted)
            return deleted

        inserted_messages_list = []

        async def mock_insert_message(index, message):
            nonlocal messages_list
            messages_list.insert(index, message)
            inserted_messages_list.append(message)

        mock_agent.message_processor.delete_message_range = AsyncMock(
            side_effect=mock_delete_message_range
        )
        mock_agent.message_processor.insert_message = AsyncMock(
            side_effect=mock_insert_message
        )

        with patch("linhai.agent.workflow.save_cleaned_messages") as mock_save:
            mock_save.return_value = Path("/tmp/test.json")
            result = await context_forget_range_step2(
                mock_registry,
                range_clean_id="test_range_clean_id",
                start_id=2,
                end_id=11,  # Delete 10 messages (2-11) to meet minimum requirement
                description="Test compression with user messages",
            )

        self.assertIsInstance(result, SuccessfulToolResult)

        # Check that a runtime message was inserted summarizing user messages
        user_message_summary_found = False
        for msg in inserted_messages_list:
            if isinstance(msg, RuntimeMessage) and "已删除以下用户消息" in msg.message:
                user_message_summary_found = True
                self.assertIn("Important task 1", msg.message)
                self.assertIn("Important task 2", msg.message)
                break

        self.assertTrue(
            user_message_summary_found, "No user message summary was created"
        )


if __name__ == "__main__":
    unittest.main()
