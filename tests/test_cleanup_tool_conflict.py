import unittest
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.group_chat import GroupChat
from linhai.agent.message import AgentMessage
from linhai.llm import SystemMessage, UserMessage
from unittest.mock import Mock, AsyncMock
from linhai.agent.lifecycle import Lifecycle
from linhai.tool.main import ToolManager
from linhai.token_manager import TokenManager


class TestCleanupToolConflict(unittest.TestCase):
    def setUp(self):
        self.group_chat = GroupChat()
        mock_lifecycle = AsyncMock(spec=Lifecycle)
        mock_lifecycle.trigger_before_add_new_message.return_value = None
        self.group_chat.register_member("lifecycle", mock_lifecycle)
        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []
        self.group_chat.register_member("tool_manager", mock_tool_manager)
        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.get_large_message_reprs = Mock(return_value=[])
        mock_token_manager.cumulative_token_usage = None
        mock_token_manager.is_dirty = False
        self.group_chat.register_member("token_manager", mock_token_manager)
        from linhai.llm_manager import LlmManager

        mock_llm_manager = Mock(spec=LlmManager)
        mock_llm = Mock()
        mock_llm.get_explicit_cache_info = Mock(return_value=None)
        mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)
        self.group_chat.register_member("llm_manager", mock_llm_manager)
        from pathlib import Path
        from tempfile import TemporaryDirectory

        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.group_chat.register_member("conversation_folder", Path(self.temp_dir.name))
        init_messages = [
            SystemMessage(group_chat=self.group_chat),
            UserMessage(message="Initial message"),
        ]
        self.message_processor = AgentMessage(self.group_chat, init_messages)
        self.orchestration = AgentContextOrchestration(
            self.group_chat, self.message_processor
        )

    def test_conflict_with_parameter_exists(self):
        toolset = self.orchestration.get_context_cleaning_toolset()
        tools = toolset.get_tools()
        # 检查context_forget_large_message
        large_message_tool = tools.get("context_forget_large_message")
        self.assertIsNotNone(large_message_tool)
        self.assertIn("conflict_with", large_message_tool)
        self.assertEqual(
            set(large_message_tool["conflict_with"]),
            {"context_forget_range_step1", "context_forget_range_step2"},
        )
        # 检查context_forget_range_step1
        step1_tool = tools.get("context_forget_range_step1")
        self.assertIsNotNone(step1_tool)
        self.assertIn("conflict_with", step1_tool)
        self.assertEqual(
            set(step1_tool["conflict_with"]),
            {"context_forget_large_message", "context_forget_range_step2"},
        )
        # 检查context_forget_range_step2
        step2_tool = tools.get("context_forget_range_step2")
        self.assertIsNotNone(step2_tool)
        self.assertIn("conflict_with", step2_tool)
        self.assertEqual(
            set(step2_tool["conflict_with"]),
            {"context_forget_large_message", "context_forget_range_step1"},
        )

    def test_conflict_with_mutual_exclusion(self):
        toolset = self.orchestration.get_context_cleaning_toolset()
        tools = toolset.get_tools()
        large_message_tool = tools.get("context_forget_large_message")
        step1_tool = tools.get("context_forget_range_step1")
        step2_tool = tools.get("context_forget_range_step2")
        # 确保每个工具都列出了其他两个工具作为冲突
        self.assertEqual(
            set(large_message_tool["conflict_with"]),
            {"context_forget_range_step1", "context_forget_range_step2"},
        )
        self.assertEqual(
            set(step1_tool["conflict_with"]),
            {"context_forget_large_message", "context_forget_range_step2"},
        )
        self.assertEqual(
            set(step2_tool["conflict_with"]),
            {"context_forget_large_message", "context_forget_range_step1"},
        )


if __name__ == "__main__":
    unittest.main()
