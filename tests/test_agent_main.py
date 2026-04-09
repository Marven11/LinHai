"""
测试agent/main.py的状态转换逻辑。
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.agent.main import Agent
from linhai.registry import Registry
from linhai.parsed_message import ParsedAnswer
from linhai.llm_manager import LlmManager


class TestAgentStateTransition(unittest.IsolatedAsyncioTestCase):
    """测试Agent状态转换。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = MagicMock(spec=Registry)

        self.context = {
            "llms": [],
            "llm_names": [],
            "current_llm_index": 0,
            "compress_threshold": 800,
        }
        self.init_messages = []

        self.registry.is_empty = MagicMock(return_value=False)
        self.registry.receive = AsyncMock()
        self.registry.send = AsyncMock()

        # 需要为Agent提供正确的参数
        # 由于这是单元测试，我们mock了context，但需要确保它有正确的结构
        # 将llms和llm_names合并为llms_with_names
        llms_list = self.context["llms"] if hasattr(self.context, "__getitem__") else []
        llm_names_list = (
            self.context["llm_names"] if hasattr(self.context, "__getitem__") else []
        )
        llms_with_names = list(zip(llms_list, llm_names_list))

        compress_threshold_val = (
            self.context["compress_threshold"]
            if hasattr(self.context, "__getitem__")
            else 800
        )
        current_llm_index = (
            self.context["current_llm_index"]
            if hasattr(self.context, "__getitem__")
            else 0
        )
        llm_name_val = llm_names_list[current_llm_index] if llm_names_list else None

        from linhai.llm_manager import LlmManager

        # 创建模拟的LLM用于LlmManager
        mock_llm = MagicMock()
        mock_llm.get_name = MagicMock(return_value="test-llm")
        llm_manager = LlmManager(
            registry=self.registry,
            llms=[mock_llm],
            default_llm_name="test-llm",
            llm_fallback_map={"test-llm": None},
            llm_fallback_duration_map={"test-llm": 120},
        )
        self.agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=compress_threshold_val,
            registry=self.registry,
            pinned_messages=self.init_messages,
        )

    async def test_state_waiting_user_transitions_to_working(self):
        """测试在等待用户状态下接收到消息后直接转为working状态。"""
        self.agent.is_last_message_user = MagicMock(return_value=False)

        self.agent.generate_response = AsyncMock()

        self.assertEqual(self.agent.state_machine.state, "waiting_user")

        self.agent.state_machine.transition_to_working()

        self.assertEqual(self.agent.state_machine.state, "working")

    async def test_state_waiting_user_with_existing_user_message(self):
        """测试在等待用户状态下已经有用户消息时不改变状态。"""
        self.agent.is_last_message_user = MagicMock(return_value=True)

        self.agent.generate_response = AsyncMock()

        self.agent.state_machine.transition_to_waiting_user()

        self.agent.state_machine.transition_to_working()

        self.assertEqual(self.agent.state_machine.state, "working")

    async def test_generate_response_returns_parsed_answer(self):
        """测试generate_response函数返回ParsedAnswer类型。"""
        # 创建模拟的ParsedAnswer对象
        mock_parsed_answer = MagicMock(spec=ParsedAnswer)
        mock_answer = MagicMock()

        from linhai.llm import AssistantMessage

        mock_assistant_message = MagicMock(spec=AssistantMessage)
        mock_assistant_message.message = "test message"
        mock_answer.get_message.return_value = mock_assistant_message

        # 设置agent_llm.call_and_wait_llm返回模拟值
        self.agent.agent_llm = MagicMock()
        self.agent.agent_llm.call_and_wait_llm = AsyncMock(
            return_value=(mock_answer, mock_parsed_answer, True)
        )

        # mock lifecycle
        mock_lifecycle = MagicMock()
        mock_lifecycle.before_add_new_message.trigger = AsyncMock()
        mock_lifecycle.after_message_generation.trigger = AsyncMock()
        self.agent.lifecycle = mock_lifecycle

        # mock message_processor以避免实际方法调用
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.message_processor.get_message_count = MagicMock(return_value=0)
        self.agent.message_processor.process_queued_messages = AsyncMock()
        self.agent.message_processor.lifecycle = mock_lifecycle

        # 调用generate_response
        result = await self.agent.generate_response()

        # 验证返回的是ParsedAnswer类型
        self.assertIsInstance(result, ParsedAnswer)
        self.assertEqual(result, mock_parsed_answer)

        # 验证call_and_wait_llm被调用
        self.agent.agent_llm.call_and_wait_llm.assert_called_once()


