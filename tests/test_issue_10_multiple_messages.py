"""测试issue #10: 多条用户消息只触发一次打断并批量处理。"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, call

from linhai.agent.main import Agent
from linhai.registry import Registry
from linhai.llm import UserMessage
from linhai.agent.base import RuntimeMessage
from linhai.utils.common import UiNotice


class TestIssue10MultipleMessages(unittest.IsolatedAsyncioTestCase):
    """测试多条用户消息的批量处理。"""

    async def asyncSetUp(self):
        """设置测试环境。"""
        self.registry = MagicMock(spec=Registry)

        # 模拟LLM Manager
        self.llm_manager = MagicMock()
        self.llm_manager.get_current_model = MagicMock()

        # 创建Agent实例
        self.agent = Agent(
            llm_manager=self.llm_manager,
            compress_threshold=800,
            registry=self.registry,
            pinned_messages=[],
        )

        # 模拟必要的组件
        self.current_answer_mock = MagicMock()
        self.current_answer_mock.interrupt = MagicMock()
        self.current_answer_mock.get_current_content = MagicMock(return_value="")
        self.agent.current_answer = self.current_answer_mock

        # 模拟agent_llm
        self.agent_llm_mock = MagicMock()
        self.agent_llm_mock.interrupt = AsyncMock()
        self.agent.agent_llm = self.agent_llm_mock

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.handle_user_message = AsyncMock()

        # 设置registry模拟
        self.registry.is_empty = MagicMock()
        self.registry.receive = AsyncMock()
        self.registry.send_if_exists = AsyncMock()

    async def test_interrupt_batches_multiple_user_messages(self):
        """测试interrupt方法批量处理多条排队用户消息。"""
        # 模拟队列中有3条用户消息
        user_messages = [
            UserMessage(message="消息1"),
            UserMessage(message="消息2"),
            UserMessage(message="消息3"),
        ]

        # 设置is_empty先返回False三次，然后返回True
        self.registry.is_empty.side_effect = [False, False, False, True]

        # 设置receive依次返回三条消息
        self.registry.receive.side_effect = user_messages

        # 设置agent_llm.interrupt的side_effect，模拟实际行为
        async def interrupt_side_effect(agent_message, ui_notice):
            # 模拟实际interrupt方法中对is_empty的多次调用
            call_count = 0
            while not self.registry.is_empty("user_message"):
                call_count += 1
                if call_count > 10:  # 防止无限循环
                    break
                msg = await self.registry.receive("user_message")
                assert isinstance(msg, UserMessage)
                await self.agent.handle_user_message(msg)

        self.agent_llm_mock.interrupt.side_effect = interrupt_side_effect

        # 调用interrupt
        await self.agent.agent_llm.interrupt("测试打断", "UI通知")

        # 验证agent_llm.interrupt被调用
        self.agent_llm_mock.interrupt.assert_called_once_with("测试打断", "UI通知")

        # 验证is_empty被调用了4次（3次False，1次True），且参数正确
        self.assertEqual(self.registry.is_empty.call_count, 4)
        expected_calls = [call("user_message")] * 4
        self.registry.is_empty.assert_has_calls(expected_calls)

        # 验证receive被调用了3次
        self.assertEqual(self.registry.receive.call_count, 3)

        # 验证handle_user_message被调用了3次，每次处理一条用户消息
        self.assertEqual(self.agent.handle_user_message.call_count, 3)
        for i, msg in enumerate(user_messages):
            call_args = self.agent.handle_user_message.call_args_list[i]
            self.assertEqual(call_args[0][0], msg)

    async def test_interrupt_with_no_user_messages(self):
        """测试interrupt方法在没有排队用户消息时的行为。"""
        # 模拟队列为空
        self.registry.is_empty.return_value = True

        # 设置agent_llm.interrupt的side_effect，模拟实际行为
        async def interrupt_side_effect(agent_message, ui_notice):
            # 模拟实际interrupt方法中对is_empty的调用
            self.registry.is_empty("user_message")
            # 不处理排队消息，因为is_empty返回True

        self.agent_llm_mock.interrupt.side_effect = interrupt_side_effect

        await self.agent.agent_llm.interrupt("测试打断", "UI通知")

        # 验证agent_llm.interrupt被调用
        self.agent_llm_mock.interrupt.assert_called_once_with("测试打断", "UI通知")

        # 验证is_empty被调用一次，参数正确
        self.registry.is_empty.assert_called_once_with("user_message")

        # 验证receive没有被调用
        self.registry.receive.assert_not_called()

        # 验证handle_user_message没有被调用
        self.agent.handle_user_message.assert_not_called()

    async def test_interrupt_with_tool_calls_in_content(self):
        """测试当current_content包含工具调用时的interrupt行为。"""
        # 模拟current_content包含工具调用
        self.current_answer_mock.get_current_content.return_value = (
            "\n```json toolcall\n{}\\```\n"
        )

        # 模拟队列中有消息
        self.registry.is_empty.side_effect = [False, True]
        self.registry.receive.return_value = UserMessage(message="测试消息")

        # 设置agent_llm.interrupt的side_effect
        async def interrupt_side_effect(agent_message, ui_notice):
            self.current_answer_mock.interrupt()
            await self.agent.message_processor.add_new_message(
                RuntimeMessage(agent_message)
            )
            # 模拟工具调用警告消息
            if "```json toolcall" in self.current_answer_mock.get_current_content():
                await self.agent.message_processor.add_new_message(
                    RuntimeMessage("当前所有工具调用全部被忽略，请重新调用")
                )
            interrupt_msg = UiNotice(level="WARNING", content=ui_notice)
            await self.registry.send_if_exists("ui_log", interrupt_msg)
            self.agent.state = "working"
            # 处理排队消息
            while not self.registry.is_empty("user_message"):
                msg = await self.registry.receive("user_message")
                assert isinstance(msg, UserMessage)
                await self.agent.handle_user_message(msg)

        self.agent_llm_mock.interrupt.side_effect = interrupt_side_effect

        await self.agent.agent_llm.interrupt("测试打断", "UI通知")

        # 验证agent_llm.interrupt被调用
        self.agent_llm_mock.interrupt.assert_called_once_with("测试打断", "UI通知")

        # 验证除了正常的RuntimeMessage外，还添加了额外的警告消息
        self.assertEqual(self.agent.message_processor.add_new_message.call_count, 2)

        # 验证批量处理逻辑仍然执行
        self.registry.is_empty.assert_any_call("user_message")
        self.registry.receive.assert_called_once()
        self.agent.handle_user_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
