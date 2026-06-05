"""Unit tests for LLM token usage functionality."""

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict

from linhai.base import (
    AnswerTokenUsage,
    ToolCallMessage,
    AssistantMessage,
    UserMessage,
    SystemMessage,
)
from linhai.llm import OpenAiAnswer
from linhai.registry import Registry
from linhai.agent import Agent
from linhai.agent.orchestration import (
    NotificationMessagePlugin,
    AgentContextOrchestration,
)
from linhai.tui.app import TUIApp
from linhai.token_manager import TokenManager


class TestLLMTokenUsage(unittest.IsolatedAsyncioTestCase):
    """Test cases for LLM token usage functionality."""

    def setUp(self):
        """设置测试环境。"""
        self.registry = Registry()
        self.registry.register_queue("ui_log")

        self.mock_stream = AsyncMock()
        self.mock_stream.__anext__ = AsyncMock()

        self.mock_agent = MagicMock(spec=Agent)
        self.mock_agent.get_threshold_info = MagicMock(return_value=None)
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.message_processor.update_notification_message = MagicMock()

        self.registry.register_member("agent", self.mock_agent)

        self.mock_orchestration = MagicMock(spec=AgentContextOrchestration)
        self.mock_orchestration.consecutive_red_block_count = 0
        self.mock_orchestration.compute_orchestration_context = MagicMock(
            return_value={
                "threshold_info": None,
                "current_state": "绿灯",
                "is_dirty": False,
                "notification_message": "当前Token用量为40000，硬限制为80000，当前使用50.0%（绿灯状态）。",
                "tool_block_details": {
                    "blocked_category": None,
                    "actual_category": "other",
                    "is_dirty": False,
                    "current_state": "绿灯",
                },
            }
        )
        self.registry.register_member(
            "agent_context_orchestration", self.mock_orchestration
        )

    async def test_openai_answer_get_token_usage(self):
        """测试OpenAiAnswer通过get_token_usage()返回正确的token用量。"""
        answer = OpenAiAnswer(
            stream=self.mock_stream,
            registry=self.registry,
            compatibility=None,
            estimated_cached_input_tokens=100,
            llm_instance=None,
        )

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock(
            content="test content",
            reasoning_content="",
        )
        mock_usage = MagicMock(
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        )
        mock_usage.prompt_tokens_details = MagicMock()
        mock_usage.prompt_tokens_details.cached_tokens = None
        mock_chunk.usage = mock_usage

        self.mock_stream.__anext__.return_value = mock_chunk

        await answer.update_toyield()

        usage = answer.get_token_usage()
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.input_tokens, 50)
        self.assertEqual(usage.output_tokens, 20)
        self.assertEqual(usage.total_tokens, 70)
        self.assertIsNone(usage.cached_input_tokens)
        self.assertEqual(usage.estimated_cached_input_tokens, 100)

    async def test_notification_message_plugin_before_message_generation(self):
        """测试NotificationMessagePlugin的before_message_generation钩子。"""
        plugin = NotificationMessagePlugin(self.registry)

        await plugin.before_message_generation()

        self.mock_agent.message_processor.update_notification_message.assert_not_called()

        threshold_info = {
            "hard_limit": 80000,
            "used_tokens": 40000,
            "usage_ratio": 0.5,
        }
        self.mock_agent.get_threshold_info.return_value = threshold_info

        notification_msg = (
            "当前Token用量为40000，硬限制为80000，当前使用50.0%（绿灯状态）。"
        )
        self.mock_orchestration.compute_orchestration_context.return_value = {
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

        await plugin.before_message_generation()

        self.mock_agent.message_processor.update_notification_message.assert_called_once()
        call_args = (
            self.mock_agent.message_processor.update_notification_message.call_args
        )
        runtime_message = call_args[0][0]
        self.assertEqual(runtime_message.message, notification_msg)
        self.assertEqual(call_args[1]["source"], "threshold_notification")

    async def test_token_manager_on_answer_generated(self):
        """测试TokenManager通过_on_answer_generated回调更新token用量。"""
        token_manager = TokenManager(self.registry)

        mock_parsed_answer = MagicMock()
        mock_answer = MagicMock()
        token_usage = AnswerTokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cached_input_tokens=20,
        )
        mock_answer.get_token_usage = MagicMock(return_value=token_usage)
        mock_parsed_answer._answer = mock_answer

        await token_manager._on_answer_generated(mock_parsed_answer, [])

        self.assertEqual(token_manager.current_token_usage.input_tokens, 100)
        self.assertEqual(token_manager.current_token_usage.output_tokens, 50)
        self.assertEqual(token_manager.current_token_usage.total_tokens, 150)
        self.assertEqual(token_manager.current_token_usage.cached_input_tokens, 20)
        self.assertIsNotNone(token_manager.cumulative_token_usage)
        assert token_manager.cumulative_token_usage is not None
        self.assertEqual(token_manager.cumulative_token_usage["input_tokens"], 100)


if __name__ == "__main__":
    unittest.main()
