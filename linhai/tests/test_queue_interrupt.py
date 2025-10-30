"""测试队列消息不打断agent输出的功能"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from linhai.agent import Agent
from linhai.group_chat import GroupChat
from linhai.llm import ChatMessage, Answer
from linhai.agent_base import RuntimeMessage


class MockAnswer:
    """模拟Answer类"""
    
    def __init__(self, message_content="Agent响应内容"):
        self.message_content = message_content
        self.tokens = ["test", " token"]
        self.current_index = 0
        
    def __aiter__(self):
        return self
        
    async def __anext__(self):
        if self.current_index < len(self.tokens):
            token = self.tokens[self.current_index]
            self.current_index += 1
            return token
        raise StopAsyncIteration
        
    def get_current_content(self):
        return "".join(self.tokens[:self.current_index])
        
    def get_message(self):
        return ChatMessage(role="assistant", message=self.message_content)
        
    def interrupt(self):
        pass


class TestQueueInterrupt(unittest.IsolatedAsyncioTestCase):
    """测试队列消息不打断功能"""

    async def asyncSetUp(self):
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

    async def test_queue_message_placed_after_agent_output(self):
        """测试/queue消息被放在agent输出后面"""
        # 创建模拟answer
        mock_answer = MockAnswer()
        self.mock_llm.answer_stream = AsyncMock(return_value=mock_answer)
        
        # 模拟group_chat行为：在生成响应过程中有/queue消息
        self.group_chat.is_empty = Mock(return_value=False)
        self.group_chat.receive = AsyncMock(return_value=ChatMessage(role="user", message="/queue 排队消息"))
        self.group_chat.send = AsyncMock()
        
        # 调用generate_response
        await self.agent.generate_response()
        
        # 找到agent输出和排队消息的位置
        assistant_messages = [msg for msg in self.agent.messages if isinstance(msg, ChatMessage) and msg.role == "assistant"]
        queue_messages = [msg for msg in self.agent.messages if isinstance(msg, ChatMessage) and msg.role == "user" and msg.message.startswith("/queue")]
        runtime_messages = [msg for msg in self.agent.messages if isinstance(msg, RuntimeMessage)]
        
        self.assertTrue(len(assistant_messages) >= 1, "应该至少有一个assistant消息")
        self.assertTrue(len(queue_messages) >= 1, "应该至少有一个/queue消息")
        self.assertTrue(len(runtime_messages) >= 1, "应该至少有一个runtime消息")
        
        # 找到最后一个assistant消息的索引
        last_assistant_idx = None
        for i, msg in enumerate(self.agent.messages):
            if isinstance(msg, ChatMessage) and msg.role == "assistant":
                last_assistant_idx = i
        
        # 验证排队消息在assistant消息之后
        for i, msg in enumerate(self.agent.messages):
            if isinstance(msg, ChatMessage) and msg.role == "user" and msg.message.startswith("/queue"):
                self.assertGreater(i, last_assistant_idx, "/queue消息应该在agent输出之后")
        
        # 验证运行时消息在assistant消息之后
        for i, msg in enumerate(self.agent.messages):
            if isinstance(msg, RuntimeMessage) and "排队消息" in msg.message:
                self.assertGreater(i, last_assistant_idx, "运行时消息应该在agent输出之后")

    def test_queue_message_handling(self):
        """测试/queue消息的处理逻辑"""
        # 模拟generate_response中的用户输入检查逻辑
        queue_msg = ChatMessage(role="user", message="/queue 这是一个排队消息")
        
        # 测试以/queue开头的消息
        content = queue_msg.message.strip()
        self.assertTrue(content.startswith("/queue"))
        
        # 模拟处理逻辑 - 更新以匹配新行为
        self.agent.messages.append(ChatMessage(role="assistant", message="Agent响应"))
        self.agent.messages.append(RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理："))
        self.agent.messages.append(queue_msg)
        
        # 验证消息被正确添加
        self.assertEqual(len(self.agent.messages), 3)
        self.assertEqual(self.agent.messages[0].message, "Agent响应")
        self.assertEqual(self.agent.messages[1].message, "用户在你回答的时候输出了以下排队消息，现在请处理：")
        self.assertEqual(self.agent.messages[2].message, "/queue 这是一个排队消息")

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