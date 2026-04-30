import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.agent.message import AgentMessage
from linhai.registry import Registry
from linhai.agent.messages import RuntimeMessage
from linhai.base import UserMessage, AssistantMessage, SystemMessage
from linhai.tool.base import ToolCallResultMessage
from linhai.tool.base import SuccessfulToolResult, FailedToolResult
from linhai.tool.main import ToolManager
from linhai.token_manager import TokenManager
from linhai.multimodal import ImageMessage


class TestLargeMessageMarking(unittest.IsolatedAsyncioTestCase):
    """大消息标记和清理功能的单元测试。"""

    def setUp(self):
        self.registry = Registry()

        from linhai.agent.lifecycle import Lifecycle

        Lifecycle(self.registry)

        from linhai.agent.main import Agent

        mock_agent = Mock(spec=Agent)
        self.registry.register_member("agent", mock_agent)

        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []
        self.registry.register_member("tool_manager", mock_tool_manager)

        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.get_large_message_reprs = Mock(return_value=[])
        mock_token_manager.cumulative_token_usage = None
        self.registry.register_member("token_manager", mock_token_manager)

        # 注册llm_manager（mock），用于is_explicit_cache_enabled
        from linhai.llm_manager import LlmManager

        mock_llm_manager = Mock(spec=LlmManager)
        mock_llm = Mock()
        mock_llm.get_explicit_cache_info = Mock(return_value=None)
        mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)
        self.registry.register_member("llm_manager", mock_llm_manager)

        from pathlib import Path
        import tempfile

        temp_dir = tempfile.mkdtemp()
        conversation_folder = Path(temp_dir)
        self.registry.register_member("conversation_folder", conversation_folder)

        self.pinned_messages = [
            SystemMessage(registry=self.registry),
            UserMessage(message="Initial message"),
        ]
        self.message_processor = AgentMessage(self.registry, self.pinned_messages)
        self.mock_count_tokens_patcher = patch(
            "linhai.agent.orchestration.count_tokens"
        )
        self.mock_count_tokens = self.mock_count_tokens_patcher.start()

        self.orchestration = AgentContextOrchestration(
            self.registry, self.message_processor
        )

    def tearDown(self):
        """清理测试环境。"""
        self.mock_count_tokens_patcher.stop()

    async def test_mark_long_message(self):
        """测试长消息（token长度>800）被标记。"""
        self.mock_count_tokens.return_value = 1000

        # 创建一个长消息（内容长度不重要，因为编码被模拟）
        long_message = RuntimeMessage("A" * 10)  # 内容很短，但编码返回1000个token

        # 触发_before_add_new_message回调
        await self.orchestration._before_add_new_message(long_message)

        # 验证消息被标记为大消息
        self.assertIn(long_message, self.orchestration.large_messages)
        self.assertEqual(len(self.orchestration.large_messages), 1)

    async def test_do_not_mark_short_message(self):
        """测试短消息（token长度<=800）不被标记。"""
        self.mock_count_tokens.return_value = 500

        short_message = RuntimeMessage("Short message")

        await self.orchestration._before_add_new_message(short_message)

        self.assertNotIn(short_message, self.orchestration.large_messages)
        self.assertEqual(len(self.orchestration.large_messages), 0)

    async def test_do_not_mark_assistant_message(self):
        """测试AssistantMessage即使token很长也不被标记为大消息。"""
        self.mock_count_tokens.return_value = 10000

        assistant_message = AssistantMessage(message="A" * 10000)

        await self.orchestration._before_add_new_message(assistant_message)

        self.assertNotIn(assistant_message, self.orchestration.large_messages)
        self.assertEqual(len(self.orchestration.large_messages), 0)

    async def test_delete_large_messages(self):
        from linhai.agent.orchestration import check_cleanable_threshold
        from linhai.agent.messages import RuntimeMessage

        # 测试check_cleanable_threshold函数 - 消息数不足
        mock_msgs = [RuntimeMessage("test") for _ in range(2)]
        result, count, tokens = check_cleanable_threshold(mock_msgs)
        self.assertFalse(result)
        self.assertEqual(count, 2)

        # 测试check_cleanable_threshold函数 - 消息数满足但token不足
        self.mock_count_tokens.return_value = 1000
        mock_msgs = [RuntimeMessage("test") for _ in range(3)]
        result, count, tokens = check_cleanable_threshold(mock_msgs)
        self.assertFalse(result)
        self.assertEqual(count, 3)
        self.assertEqual(tokens, 3000)

        # 测试check_cleanable_threshold函数 - 满足条件
        self.mock_count_tokens.return_value = 5000
        mock_msgs = [RuntimeMessage("test") for _ in range(3)]
        result, count, tokens = check_cleanable_threshold(mock_msgs)
        self.assertTrue(result)
        self.assertEqual(count, 3)
        self.assertEqual(tokens, 15000)


if __name__ == "__main__":
    unittest.main()