class TestGetThresholdInfo(unittest.TestCase):
    """测试Agent.get_threshold_info的compress_threshold优先级。"""

    def _create_agent(self, compress_threshold, llm_compress_threshold=None):
        registry = MagicMock(spec=Registry)
        registry.is_empty = MagicMock(return_value=False)
        registry.receive = AsyncMock()
        registry.send = AsyncMock()

        mock_llm = MagicMock()
        mock_llm.get_name = MagicMock(return_value="test-llm")
        mock_llm.get_token_limit = MagicMock(return_value=100000)
        mock_llm.get_compress_threshold = MagicMock(return_value=llm_compress_threshold)

        llm_manager = LlmManager(
            registry=registry,
            llms=[mock_llm],
            default_llm_name="test-llm",
            llm_fallback_map={"test-llm": None},
            llm_fallback_duration_map={"test-llm": 120},
        )
        agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=compress_threshold,
            registry=registry,
            pinned_messages=[],
        )
        return agent, registry, mock_llm

    def test_threshold_info_uses_agent_level_when_llm_none(self):
        """当LLM级别compress_threshold为None时使用agent级别。"""
        agent, registry, _ = self._create_agent(0.8, llm_compress_threshold=None)
        from linhai.token_manager import TokenManager
        from linhai.llm import AnswerTokenUsage

        mock_tm = MagicMock(spec=TokenManager)
        mock_tm.current_token_usage = AnswerTokenUsage(
            input_tokens=50000, output_tokens=1000, total_tokens=51000
        )
        registry.get_member_typechecked = MagicMock(return_value=mock_tm)

        result = agent.get_threshold_info()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["hard_limit"], 80000)

    def test_threshold_info_prefers_llm_level_float(self):
        """当LLM级别设置了float compress_threshold时优先使用。"""
        agent, registry, _ = self._create_agent(0.8, llm_compress_threshold=0.5)
        from linhai.token_manager import TokenManager
        from linhai.llm import AnswerTokenUsage

        mock_tm = MagicMock(spec=TokenManager)
        mock_tm.current_token_usage = AnswerTokenUsage(
            input_tokens=50000, output_tokens=1000, total_tokens=51000
        )
        registry.get_member_typechecked = MagicMock(return_value=mock_tm)

        result = agent.get_threshold_info()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["hard_limit"], 50000)

    def test_threshold_info_prefers_llm_level_int(self):
        """当LLM级别设置了int compress_threshold时直接使用。"""
        agent, registry, _ = self._create_agent(0.8, llm_compress_threshold=60000)
        from linhai.token_manager import TokenManager
        from linhai.llm import AnswerTokenUsage

        mock_tm = MagicMock(spec=TokenManager)
        mock_tm.current_token_usage = AnswerTokenUsage(
            input_tokens=50000, output_tokens=1000, total_tokens=51000
        )
        registry.get_member_typechecked = MagicMock(return_value=mock_tm)

        result = agent.get_threshold_info()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["hard_limit"], 60000)

    def test_threshold_info_returns_none_when_no_usage(self):
        """当没有token使用数据时返回None。"""
        agent, registry, _ = self._create_agent(0.8)
        from linhai.token_manager import TokenManager

        mock_tm = MagicMock(spec=TokenManager)
        mock_tm.current_token_usage = None
        registry.get_member_typechecked = MagicMock(return_value=mock_tm)

        result = agent.get_threshold_info()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
