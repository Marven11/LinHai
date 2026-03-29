import unittest
from unittest.mock import AsyncMock, MagicMock

from linhai.agent import AgentLlm, Lifecycle
from linhai.llm import UserMessage, AssistantMessage
from linhai.agent.base import RuntimeMessage


class TestAgentLlm(unittest.IsolatedAsyncioTestCase):
    """Test cases for AgentLlm class."""

    def setUp(self):
        from linhai.registry import Registry
        from linhai.agent import Agent
        from linhai.llm_manager import LlmManager

        self.registry = MagicMock(spec=Registry)
        self.registry.is_empty.return_value = True

        self.mock_agent = MagicMock(spec=Agent)
        self.mock_agent.state = "waiting_user"

        self.mock_llm_manager = MagicMock(spec=LlmManager)

        self.mock_toolcall_processor = MagicMock()
        self.mock_message_processor = MagicMock()
        self.mock_message_processor.add_new_message = AsyncMock()

        self.lifecycle = MagicMock(spec=Lifecycle)
        self.mock_agent.lifecycle = self.lifecycle

        # 注册mock agent到registry，因为AgentLlm现在从registry获取agent
        self.registry.get_member_typechecked.return_value = self.mock_agent

        self.agent_llm = AgentLlm(
            llm_manager=self.mock_llm_manager,
            registry=self.registry,
            toolcall_processor=self.mock_toolcall_processor,
            message_processor=self.mock_message_processor,
        )

    async def test_init(self):
        """__init__：正确初始化所有属性。"""
        self.assertEqual(self.agent_llm.llm_manager, self.mock_llm_manager)
        self.assertEqual(self.agent_llm.registry, self.registry)
        self.assertEqual(
            self.agent_llm.toolcall_processor, self.mock_toolcall_processor
        )
        self.assertEqual(self.agent_llm.message_processor, self.mock_message_processor)
        self.assertIsNone(self.agent_llm._current_parsed_answer)
        self.assertIsNone(self.agent_llm.current_answer)

    async def test_interrupt_no_current_answer(self):
        """interrupt：无current_answer时不执行任何操作。"""
        self.agent_llm._current_parsed_answer = None

        await self.agent_llm.interrupt("agent message", "ui notice")

        self.assertIsNone(self.agent_llm._current_parsed_answer)

    async def test_interrupt_with_current_answer(self):
        """interrupt：有current_answer时正常打断。"""
        parsed_answer_mock = MagicMock()
        answer_mock = MagicMock()
        answer_mock.get_current_content.return_value = "test content"
        parsed_answer_mock._answer = answer_mock
        self.agent_llm._current_parsed_answer = parsed_answer_mock
        self.mock_agent.state = "working"

        await self.agent_llm.interrupt("agent message", "ui notice")

        parsed_answer_mock.interrupt.assert_called_once()

    async def test_interrupt_batches_user_messages(self):
        """interrupt：批量处理用户消息。"""
        parsed_answer_mock = MagicMock()
        answer_mock = MagicMock()
        answer_mock.get_current_content.return_value = "test content"
        parsed_answer_mock._answer = answer_mock
        self.agent_llm._current_parsed_answer = parsed_answer_mock

        self.registry.is_empty.side_effect = [False, True, True]

        # 模拟receive返回UserMessage
        mock_user_msg = MagicMock(spec=UserMessage)
        self.registry.receive = AsyncMock(return_value=mock_user_msg)
        self.mock_agent.handle_user_message = AsyncMock()

        await self.agent_llm.interrupt("agent message", "ui notice")

        parsed_answer_mock.interrupt.assert_called_once()

    async def test_interrupt_with_tool_calls_in_content(self):
        """interrupt：content包含工具调用时添加警告。"""
        parsed_answer_mock = MagicMock()
        answer_mock = MagicMock()
        parsed_answer_mock._answer = answer_mock
        answer_mock.get_current_content.return_value = r"""\n```json toolcall\n{}\\```
"""
        self.agent_llm._current_parsed_answer = parsed_answer_mock

        await self.agent_llm.interrupt("agent message", "ui notice")

        parsed_answer_mock.interrupt.assert_called_once()


if __name__ == "__main__":
    unittest.main()
