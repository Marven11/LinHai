import unittest
from unittest.mock import Mock



from linhai.agent import Agent, AgentContext

from linhai.group_chat import GroupChat
from linhai.llm import ChatMessage
from linhai.agent.base import RuntimeMessage
from linhai.tool.main import ToolManager


class TestEraseMessageByID(unittest.TestCase):
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
        self.init_messages = [ChatMessage(role="user", message="Test")]
        
        self.agent = Agent(
            context=self.config,
            group_chat=self.group_chat,
            init_messages=self.init_messages,
        )

    def test_delete_nonexistent_message(self):
        # 测试删除不存在的ID
        result = self.agent.message_processor.erase_message_by_id("nonexistent-id")
        self.assertIn("错误", result)
        self.assertEqual(result, "错误：ID 'nonexistent-id' 不存在，无法擦除消息。")

    def test_delete_existing_message(self):
        # 测试删除存在的消息
        large_message = RuntimeMessage("x" * 30001)  # 大于30000字符
        test_id = self.agent.message_processor.record_large_message(large_message, "x" * 30001)
        self.agent.message_processor.append_message(large_message)
        
        # 调用删除工具
        result = self.agent.message_processor.erase_message_by_id(test_id)
        self.assertIn("成功擦除", result)
        self.assertNotIn(test_id, self.agent.message_processor.large_messages)
        # 消息应该被替换为RuntimeMessage，而不是完全删除
        self.assertTrue(any(isinstance(msg, RuntimeMessage) and f"ID为{test_id}的消息已被擦除" in msg.message for msg in self.agent.message_processor.messages))
