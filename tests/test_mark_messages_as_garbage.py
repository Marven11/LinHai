import unittest
from unittest.mock import Mock



from linhai.agent import Agent, AgentContext

from linhai.group_chat import GroupChat
from linhai.llm import UserMessage, AssistantMessage
from linhai.agent.base import RuntimeMessage
from linhai.tool.main import ToolManager


class TestMarkMessagesAsGarbage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.group_chat = Mock(spec=GroupChat)
        self.group_chat.register_queue = Mock()
        self.group_chat.register_member = Mock()
        
        # 创建一个mock的lifecycle对象
        self.mock_lifecycle = Mock()
        self.mock_lifecycle.register_after_working = Mock()
        
        # 创建一个mock的tool_manager对象
        from linhai.tool.main import ToolManager
        self.mock_tool_manager = Mock(spec=ToolManager)
        
        # 让get_members根据请求的类型返回不同的mock
        def get_members_side_effect(name, expected_type):
            if name == "lifecycle":
                return self.mock_lifecycle
            else:
                return self.mock_tool_manager
        
        self.group_chat.get_members = Mock(side_effect=get_members_side_effect)
        
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
        result = self.agent.orchestration.mark_messages_as_garbage(["nonexistent-id"])
        self.assertIn("以下ID不存在: nonexistent-id", result)

    def test_mark_existing_messages(self):
        large_message = RuntimeMessage("x" * 30001)  # 大于30000字符
        test_id = self.agent.orchestration.record_large_message(large_message, "x" * 30001)
        self.agent.message_processor.append_message(large_message)
        
        result = self.agent.orchestration.mark_messages_as_garbage([test_id])
        self.assertIn("已成功标记 1 条消息为垃圾消息", result)
        self.assertIn(f"ID为{test_id}的消息已被标记为垃圾", result)

    async def test_message_garbage_clean(self):
        large_message = RuntimeMessage("x" * 30001)  # 大于30000字符
        test_id = self.agent.orchestration.record_large_message(large_message, "x" * 30001)
        self.agent.message_processor.append_message(large_message)
        
        self.agent.orchestration.mark_messages_as_garbage([test_id])
        
        result = await self.agent.orchestration.message_garbage_clean()
        self.assertIn("已清理 1 条消息", result)
        self.assertNotIn(test_id, self.agent.orchestration.large_messages)
