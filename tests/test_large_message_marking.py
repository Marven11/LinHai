import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.agent.message import AgentMessage
from linhai.registry import Registry
from linhai.agent.base import RuntimeMessage
from linhai.llm import UserMessage, AssistantMessage, SystemMessage
from linhai.tool.base import ToolCallResultMessage
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.tool.main import ToolManager
from linhai.token_manager import TokenManager
from linhai.multimodal import ImageMessage


class TestLargeMessageMarking(unittest.IsolatedAsyncioTestCase):
    """大消息标记和清理功能的单元测试。"""

    def setUp(self):
        self.registry = Registry()

        # 注册必要的mock组件
        from linhai.agent.lifecycle import Lifecycle

        mock_lifecycle = Mock(spec=Lifecycle)
        mock_lifecycle.trigger_before_add_new_message = AsyncMock(
            side_effect=lambda msg: msg
        )
        mock_lifecycle.trigger_before_cache_invalidate = AsyncMock(return_value=None)
        mock_lifecycle.trigger_after_cache_invalidate = AsyncMock(return_value=None)
        self.registry.register_member("lifecycle", mock_lifecycle)

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
        self.mock_tokenizer_patcher = patch(
            "linhai.agent.orchestration.get_cl100k_base_tokenizer"
        )
        self.mock_tokenizer = self.mock_tokenizer_patcher.start()
        self.mock_encoder = Mock()
        self.mock_encoder.encode.return_value = []
        self.mock_tokenizer.return_value = self.mock_encoder

        self.orchestration = AgentContextOrchestration(
            self.registry, self.message_processor
        )

    def tearDown(self):
        """清理测试环境。"""
        self.mock_tokenizer_patcher.stop()

    async def test_mark_long_message(self):
        """测试长消息（token长度>800）被标记。"""
        # 模拟tiktoken编码，让消息的token长度超过800
        mock_encoder = self.mock_encoder
        mock_encoder.encode.return_value = list(range(1000))  # 1000个token

        # 创建一个长消息（内容长度不重要，因为编码被模拟）
        long_message = RuntimeMessage("A" * 10)  # 内容很短，但编码返回1000个token

        # 触发_before_add_new_message回调
        await self.orchestration._before_add_new_message(long_message)

        # 验证消息被标记为大消息
        self.assertIn(long_message, self.orchestration.large_messages)
        self.assertEqual(len(self.orchestration.large_messages), 1)

    async def test_do_not_mark_short_message(self):
        """测试短消息（token长度<=800）不被标记。"""
        self.mock_encoder.encode.return_value = list(range(500))

        short_message = RuntimeMessage("Short message")

        await self.orchestration._before_add_new_message(short_message)

        self.assertNotIn(short_message, self.orchestration.large_messages)
        self.assertEqual(len(self.orchestration.large_messages), 0)

        self.mock_encoder.encode.return_value = []

    async def test_delete_large_messages(self):
        """测试删除大消息时，消息从数组中移除且其余消息不变。"""
        # 先添加50条普通消息，确保后面的大消息在recent_count=20之外
        # 需要在5个大消息之前至少有20条消息，才能让大消息被清理
        for i in range(50):
            msg = RuntimeMessage(f"Regular message {i}")
            await self.message_processor.add_new_message(msg)

        # 添加一些普通消息
        msg1 = Mock()
        msg1.to_json = lambda: '{"role": "user", "message": "Message 1"}'
        msg1.__class__.__name__ = "UserMessage"
        msg2 = Mock()
        msg2.to_json = lambda: '{"role": "user", "message": "Message 2"}'
        msg2.__class__.__name__ = "UserMessage"
        msg3 = Mock()
        msg3.to_json = lambda: '{"role": "assistant", "message": "Response 1"}'
        msg3.__class__.__name__ = "AssistantMessage"

        await self.message_processor.add_new_message(msg1)
        await self.message_processor.add_new_message(msg2)
        await self.message_processor.add_new_message(msg3)

        # 添加5个大消息
        large_msgs = []
        for i in range(5):
            msg = Mock()
            msg.to_json = lambda i=i: f'{{"content": "Large {i}"}}'
            msg.__class__.__name__ = "RuntimeMessage"
            large_msgs.append(msg)
            self.orchestration.large_messages.add(msg)
            await self.message_processor.add_new_message(msg)

        # 再添加25条普通消息，把大消息推出recent_count=20的范围
        for i in range(25):
            msg = RuntimeMessage(f"After large message {i}")
            await self.message_processor.add_new_message(msg)

        # 初始消息总数：50 + 3个普通 + 5个大 + 25个后续 = 83个，加上2个初始pinned
        initial_messages = self.message_processor.messages.copy()

        # 模拟不足5条可清理的大消息（4条）
        with patch.object(
            self.orchestration, "large_messages", {"fake1", "fake2", "fake3", "fake4"}
        ):
            result = await self.orchestration.context_forget_large_message()
            # 由于大消息数量不足5，应该返回失败
            self.assertIsInstance(result, ToolResultFailed)

        # 执行清理（现在有5条大消息且都在可清理范围内）
        result = await self.orchestration.context_forget_large_message()
        self.assertIsInstance(result, ToolResultSuccess)

        # 验证大消息集合已清空（5条都被清理了）
        self.assertEqual(len(self.orchestration.large_messages), 0)

        # 验证消息数组中不再包含大消息
        remaining_messages = self.message_processor.messages
        for msg in large_msgs:
            self.assertNotIn(msg, remaining_messages)

        # 验证其他消息保持不变
        self.assertIn(msg1, remaining_messages)
        self.assertIn(msg2, remaining_messages)
        self.assertIn(msg3, remaining_messages)

        # 验证消息顺序和数量
        # 50 + 3个普通 + 25个后续消息应该保留，5个大消息被替换为占位符
        # 2个初始消息也在pinned_messages中
        # 总共: 50 + 3 + 25 + 2 = 80，加上5个占位符 = 85，但大消息被替换所以是80
        self.assertEqual(len(remaining_messages), 83)


if __name__ == "__main__":
    unittest.main()
