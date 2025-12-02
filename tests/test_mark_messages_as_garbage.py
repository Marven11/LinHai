import unittest
from unittest.mock import Mock



from linhai.agent import Agent, AgentContext

from linhai.group_chat import GroupChat
from linhai.llm import UserMessage, AssistantMessage
from linhai.agent.base import RuntimeMessage
from linhai.tool.main import ToolManager


class TestMarkMessagesAsGarbage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # 创建模拟group_chat和config
        self.group_chat = Mock(spec=GroupChat)
        self.group_chat.register_queue = Mock()
        self.group_chat.register_member = Mock()
        self.group_chat.get_members = Mock(return_value=Mock(spec=ToolManager))
        
        self.config: AgentContext = {
            "system_prompt": "Test prompt",
            "llms": [],
            "llm_names": [],
            "current_llm_index": 0,
            "compress_threshold_soft": 1000,
            "compress_threshold_hard": 2000,
        }
        self.init_messages = [UserMessage(message="Test")]
        
        self.agent = Agent(
            context=self.config,
            group_chat=self.group_chat,
            init_messages=self.init_messages,
        )

    def test_mark_nonexistent_messages(self):
        # 测试标记不存在的ID
        result = self.agent.message_processor.mark_messages_as_garbage(["nonexistent-id"])
        self.assertIn("以下ID不存在: nonexistent-id", result)

    def test_mark_existing_messages(self):
        # 测试标记存在的消息
        large_message = RuntimeMessage("x" * 30001)  # 大于30000字符
        test_id = self.agent.message_processor.record_large_message(large_message, "x" * 30001)
        self.agent.message_processor.append_message(large_message)
        
        # 调用标记工具
        result = self.agent.message_processor.mark_messages_as_garbage([test_id])
        self.assertIn("已成功标记 1 条消息为垃圾消息", result)
        self.assertIn(f"ID为{test_id}的消息已被标记为垃圾", result)

    async def test_message_garbage_clean(self):
        # 测试清理垃圾消息
        large_message = RuntimeMessage("x" * 30001)  # 大于30000字符
        test_id = self.agent.message_processor.record_large_message(large_message, "x" * 30001)
        self.agent.message_processor.append_message(large_message)
        
        # 先标记为垃圾
        self.agent.message_processor.mark_messages_as_garbage([test_id])
        
        # 然后清理垃圾消息
        result = await self.agent.message_processor.message_garbage_clean()
        self.assertIn("已清理所有消息", result)
        # 垃圾消息应该被删除
        self.assertNotIn(test_id, self.agent.message_processor.large_messages)
