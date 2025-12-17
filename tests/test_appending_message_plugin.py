"""AppendingMessagePlugin类的单元测试。"""

import unittest
from unittest.mock import Mock, AsyncMock, patch

from linhai.agent.orchestration import AppendingMessagePlugin
from linhai.group_chat import GroupChat
from linhai.agent.main import Agent
from linhai.agent.message import AgentMessage
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.type_hints import ThresholdInfo


class TestAppendingMessagePlugin(unittest.IsolatedAsyncioTestCase):
    """AppendingMessagePlugin类的测试用例。"""

    async def asyncSetUp(self):
        """设置测试环境。"""
        self.group_chat = GroupChat()
        self.plugin = AppendingMessagePlugin(self.group_chat)
        
        # 创建模拟的Agent和AgentContextOrchestration
        self.agent = Mock(spec=Agent)
        self.agent.get_threshold_info = Mock()
        
        self.orchestration = Mock(spec=AgentContextOrchestration)
        self.orchestration.add_soft_threshold_notification = Mock()
        
        # 注册到group chat
        self.group_chat.register_member("agent", self.agent)
        self.group_chat.register_member("agent_context_orchestration", self.orchestration)

    async def test_after_message_generation_with_threshold_info(self):
        """测试有阈值信息时的消息生成后回调。"""
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 50000,
            "remaining_tokens": 50000,
            "usage_ratio": 0.5
        }
        self.agent.get_threshold_info.return_value = threshold_info
        
        await self.plugin.after_message_generation(
            Mock(), "test response", []
        )
        
        self.agent.get_threshold_info.assert_called_once()
        self.orchestration.add_soft_threshold_notification.assert_called_once_with(threshold_info)

    async def test_after_message_generation_without_threshold_info(self):
        """测试无阈值信息时的消息生成后回调。"""
        self.agent.get_threshold_info.return_value = None
        
        await self.plugin.after_message_generation(
            Mock(), "test response", []
        )
        
        self.agent.get_threshold_info.assert_called_once()
        self.orchestration.add_soft_threshold_notification.assert_not_called()

    def test_register(self):
        """测试插件注册。"""
        lifecycle = Mock()
        self.plugin.register(lifecycle)
        
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()