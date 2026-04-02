"""测试 VolcanoDeepseekFixPlugin 模块。"""

import re
import unittest
from unittest.mock import MagicMock, AsyncMock
from linhai.plugin import VolcanoDeepseekFixPlugin
from linhai.agent.base import RuntimeMessage
from linhai.utils.common import UiNotice


class TestVolcanoDeepseekFixPlugin(unittest.IsolatedAsyncioTestCase):
    """测试 VolcanoDeepseekFixPlugin 类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.added_messages = []

        def capture_message(msg):
            self.added_messages.append(msg)

        self.agent.message_processor.add_new_message = AsyncMock(
            side_effect=capture_message
        )
        self.registry = MagicMock()
        self.registry.get_member_typechecked = MagicMock(return_value=self.agent)
        self.registry.send_if_exists = AsyncMock()
        self.plugin = VolcanoDeepseekFixPlugin(self.registry)
        self.answer = MagicMock()
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )

    async def test_after_message_generation_no_abnormal_marker(self):
        """测试没有异常标记时不触发警告。"""
        full_response = (
            '正常的工具调用\n```json toolcall\n{"name": "test", "arguments": {}}\n```'
        )

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(len(self.added_messages), 0)
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_with_abnormal_marker(self):
        """测试有异常标记时显示上下文内容。"""
        abnormal_marker = VolcanoDeepseekFixPlugin.ABNORMAL_MARKER
        full_response = (
            "一些正常内容\n"
            f"{abnormal_marker}\n"
            '{"name": "test", "arguments": {}}\n'
            "```\n"
            "更多内容"
        )

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(len(self.added_messages), 1)
        runtime_msg = self.added_messages[0]
        self.assertIsInstance(runtime_msg, RuntimeMessage)
        message = runtime_msg.message
        self.assertIn("警告：检测到火山平台 deepseek 的异常输出标记", message)
        self.assertIn("异常位置附近的内容:", message)
        self.assertTrue(re.search(r"\[位置\s*1\]", message))
        self.assertIn(abnormal_marker, message)

        self.registry.send_if_exists.assert_called_once()
        ui_call = self.registry.send_if_exists.call_args[0]
        self.assertIsInstance(ui_call[1], UiNotice)
        self.assertIn("已提醒 agent 并显示上下文", ui_call[1].content)

    async def test_after_message_generation_with_multiple_abnormal_markers(self):
        """测试多个异常标记时显示所有上下文。"""
        abnormal_marker = VolcanoDeepseekFixPlugin.ABNORMAL_MARKER
        full_response = (
            "内容 1\n"
            f"{abnormal_marker}\n"
            '{"name": "tool1", "arguments": {}}\n'
            "```\n"
            "中间内容\n"
            f"{abnormal_marker}\n"
            '{"name": "tool2", "arguments": {}}\n'
            "```\n"
            "内容 2"
        )

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(len(self.added_messages), 1)
        runtime_msg = self.added_messages[0]
        message = runtime_msg.message
        self.assertTrue(re.search(r"\[位置\s*1\]", message))
        self.assertTrue(re.search(r"\[位置\s*2\]", message))

        self.registry.send_if_exists.assert_called_once()
        ui_call = self.registry.send_if_exists.call_args[0]
        self.assertTrue(re.search(r"共\s*2\s*处", ui_call[1].content))

    async def test_after_message_generation_context_truncation(self):
        """测试上下文截断逻辑。"""
        abnormal_marker = VolcanoDeepseekFixPlugin.ABNORMAL_MARKER
        prefix = "a" * 150
        suffix = "b" * 150
        full_response = (
            prefix + f"{abnormal_marker}\n"
            '{"name": "test", "arguments": {}}\n'
            "```\n" + suffix
        )

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(len(self.added_messages), 1)
        runtime_msg = self.added_messages[0]
        message = runtime_msg.message
        self.assertIn("...", message)

    async def test_context_length_is_around_100(self):
        """测试上下文总长度约 100 字符。"""
        abnormal_marker = VolcanoDeepseekFixPlugin.ABNORMAL_MARKER
        self.assertEqual(VolcanoDeepseekFixPlugin.CONTEXT_CHARS, 50)

        prefix = "a" * 100
        suffix = "b" * 100
        full_response = (
            prefix + f"{abnormal_marker}\n"
            '{"name": "test", "arguments": {}}\n'
            "```\n" + suffix
        )

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(len(self.added_messages), 1)
        runtime_msg = self.added_messages[0]
        message = runtime_msg.message
        context_lines = [
            line
            for line in message.split("\n")
            if line.strip()
            and not any(
                x in line for x in ["警告", "正确", "请修正", "异常位置", "[位置"]
            )
        ]
        total_context_length = sum(len(line) for line in context_lines)
        self.assertLess(
            total_context_length,
            200,
            f"上下文总长度 {total_context_length} 超过 200 字符",
        )
        self.assertGreater(
            total_context_length,
            50,
            f"上下文总长度 {total_context_length} 少于 50 字符",
        )
