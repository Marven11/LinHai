"""Unit tests for token usage integration functionality."""

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any

from linhai.agent import Agent
from linhai.agent.orchestration import AgentContextOrchestration


class TestTokenUsageIntegration(unittest.IsolatedAsyncioTestCase):
    """Test cases for token usage integration."""

    async def test_token_manager_on_answer_generated(self):
        """测试TokenManager通过_on_answer_generated集成更新token用量。"""
        from linhai.registry import Registry
        from linhai.base import AnswerTokenUsage
        from linhai.token_manager import TokenManager

        registry = Registry()
        token_manager = TokenManager(registry)

        mock_parsed_answer = MagicMock()
        mock_answer = MagicMock()
        token_usage = AnswerTokenUsage(
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
            cached_input_tokens=100,
        )
        mock_answer.get_token_usage = MagicMock(return_value=token_usage)
        mock_parsed_answer._answer = mock_answer

        await token_manager._on_answer_generated(mock_parsed_answer)

        self.assertEqual(token_manager._current_token_usage.input_tokens, 50)
        self.assertEqual(token_manager._current_token_usage.output_tokens, 20)
        self.assertEqual(token_manager._current_token_usage.total_tokens, 70)
        self.assertEqual(token_manager._current_token_usage.cached_input_tokens, 100)

        await token_manager.finalize_round(mock_parsed_answer, [])
        token_info = token_manager.get_token_info()
        self.assertFalse(token_info.is_dirty)
        assert token_info.last_valid_token_usage is not None
        self.assertEqual(token_info.last_valid_token_usage.input_tokens, 50)

    async def test_notification_message_plugin_integration(self):
        """测试NotificationMessagePlugin的基本集成。"""
        from linhai.registry import Registry
        from linhai.agent.messages import RuntimeMessage

        registry = Registry()

        mock_agent = MagicMock(spec=Agent)
        threshold_info = {
            "hard_limit": 80000,
            "used_tokens": 40000,
            "usage_ratio": 0.5,
        }
        mock_agent.get_threshold_info = MagicMock(return_value=threshold_info)
        mock_agent.message_processor = MagicMock()
        mock_agent.message_processor.update_notification_message = MagicMock()

        registry.register_member("agent", mock_agent)

        mock_orchestration = MagicMock(spec=AgentContextOrchestration)
        mock_orchestration.consecutive_red_block_count = 0
        notification_msg = (
            "当前Token用量为40000，硬限制为80000，当前使用50.0%（绿灯状态）。"
        )
        mock_orchestration.compute_orchestration_context = MagicMock(
            return_value={
                "threshold_info": threshold_info,
                "current_state": "绿灯",
                "is_dirty": False,
                "notification_message": notification_msg,
                "tool_block_details": {
                    "blocked_category": None,
                    "actual_category": "other",
                    "is_dirty": False,
                    "current_state": "绿灯",
                },
            }
        )
        registry.register_member("agent_context_orchestration", mock_orchestration)

        from linhai.agent.orchestration import NotificationMessagePlugin

        plugin = NotificationMessagePlugin(registry)

        await plugin.before_message_generation()

        mock_agent.get_threshold_info.assert_called_once()
        mock_orchestration.compute_orchestration_context.assert_called_once_with(
            "", threshold_info
        )
        mock_agent.message_processor.update_notification_message.assert_called_once()

        call_args = mock_agent.message_processor.update_notification_message.call_args
        runtime_message = call_args[0][0]
        self.assertIsInstance(runtime_message, RuntimeMessage)
        self.assertEqual(runtime_message.message, notification_msg)
        self.assertEqual(call_args[1]["source"], "threshold_notification")

    async def test_token_manager_cumulative_usage(self):
        """测试TokenManager累计用量通过多次_on_answer_generated更新。"""
        from linhai.registry import Registry
        from linhai.base import AnswerTokenUsage
        from linhai.token_manager import TokenManager

        registry = Registry()
        token_manager = TokenManager(registry)

        usage1 = AnswerTokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cached_input_tokens=25,
        )
        mock_answer1 = MagicMock()
        mock_answer1.get_token_usage = MagicMock(return_value=usage1)
        mock_parsed1 = MagicMock()
        mock_parsed1._answer = mock_answer1
        await token_manager._on_answer_generated(mock_parsed1)
        await token_manager.finalize_round(mock_parsed1, [])

        usage2 = AnswerTokenUsage(
            input_tokens=200,
            output_tokens=80,
            total_tokens=280,
            cached_input_tokens=30,
        )
        mock_answer2 = MagicMock()
        mock_answer2.get_token_usage = MagicMock(return_value=usage2)
        mock_parsed2 = MagicMock()
        mock_parsed2._answer = mock_answer2
        await token_manager._on_answer_generated(mock_parsed2)
        await token_manager.finalize_round(mock_parsed2, [])

        self.assertIsNotNone(token_manager.cumulative_token_usage)
        assert token_manager.cumulative_token_usage is not None
        self.assertEqual(token_manager.cumulative_token_usage["input_tokens"], 300)
        self.assertEqual(token_manager.cumulative_token_usage["output_tokens"], 130)
        self.assertEqual(token_manager.cumulative_token_usage["total_tokens"], 430)
        self.assertEqual(
            token_manager.cumulative_token_usage["cached_input_tokens"], 55
        )
        self.assertEqual(token_manager.cumulative_token_usage["message_count"], 2)


if __name__ == "__main__":
    unittest.main()
