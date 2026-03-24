"""Unit tests for token usage integration functionality."""

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any

from linhai.agent import Agent
from linhai.agent.orchestration import AgentContextOrchestration


class TestTokenUsageIntegration(unittest.IsolatedAsyncioTestCase):
    """Test cases for token usage integration."""

    async def test_openai_answer_sends_token_usage(self):
        """测试OpenAiAnswer将token usage发送到group_chat。"""
        # 避免循环导入，使用mock
        from linhai.group_chat import GroupChat
        from linhai.llm import AnswerTokenUsage

        # 模拟OpenAiAnswer的核心逻辑
        group_chat = GroupChat()
        group_chat.register_queue("token_usage")

        # 记录发送的消息
        sent_messages = []
        original_send = group_chat.send

        async def mock_send(name: str, message: Any):
            sent_messages.append((name, message))
            return await original_send(name, message)

        group_chat.send = mock_send

        try:
            # 手动创建AnswerTokenUsage并发送
            token_usage = AnswerTokenUsage(
                input_tokens=50,
                output_tokens=20,
                total_tokens=70,
                cached_input_tokens=100,
            )

            await group_chat.send("token_usage", token_usage)

            # 验证发送了消息
            self.assertEqual(len(sent_messages), 1)
            self.assertEqual(sent_messages[0][0], "token_usage")
            self.assertIsInstance(sent_messages[0][1], AnswerTokenUsage)

            sent_usage = sent_messages[0][1]
            self.assertEqual(sent_usage.input_tokens, 50)
            self.assertEqual(sent_usage.output_tokens, 20)
            self.assertEqual(sent_usage.total_tokens, 70)
            self.assertEqual(sent_usage.cached_input_tokens, 100)
        finally:
            group_chat.send = original_send

    async def test_notification_message_plugin_integration(self):
        """测试NotificationMessagePlugin的基本集成。"""
        # 使用mock避免复杂导入
        from linhai.group_chat import GroupChat
        from linhai.agent.base import RuntimeMessage

        group_chat = GroupChat()

        # Mock agent - 使用spec确保类型匹配
        mock_agent = MagicMock(spec=Agent)
        threshold_info = {
            "hard_limit": 80000,
            "used_tokens": 40000,
            "usage_ratio": 0.5,
        }
        mock_agent.get_threshold_info = MagicMock(return_value=threshold_info)
        mock_agent.message_processor = MagicMock()
        mock_agent.message_processor.update_notification_message = MagicMock()

        group_chat.register_member("agent", mock_agent)

        # Mock orchestration - 使用spec确保类型匹配
        mock_orchestration = MagicMock(spec=AgentContextOrchestration)
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
        group_chat.register_member("agent_context_orchestration", mock_orchestration)

        # 导入并测试NotificationMessagePlugin
        from linhai.agent.orchestration import NotificationMessagePlugin

        plugin = NotificationMessagePlugin(group_chat)

        # 测试before_message_generation
        await plugin.before_message_generation()

        # 验证调用
        mock_agent.get_threshold_info.assert_called_once()
        mock_orchestration.compute_orchestration_context.assert_called_once_with(
            "", threshold_info
        )
        mock_agent.message_processor.update_notification_message.assert_called_once()

        # 验证参数
        call_args = mock_agent.message_processor.update_notification_message.call_args
        runtime_message = call_args[0][0]
        self.assertIsInstance(runtime_message, RuntimeMessage)
        self.assertEqual(runtime_message.message, notification_msg)
        self.assertEqual(call_args[1]["source"], "threshold_notification")

    async def test_cli_token_usage_receiving(self):
        """测试CLI接收token usage的基本逻辑。"""
        from linhai.group_chat import GroupChat
        from linhai.llm import AnswerTokenUsage

        group_chat = GroupChat()
        group_chat.register_queue("token_usage")

        # 发送token usage
        token_usage = AnswerTokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cached_input_tokens=25,
        )

        await group_chat.send("token_usage", token_usage)

        # 接收并验证
        received = await group_chat.receive("token_usage")

        self.assertIsInstance(received, AnswerTokenUsage)
        self.assertEqual(received.input_tokens, 100)
        self.assertEqual(received.output_tokens, 50)
        self.assertEqual(received.total_tokens, 150)
        self.assertEqual(received.cached_input_tokens, 25)


if __name__ == "__main__":
    unittest.main()
