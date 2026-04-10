import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from datetime import datetime, timedelta
from linhai.agent.main import Agent
from linhai.llm_manager import LlmManager
from linhai.registry import Registry


class TestAgentMain(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_registry = MagicMock(spec=Registry)
        self.mock_registry.send_if_exists = AsyncMock()
        self.mock_registry.register_member = MagicMock()

        self.mock_llm1 = MagicMock()
        self.mock_llm1.get_name = MagicMock(return_value="llm1")
        self.mock_llm1.get_token_limit = MagicMock(return_value=8000)

        self.mock_llm2 = MagicMock()
        self.mock_llm2.get_name = MagicMock(return_value="llm2")
        self.mock_llm2.get_token_limit = MagicMock(return_value=16000)

        self.llm_manager = LlmManager(
            registry=self.mock_registry,
            llms=[self.mock_llm1, self.mock_llm2],
            default_llm_name="llm1",
            llm_fallback_map={"llm1": "llm2", "llm2": None},
            llm_fallback_duration_map={"llm1": 120, "llm2": 120},
        )

        self.agent = Agent(
            llm_manager=self.llm_manager,
            compress_threshold=65536,
            registry=self.mock_registry,
            pinned_messages=[],
            max_toolcall_token_in_round=0.3,
        )

    def test_get_current_llm_info_default(self):
        name, llm = self.agent.get_current_llm_info()
        self.assertEqual(name, "llm1")
        self.assertEqual(llm, self.mock_llm1)

    def test_get_current_llm_info_without_cleanup(self):
        name, llm = self.agent.get_current_llm_info(rotate_invalid_llm=False)
        self.assertEqual(name, "llm1")
        self.assertEqual(llm, self.mock_llm1)

    def test_get_current_llm_info_after_switch(self):
        self.llm_manager.llm_stack.append(("llm2", None))
        name, llm = self.agent.get_current_llm_info()
        self.assertEqual(name, "llm2")
        self.assertEqual(llm, self.mock_llm2)


if __name__ == "__main__":
    unittest.main()
