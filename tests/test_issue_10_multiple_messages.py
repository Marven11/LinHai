import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock

from linhai.agent.main import Agent
from linhai.agent.user_message_handler import UserMessageHandler
from linhai.registry import Registry
from linhai.llm import UserMessage
from linhai.agent.base import RuntimeMessage
from linhai.utils.common import UiNotice


class TestIssue10MultipleMessages(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.registry = MagicMock(spec=Registry)

        self.llm_manager = MagicMock()
        self.llm_manager.get_current_model = MagicMock()

        self.agent = Agent(
            llm_manager=self.llm_manager,
            compress_threshold=800,
            registry=self.registry,
            pinned_messages=[],
        )

        self.current_answer_mock = MagicMock()
        self.current_answer_mock.interrupt = MagicMock()
        self.current_answer_mock.get_current_content = MagicMock(return_value="")
        self.agent.current_answer = self.current_answer_mock

        self.agent_llm_mock = MagicMock()
        self.agent_llm_mock.interrupt = AsyncMock()
        self.agent.agent_llm = self.agent_llm_mock

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()

        self.registry.send_if_exists = AsyncMock()

    async def test_interrupt_batches_multiple_user_messages(self):
        user_messages = [
            UserMessage(message="msg1"),
            UserMessage(message="msg2"),
            UserMessage(message="msg3"),
        ]

        mock_handler = MagicMock(spec=UserMessageHandler)
        mock_handler.has_message = MagicMock(side_effect=[True, True, True, False])
        mock_handler.receive_and_dispatch = AsyncMock(return_value=True)

        call_count = 0

        async def interrupt_side_effect(agent_message, ui_notice):
            nonlocal call_count
            while mock_handler.has_message():
                call_count += 1
                if call_count > 10:
                    break
                await mock_handler.receive_and_dispatch()

        self.agent_llm_mock.interrupt.side_effect = interrupt_side_effect

        def get_member(name, cls):
            if name == "agent":
                return self.agent
            if name == "user_message_handler":
                return mock_handler
            return None

        self.registry.get_member_typechecked = MagicMock(side_effect=get_member)

        await self.agent.agent_llm.interrupt("test", "UI")

        self.assertEqual(mock_handler.receive_and_dispatch.call_count, 3)

    async def test_interrupt_with_no_user_messages(self):
        mock_handler = MagicMock(spec=UserMessageHandler)
        mock_handler.has_message = MagicMock(return_value=False)
        mock_handler.receive_and_dispatch = AsyncMock()

        def get_member(name, cls):
            if name == "agent":
                return self.agent
            if name == "user_message_handler":
                return mock_handler
            return None

        self.registry.get_member_typechecked = MagicMock(side_effect=get_member)

        async def interrupt_side_effect(agent_message, ui_notice):
            pass

        self.agent_llm_mock.interrupt.side_effect = interrupt_side_effect

        await self.agent.agent_llm.interrupt("test", "UI")

        mock_handler.receive_and_dispatch.assert_not_called()

    async def test_interrupt_with_tool_calls_in_content(self):
        self.current_answer_mock.get_current_content.return_value = (
            "\n```json toolcall\n{}\\```\n"
        )

        mock_handler = MagicMock(spec=UserMessageHandler)
        mock_handler.has_message = MagicMock(side_effect=[True, False])
        mock_handler.receive_and_dispatch = AsyncMock(return_value=True)

        def get_member(name, cls):
            if name == "agent":
                return self.agent
            if name == "user_message_handler":
                return mock_handler
            return None

        self.registry.get_member_typechecked = MagicMock(side_effect=get_member)

        async def interrupt_side_effect(agent_message, ui_notice):
            self.current_answer_mock.interrupt()
            await self.agent.message_processor.add_new_message(
                RuntimeMessage(agent_message)
            )
            if "```json toolcall" in self.current_answer_mock.get_current_content():
                await self.agent.message_processor.add_new_message(
                    RuntimeMessage("当前所有工具调用全部被忽略，请重新调用")
                )
            interrupt_msg = UiNotice(level="WARNING", content=ui_notice)
            await self.registry.send_if_exists("ui_log", interrupt_msg)
            self.agent.state = "working"
            while mock_handler.has_message():
                await mock_handler.receive_and_dispatch()

        self.agent_llm_mock.interrupt.side_effect = interrupt_side_effect

        await self.agent.agent_llm.interrupt("test", "UI")

        self.assertEqual(self.agent.message_processor.add_new_message.call_count, 2)
        mock_handler.receive_and_dispatch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
