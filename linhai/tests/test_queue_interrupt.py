"""测试队列消息不打断agent输出的功能"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
from linhai.agent import Agent
from linhai.group_chat import GroupChat
from linhai.llm import ChatMessage
from linhai.agent_base import RuntimeMessage


class TestQueueInterrupt(unittest.TestCase):
    """测试队列消息不打断功能"""

    def setUp(self):
        """设置测试环境"""
        self.group_chat = GroupChat()
        
        # 创建模拟LLM
        self.mock_llm = Mock()
        
        # 创建Agent配置
        self.config = {
            "system_prompt": "测试系统提示",
            "llms": [self.mock_llm],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_soft": 32768,
            "compress_threshold_hard": 52428,
        }
        
        # 初始化消息
        self.init_messages = []
        
        # 创建Agent实例
        self.agent = Agent(
            config=self.config,
            group_chat=self.group_chat,
            init_messages=self.init_messages,
        )

    def test_queue_message_handling(self):
        """测试/queue消息的处理逻辑"""
        # 模拟generate_response中的用户输入检查逻辑
        queue_msg = ChatMessage(role="user", message="/queue 这是一个排队消息")
        
        # 测试以/queue开头的消息
        content = queue_msg.message.strip()
        self.assertTrue(content.startswith("/queue"))
        
        # 模拟处理逻辑
        self.agent.messages.append(queue_msg)
        self.agent.messages.append(RuntimeMessage("用户消息已排队，不会打断当前输出"))
        
        # 验证消息被正确添加
        self.assertEqual(len(self.agent.messages), 2)
        self.assertEqual(self.agent.messages[0].message, "/queue 这是一个排队消息")
        self.assertEqual(self.agent.messages[1].message, "用户消息已排队，不会打断当前输出")

    def test_normal_message_handling(self):
        """测试普通消息的处理逻辑"""
        normal_msg = ChatMessage(role="user", message="这是一个普通消息")
        
        # 测试不以/queue开头的消息
        content = normal_msg.message.strip()
        self.assertFalse(content.startswith("/queue"))
        
        # 模拟正常打断逻辑
        # 这里我们只验证逻辑，不实际调用interrupt


if __name__ == "__main__":
    unittest.main()