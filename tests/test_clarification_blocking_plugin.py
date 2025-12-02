"""测试ClarificationBlockingPlugin"""

import unittest
from unittest.mock import MagicMock

from linhai.subagent.plugin import ClarificationBlockingPlugin
from linhai.llm import Answer


class TestClarificationBlockingPlugin(unittest.IsolatedAsyncioTestCase):
    """测试ClarificationBlockingPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        self.agent.state = "working"
        
        self.clarification_manager = MagicMock()
        self.clarification_manager.has_unanswered_clarifications.return_value = False
        
        self.group_chat = MagicMock()
        def get_members_side_effect(member_type, _member_class=None):
            if member_type == "agent":
                return self.agent
            elif member_type == "clarification_manager":
                return self.clarification_manager
            return None
        self.group_chat.get_members = MagicMock(side_effect=get_members_side_effect)
        
        self.plugin = ClarificationBlockingPlugin(self.group_chat)
        self.answer = MagicMock(spec=Answer)

    async def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )

    async def test_with_unanswered_clarifications_and_waiting_marker(self):
        """测试有未解答澄清且使用等待标记的情况。"""
        self.clarification_manager.has_unanswered_clarifications.return_value = True
        full_response = "一些内容 #LINHAI_WAITING_USER"
        
        await self.plugin.after_message_generation(
            self.answer, full_response, []
        )
        
        self.agent.message_processor.append_message.assert_called_once()
        self.assertEqual(self.agent.state, "working")

    async def test_with_unanswered_clarifications_no_waiting_marker(self):
        """测试有未解答澄清但没有使用等待标记的情况。"""
        self.clarification_manager.has_unanswered_clarifications.return_value = True
        full_response = "一些内容"
        
        await self.plugin.after_message_generation(
            self.answer, full_response, []
        )
        
        self.agent.message_processor.append_message.assert_not_called()

    async def test_without_unanswered_clarifications(self):
        """测试没有未解答澄清的情况。"""
        self.clarification_manager.has_unanswered_clarifications.return_value = False
        full_response = "一些内容 #LINHAI_WAITING_USER"
        
        await self.plugin.after_message_generation(
            self.answer, full_response, []
        )
        
        self.agent.message_processor.append_message.assert_not_called()
        self.assertEqual(self.agent.state, "working")