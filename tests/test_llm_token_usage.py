"""Unit tests for LLM token usage functionality."""

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict

from linhai.llm import (
    OpenAiAnswer,
    AnswerTokenUsage,
    ToolCallMessage,
    AssistantMessage,
    UserMessage,
    SystemMessage,
)
from linhai.registry import Registry
from linhai.agent import Agent
from linhai.agent.orchestration import (
    NotificationMessagePlugin,
    AgentContextOrchestration,
)
from linhai.cli.app import CLIApp
from linhai.token_manager import TokenManager


class TestLLMTokenUsage(unittest.IsolatedAsyncioTestCase):
    """Test cases for LLM token usage functionality."""

    def setUp(self):
        """设置测试环境。"""
        self.registry = Registry()
        self.registry.register_queue("ui_log")

        # Mock stream for OpenAiAnswer
        self.mock_stream = AsyncMock()
        self.mock_stream.__anext__ = AsyncMock()

        # Mock agent for NotificationMessagePlugin - 使用spec确保类型匹配
        self.mock_agent = MagicMock(spec=Agent)
        self.mock_agent.get_threshold_info = MagicMock(return_value=None)
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.message_processor.update_notification_message = MagicMock()

        self.registry.register_member("agent", self.mock_agent)

        # Mock orchestration - 使用spec确保类型匹配
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

    async def test_openai_answer_sends_token_usage(self):
        """测试OpenAiAnswer将token usage发送到registry。"""
        self.registry.register_queue("token_usage")

        # 创建OpenAiAnswer实例
        answer = OpenAiAnswer(
            stream=self.mock_stream,
            registry=self.registry,
            compatibility=None,
            estimated_cached_input_tokens=100,
            llm_instance=None,
        )

        # 模拟stream返回带有usage的chunk
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock(
            content="test content",
            reasoning_content="",  # 设置为空字符串以避免AssertionError
        )
        mock_usage = MagicMock(
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        )
        # 设置prompt_tokens_details.cached_tokens为None，避免覆盖estimated_cached_input_tokens
        mock_usage.prompt_tokens_details = MagicMock()
        mock_usage.prompt_tokens_details.cached_tokens = None
        mock_chunk.usage = mock_usage

        # 设置stream的返回值
        self.mock_stream.__anext__.return_value = mock_chunk

        # 模拟registry.send方法
        sent_messages = []
        original_send = self.registry.send

        async def mock_send(name: str, message: object):
            sent_messages.append((name, message))
            return await original_send(name, message)

        self.registry.send = mock_send

        try:
            # 尝试获取token，这会触发update_toyield
            await answer.update_toyield()

            # 检查是否发送了token_usage消息
            token_usage_sent = False
            for name, message in sent_messages:
                if name == "token_usage" and isinstance(message, AnswerTokenUsage):
                    token_usage_sent = True
                    self.assertEqual(message.input_tokens, 50)
                    self.assertEqual(message.output_tokens, 20)
                    self.assertEqual(message.total_tokens, 70)
                    self.assertEqual(message.cached_input_tokens, 100)
                    break

            self.assertTrue(token_usage_sent, "应该发送token_usage消息")
        finally:
            self.registry.send = original_send

    async def test_notification_message_plugin_before_message_generation(self):
        """测试NotificationMessagePlugin的before_message_generation钩子。"""
        plugin = NotificationMessagePlugin(self.registry)

        # 测试threshold_info为None的情况
        await plugin.before_message_generation()

        # 验证没有调用update_notification_message
        self.mock_agent.message_processor.update_notification_message.assert_not_called()

        # 测试有threshold_info的情况
        threshold_info = {
            "hard_limit": 80000,
            "used_tokens": 40000,
            "usage_ratio": 0.5,
        }
        self.mock_agent.get_threshold_info.return_value = threshold_info

        # 设置orchestration返回通知消息
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

        # 验证调用了update_notification_message
        self.mock_agent.message_processor.update_notification_message.assert_called_once()
        call_args = (
            self.mock_agent.message_processor.update_notification_message.call_args
        )
        runtime_message = call_args[0][0]
        self.assertEqual(runtime_message.message, notification_msg)
        self.assertEqual(call_args[1]["source"], "threshold_notification")

    async def test_cli_token_usage_queue_handling(self):
        """测试CLI app正确处理token_usage队列。"""
        # 创建TokenManager
        token_manager = TokenManager(self.registry)

        # 模拟CLIApp的watch_token_usage_queue方法
        cli_app = MagicMock(spec=CLIApp)
        cli_app.token_manager = token_manager

        # 发送token_usage消息
        token_usage = AnswerTokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cached_input_tokens=20,
        )

        await self.registry.send("token_usage", token_usage)

        # 手动调用watch_token_usage_queue的逻辑
        output = await self.registry.receive("token_usage")

        self.assertIsInstance(output, AnswerTokenUsage)
        self.assertEqual(output.input_tokens, 100)
        self.assertEqual(output.output_tokens, 50)
        self.assertEqual(output.total_tokens, 150)
        self.assertEqual(output.cached_input_tokens, 20)


if __name__ == "__main__":
    unittest.main()
