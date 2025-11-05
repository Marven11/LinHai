import unittest
from unittest.mock import Mock
import uuid

from linhai.agent import Agent, AgentConfig
from linhai.group_chat import GroupChat
from linhai.llm import ChatMessage
from linhai.agent_base import RuntimeMessage
from linhai.tool.main import ToolManager


class TestEraseMessageByUUID(unittest.TestCase):
    def setUp(self):
        # 创建模拟group_chat和config
        self.group_chat = Mock(spec=GroupChat)
        self.group_chat.register_queue = Mock()
        self.group_chat.register_member = Mock()
        self.group_chat.get_members = Mock(return_value=Mock(spec=ToolManager))
        
        self.config: AgentConfig = {
            "system_prompt": "Test prompt",
            "llms": [],
            "llm_names": [],
            "current_llm_index": 0,
            "compress_threshold_soft": 1000,
            "compress_threshold_hard": 2000,
        }
        self.init_messages = [ChatMessage(role="user", message="Test")]
        
        self.agent = Agent(
            config=self.config,
            group_chat=self.group_chat,
            init_messages=self.init_messages,
        )

    def test_delete_nonexistent_message(self):
        # 测试删除不存在的UUID
        result = self.agent.erase_message_by_uuid("nonexistent-uuid")
        self.assertIn("错误", result)
        self.assertEqual(result, "错误：ID 'nonexistent-uuid' 不存在，无法擦除消息。")

    def test_delete_existing_message(self):
        # 测试删除存在的消息
        test_uuid = str(uuid.uuid4())
        large_message = RuntimeMessage("x" * 30001)  # 大于30000字符
        self.agent.large_messages[test_uuid] = large_message
        self.agent.messages.append(large_message)
        
        # 调用删除工具
        result = self.agent.erase_message_by_uuid(test_uuid)
        self.assertIn("成功擦除", result)
        self.assertNotIn(test_uuid, self.agent.large_messages)
        self.assertNotIn(large_message, self.agent.messages)
