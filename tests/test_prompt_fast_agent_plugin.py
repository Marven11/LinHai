"""测试PromptFastAgentPlugin的功能。"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.plugin.tool_call_managers import PromptFastAgentPlugin
from linhai.registry import Registry
from linhai.base import Answer
from linhai.llm import OpenAi


class TestPromptFastAgentPlugin(unittest.TestCase):
    """测试PromptFastAgentPlugin。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = MagicMock(spec=Registry)
        self.max_toolcall_for_llm = {"test-llm": 3, "another-llm": 5}
        self.plugin = PromptFastAgentPlugin(self.registry, self.max_toolcall_for_llm)

    def test_init(self):
        """测试插件初始化。"""
        self.assertEqual(self.plugin.max_toolcall_for_llm, self.max_toolcall_for_llm)
        self.assertEqual(self.plugin.speeding_counter, 0)

    def test_get_max_toolcall_for_current_model_with_configured_llm(self):
        """测试获取已配置LLM的最大工具调用数量。"""
        agent = MagicMock()
        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "test-llm"
        agent.get_current_model.return_value = model

        result = self.plugin._get_max_toolcall_for_current_model(agent)

        self.assertEqual(result, 3)

    def test_get_max_toolcall_for_current_model_with_unconfigured_llm(self):
        """测试获取未配置LLM的最大工具调用数量。"""
        agent = MagicMock()
        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "unconfigured-llm"
        agent.get_current_model.return_value = model

        result = self.plugin._get_max_toolcall_for_current_model(agent)

        self.assertIsNone(result)

    def test_before_message_generation_with_configured_llm(self):
        """测试已配置LLM的before_message_generation。"""
        agent = MagicMock()
        agent.get_current_model = MagicMock()
        agent.message_processor.update_notification_message = MagicMock()

        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "test-llm"
        agent.get_current_model.return_value = model

        self.registry.get_member_typechecked = MagicMock(return_value=agent)
        self.registry.send_if_exists = AsyncMock()

        # 测试第一次生成消息
        asyncio.run(self.plugin.before_message_generation())

        # 应该设置notification消息
        agent.message_processor.update_notification_message.assert_called_once()
        # 注意：插件没有发送UI日志，所以send_if_exists不应该被调用
        self.registry.send_if_exists.assert_not_called()

        # 重置mock，测试非第一次生成消息
        agent.message_processor.update_notification_message.reset_mock()
        self.registry.send_if_exists.reset_mock()

        # 测试非第一次生成消息
        asyncio.run(self.plugin.before_message_generation())

        # 应该设置notification消息但不发送UI日志
        agent.message_processor.update_notification_message.assert_called_once()
        self.registry.send_if_exists.assert_not_called()

    def test_before_message_generation_with_unconfigured_llm(self):
        """测试未配置LLM的before_message_generation。"""
        agent = MagicMock()
        agent.get_current_model = MagicMock()
        agent.message_processor.update_notification_message = MagicMock()

        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "unconfigured-llm"
        agent.get_current_model.return_value = model

        self.registry.get_member_typechecked = MagicMock(return_value=agent)
        self.registry.send_if_exists = AsyncMock()

        # 测试未配置LLM的情况
        asyncio.run(self.plugin.before_message_generation())

        # 应该清理notification消息（传入None）
        agent.message_processor.update_notification_message.assert_called_once_with(
            None, source="prompt_fast_agent"
        )
        self.registry.send_if_exists.assert_not_called()

    def test_after_token_generation_exceeds_limit(self):
        """测试工具调用数量超过限制。"""
        agent = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()
        self.registry.send_if_exists = AsyncMock()

        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "test-llm"
        agent.get_current_model.return_value = model

        answer = MagicMock(spec=Answer)

        # 模拟4个工具调用（超过限制3）
        current_content = "\n```json toolcall\n{}```\n" * 4

        result = asyncio.run(
            self.plugin.after_token_generation(agent, answer, current_content)
        )

        self.assertFalse(result)
        answer.truncate.assert_called_once()
        agent.message_processor.add_new_message.assert_called_once()
        self.assertEqual(self.plugin.speeding_counter, 1)

    def test_after_token_generation_within_limit(self):
        """测试工具调用数量在限制内。"""
        agent = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()
        self.registry.send_if_exists = AsyncMock()

        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "test-llm"
        agent.get_current_model.return_value = model

        answer = MagicMock(spec=Answer)

        # 模拟2个工具调用（在限制3内）
        current_content = "\n```json toolcall\n{}```\n" * 2

        result = asyncio.run(
            self.plugin.after_token_generation(agent, answer, current_content)
        )

        self.assertFalse(result)
        answer.truncate.assert_not_called()
        agent.message_processor.add_new_message.assert_not_called()
        self.assertEqual(self.plugin.speeding_counter, 0)

    def test_after_token_generation_unconfigured_llm(self):
        """测试未配置LLM的after_token_generation。"""
        agent = MagicMock()
        answer = MagicMock(spec=Answer)

        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "unconfigured-llm"
        agent.get_current_model.return_value = model

        current_content = "\n```json toolcall\n{}```\n" * 100

        result = asyncio.run(
            self.plugin.after_token_generation(agent, answer, current_content)
        )

        self.assertFalse(result)
        answer.truncate.assert_not_called()


class TestPromptFastAgentPluginIntegration(unittest.TestCase):
    """测试PromptFastAgentPlugin的集成场景。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = MagicMock(spec=Registry)

    def test_switch_llm_with_different_limits(self):
        """测试切换LLM时的不同限制。"""
        max_toolcall_for_llm = {"llm-a": 3, "llm-b": 5}
        plugin = PromptFastAgentPlugin(self.registry, max_toolcall_for_llm)

        # 测试llm-a限制为3
        agent = MagicMock()
        model_a = MagicMock(spec=OpenAi)
        model_a.get_name.return_value = "llm-a"
        agent.get_current_model.return_value = model_a

        max_toolcall = plugin._get_max_toolcall_for_current_model(agent)
        self.assertEqual(max_toolcall, 3)

        # 测试llm-b限制为5
        model_b = MagicMock(spec=OpenAi)
        model_b.get_name.return_value = "llm-b"
        agent.get_current_model.return_value = model_b

        max_toolcall = plugin._get_max_toolcall_for_current_model(agent)
        self.assertEqual(max_toolcall, 5)

        # 测试未配置的llm-c
        model_c = MagicMock(spec=OpenAi)
        model_c.get_name.return_value = "llm-c"
        agent.get_current_model.return_value = model_c

        max_toolcall = plugin._get_max_toolcall_for_current_model(agent)
        self.assertIsNone(max_toolcall)


if __name__ == "__main__":
    unittest.main()
