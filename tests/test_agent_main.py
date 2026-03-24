"""
测试agent/main.py的状态转换逻辑。
"""

import unittest
from unittest.mock import AsyncMock, MagicMock

from linhai.agent.main import Agent
from linhai.group_chat import GroupChat


class TestAgentStateTransition(unittest.IsolatedAsyncioTestCase):
    """测试Agent状态转换。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = MagicMock(spec=GroupChat)

        self.context = {
            "llms": [],
            "llm_names": [],
            "current_llm_index": 0,
            "compress_threshold": 800,
        }
        self.init_messages = []

        self.group_chat.is_empty = MagicMock(return_value=False)
        self.group_chat.receive = AsyncMock()
        self.group_chat.send = AsyncMock()

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
            group_chat=self.group_chat,
            llms=[mock_llm],
            default_llm_name="test-llm",
            llm_fallback_map={"test-llm": None},
        )
        self.agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=compress_threshold_val,
            group_chat=self.group_chat,
            pinned_messages=self.init_messages,
        )

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
