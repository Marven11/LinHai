"""火山平台deepseek异常输出插件测试。"""

import re
import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.plugin.message_checkers import VolcanoDeepseekFixPlugin
from linhai.agent import Agent
from linhai.agent.messages import RuntimeMessage
from linhai.base import Answer
from linhai.llm import OpenAi
from linhai.utils.common import UiNotice


class TestVolcanoDeepseekFixPlugin(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.registry = MagicMock()
        self.registry.send_if_exists = AsyncMock()
        self.plugin = VolcanoDeepseekFixPlugin(self.registry)

        self.agent = MagicMock(spec=Agent)
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )

        self.model = MagicMock(spec=OpenAi)
        self.model.base_url = "https://ark.cn-beijing.volces.com/api/v3"
        self.model.model = "deepseek-chat"
        self.agent.get_current_model.return_value = self.model

    async def test_no_abnormal_marker(self) -> None:
        full_response = (
            '思考中...\n```json toolcall\n{"name": "test", "arguments": {}}\n```'
        )
        parsed_answer = MagicMock(spec=Answer)
        parsed_answer.get_message.return_value.get_content.return_value = full_response
        await self.plugin.after_message_generation(parsed_answer, [])
        self.registry.send_if_exists.assert_not_called()

    async def test_single_abnormal_marker(self) -> None:
        abnormal_marker = VolcanoDeepseekFixPlugin.ABNORMAL_MARKER
        full_response = (
            "一些正常内容\n"
            f"{abnormal_marker}\n"
            '{"name": "test", "arguments": {}}\n'
            "```"
        )
        parsed_answer = MagicMock(spec=Answer)
        parsed_answer.get_message.return_value.get_content.return_value = full_response
        await self.plugin.after_message_generation(parsed_answer, [])

        self.agent.message_processor.add_new_message.assert_called_once()
        self.registry.send_if_exists.assert_called_once()

        ui_call = self.registry.send_if_exists.call_args[0]
        self.assertIsInstance(ui_call[1], UiNotice)
        self.assertIn("已提醒 agent 并显示上下文", ui_call[1].content)

    async def test_multiple_abnormal_markers(self) -> None:
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
        parsed_answer = MagicMock(spec=Answer)
        parsed_answer.get_message.return_value.get_content.return_value = full_response
        await self.plugin.after_message_generation(parsed_answer, [])

        self.agent.message_processor.add_new_message.assert_called_once()
        self.registry.send_if_exists.assert_called_once()

        ui_call = self.registry.send_if_exists.call_args[0]
        self.assertTrue(re.search(r"共\s*2\s*处", ui_call[1].content))

        call_args = self.agent.message_processor.add_new_message.call_args
        runtime_msg = call_args[0][0]
        self.assertIsInstance(runtime_msg, RuntimeMessage)
        message = runtime_msg.message
        self.assertTrue(re.search(r"\[位置\s*1\]", message))
        self.assertTrue(re.search(r"\[位置\s*2\]", message))

    async def test_context_truncation(self) -> None:
        abnormal_marker = VolcanoDeepseekFixPlugin.ABNORMAL_MARKER
        prefix = "a" * 150
        suffix = "b" * 150
        full_response = (
            prefix + f"{abnormal_marker}\n"
            '{"name": "test", "arguments": {}}\n'
            "```\n" + suffix
        )
        parsed_answer = MagicMock(spec=Answer)
        parsed_answer.get_message.return_value.get_content.return_value = full_response
        await self.plugin.after_message_generation(parsed_answer, [])

        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args
        runtime_msg = call_args[0][0]
        self.assertIn("...", runtime_msg.message)

    async def test_context_length_around_100(self) -> None:
        abnormal_marker = VolcanoDeepseekFixPlugin.ABNORMAL_MARKER
        self.assertEqual(VolcanoDeepseekFixPlugin.CONTEXT_CHARS, 50)

        prefix = "a" * 100
        suffix = "b" * 100
        full_response = (
            prefix + f"{abnormal_marker}\n"
            '{"name": "test", "arguments": {}}\n'
            "```\n" + suffix
        )
        parsed_answer = MagicMock(spec=Answer)
        parsed_answer.get_message.return_value.get_content.return_value = full_response
        await self.plugin.after_message_generation(parsed_answer, [])

        call_args = self.agent.message_processor.add_new_message.call_args
        runtime_msg = call_args[0][0]
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
        self.assertLess(total_context_length, 200)
        self.assertGreater(total_context_length, 50)

    def test_plugin_registration(self) -> None:
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.after_message_generation.register.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()
