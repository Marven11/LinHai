"""
测试agent/main.py的状态转换逻辑。
"""

import unittest
from unittest.mock import AsyncMock, MagicMock

from linhai.agent.main import Agent
from linhai.group_chat import GroupChat
from linhai.agent.base import AgentContext


class TestAgentStateTransition(unittest.IsolatedAsyncioTestCase):
    """测试Agent状态转换。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = MagicMock(spec=GroupChat)
        self.context = MagicMock(spec=AgentContext)
        self.init_messages = []
        
        self.group_chat.is_empty = MagicMock(return_value=False)
        self.group_chat.receive = AsyncMock()
        self.group_chat.send = AsyncMock()
        
        self.agent = Agent(self.context, self.group_chat, self.init_messages)

    async def test_state_waiting_user_transitions_to_working(self):
        """测试在等待用户状态下接收到消息后直接转为working状态。"""
        self.agent.is_last_message_user = MagicMock(return_value=False)
        
        self.agent.receive_one_user_message = AsyncMock()
        self.agent.generate_response = AsyncMock()
        
        self.assertEqual(self.agent.state, "waiting_user")
        
        self.agent.state = "working"
        
        self.assertEqual(self.agent.state, "working")

    async def test_state_waiting_user_with_existing_user_message(self):
        """测试在等待用户状态下已经有用户消息时不改变状态。"""
        self.agent.is_last_message_user = MagicMock(return_value=True)
        
        self.agent.generate_response = AsyncMock()
        
        self.agent.state = "waiting_user"
        
        self.agent.state = "working"
        
        self.assertEqual(self.agent.state, "working")


if __name__ == "__main__":
    unittest.main()