"""测试issue #10: 多条用户消息只触发一次打断并批量处理。"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, call

from linhai.agent.main import Agent
from linhai.group_chat import GroupChat
from linhai.llm import UserMessage


class TestIssue10MultipleMessages(unittest.IsolatedAsyncioTestCase):
    """测试多条用户消息的批量处理。"""

    async def asyncSetUp(self):
        """设置测试环境。"""
        self.group_chat = MagicMock(spec=GroupChat)
        
        # 模拟LLM Manager
        self.llm_manager = MagicMock()
        self.llm_manager.get_current_model = MagicMock()
        
        # 创建Agent实例
        self.agent = Agent(
            llm_manager=self.llm_manager,
            compress_threshold=800,
            group_chat=self.group_chat,
            pinned_messages=[],
        )
        
        # 模拟必要的组件
        self.current_answer_mock = MagicMock()
        self.current_answer_mock.interrupt = MagicMock()
        self.current_answer_mock.get_current_content = MagicMock(return_value="")
        self.agent.current_answer = self.current_answer_mock
        
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.handle_user_message = AsyncMock()
        
        # 设置group_chat模拟
        self.group_chat.is_empty = MagicMock()
        self.group_chat.receive = AsyncMock()
        self.group_chat.send_if_exists = AsyncMock()
        
    async def test_interrupt_batches_multiple_user_messages(self):
        """测试interrupt方法批量处理多条排队用户消息。"""
        # 模拟队列中有3条用户消息
        user_messages = [
            UserMessage(message="消息1"),
            UserMessage(message="消息2"),
            UserMessage(message="消息3"),
        ]
        
        # 设置is_empty先返回False三次，然后返回True
        self.group_chat.is_empty.side_effect = [False, False, False, True]
        
        # 设置receive依次返回三条消息
        self.group_chat.receive.side_effect = user_messages
        
        # 调用interrupt
        await self.agent.interrupt("测试打断", "UI通知")
        
        # 验证interrupt被调用
        self.current_answer_mock.interrupt.assert_called_once()
        
        # 验证add_new_message被调用（添加RuntimeMessage）
        self.agent.message_processor.add_new_message.assert_called_once()
        
        # 验证send_if_exists被调用（UI通知）
        self.group_chat.send_if_exists.assert_called_once()
        
        # 验证状态变为working
        self.assertEqual(self.agent.state, "working")
        
        # 验证is_empty被调用了4次（3次False，1次True），且参数正确
        self.assertEqual(self.group_chat.is_empty.call_count, 4)
        expected_calls = [call("user_message")] * 4
        self.group_chat.is_empty.assert_has_calls(expected_calls)
        
        # 验证receive被调用了3次
        self.assertEqual(self.group_chat.receive.call_count, 3)
        
        # 验证handle_user_message被调用了3次，每次处理一条用户消息
        self.assertEqual(self.agent.handle_user_message.call_count, 3)
        for i, msg in enumerate(user_messages):
            call_args = self.agent.handle_user_message.call_args_list[i]
            self.assertEqual(call_args[0][0], msg)
    
    async def test_interrupt_with_no_user_messages(self):
        """测试interrupt方法在没有排队用户消息时的行为。"""
        # 模拟队列为空
        self.group_chat.is_empty.return_value = True
        
        await self.agent.interrupt("测试打断", "UI通知")
        
        # 验证interrupt被调用
        self.current_answer_mock.interrupt.assert_called_once()
        
        # 验证is_empty被调用一次，参数正确
        self.group_chat.is_empty.assert_called_once_with("user_message")
        
        # 验证receive没有被调用
        self.group_chat.receive.assert_not_called()
        
        # 验证handle_user_message没有被调用
        self.agent.handle_user_message.assert_not_called()
    
    async def test_interrupt_with_tool_calls_in_content(self):
        """测试当current_content包含工具调用时的interrupt行为。"""
        # 模拟current_content包含工具调用
        self.current_answer_mock.get_current_content.return_value = "\n```json toolcall\n{}\\```\n"
        
        # 模拟队列中有消息
        self.group_chat.is_empty.side_effect = [False, True]
        self.group_chat.receive.return_value = UserMessage(message="测试消息")
        
        await self.agent.interrupt("测试打断", "UI通知")
        
        # 验证除了正常的RuntimeMessage外，还添加了额外的警告消息
        self.assertEqual(self.agent.message_processor.add_new_message.call_count, 2)
        
        # 验证批量处理逻辑仍然执行
        self.group_chat.is_empty.assert_any_call("user_message")
        self.group_chat.receive.assert_called_once()
        self.agent.handle_user_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()