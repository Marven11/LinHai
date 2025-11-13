"""
测试agent/main.py的状态转换逻辑。
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from linhai.agent.main import Agent
from linhai.group_chat import GroupChat
from linhai.agent.base import AgentContext
from linhai.llm import ChatMessage


class TestAgentStateTransition(unittest.TestCase):
    """测试Agent状态转换。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = MagicMock(spec=GroupChat)
        self.context = MagicMock(spec=AgentContext)
        self.init_messages = []
        
        # 模拟group_chat的方法
        self.group_chat.is_empty = MagicMock(return_value=False)
        self.group_chat.receive = AsyncMock()
        self.group_chat.send = AsyncMock()
        
        # 创建Agent实例
        self.agent = Agent(self.context, self.group_chat, self.init_messages)

    @patch("linhai.agent.main.CliRuntimeNotice")
    @patch("linhai.agent.main.Agent.handle_user_message")
    @patch("linhai.agent.main.Agent.generate_response")
    async def test_state_waiting_user_transitions_to_working(self, mock_generate_response, mock_handle_user_message, mock_cli_runtime_notice):
        """测试在等待用户状态下接收到消息后直接转为working状态。"""
        # 设置模拟
        self.agent.is_last_message_user = MagicMock(return_value=False)
        mock_user_message = MagicMock(spec=ChatMessage)
        self.group_chat.receive.return_value = mock_user_message
        mock_generate_response.return_value = MagicMock()
        
        # 初始状态应该是waiting_user
        self.assertEqual(self.agent.state, "waiting_user")
        
        # 执行state_waiting_user方法
        await self.agent.state_waiting_user()
        
        # 验证状态已转为working
        self.assertEqual(self.agent.state, "working")
        
        # 验证用户消息被处理
        mock_handle_user_message.assert_called_once_with(mock_user_message)
        
        # 验证generate_response被调用
        mock_generate_response.assert_called_once()

    @patch("linhai.agent.main.Agent.generate_response")
    async def test_state_waiting_user_with_existing_user_message(self, mock_generate_response):
        """测试在等待用户状态下已经有用户消息时不改变状态。"""
        # 设置模拟
        self.agent.is_last_message_user = MagicMock(return_value=True)
        mock_generate_response.return_value = MagicMock()
        
        # 初始状态
        self.agent.state = "waiting_user"
        
        # 执行state_waiting_user方法
        await self.agent.state_waiting_user()
        
        # 验证状态保持不变（因为已经有用户消息，不需要接收新消息）
        self.assertEqual(self.agent.state, "waiting_user")
        
        # 验证generate_response被调用
        mock_generate_response.assert_called_once()


if __name__ == "__main__":
    unittest.main()