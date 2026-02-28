import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.plugin.message_checkers import VolcanoDeepseekFixPlugin
from linhai.agent import Agent
from linhai.llm import OpenAi, Answer


class TestVolcanoDeepseekFixPlugin(unittest.IsolatedAsyncioTestCase):
    """火山平台deepseek异常输出插件测试。"""

    def setUp(self) -> None:
        self.group_chat = MagicMock()
        self.plugin = VolcanoDeepseekFixPlugin(self.group_chat)

        self.agent = MagicMock(spec=Agent)
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.group_chat.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )

        self.model = MagicMock(spec=OpenAi)
        self.model.base_url = "https://ark.cn-beijing.volces.com/api/v3"
        self.model.model = "deepseek-chat"
        self.agent.get_current_model.return_value = self.model

        self.group_chat.send_if_exists = AsyncMock()

    async def test_is_volcano_deepseek_detection(self) -> None:
        """测试火山平台deepseek检测逻辑。"""
        full_response = '思考中...\n</think>```json toolcall\n{"name": "test", "arguments": {}}\n```'

        tool_calls = []
        await self.plugin.after_message_generation(
            MagicMock(spec=Answer), full_response, tool_calls
        )

        self.group_chat.send_if_exists.assert_called_once()
        self.agent.message_processor.add_new_message.assert_called_once()

        self.assertEqual(len(tool_calls), 0)

    async def test_clean_abnormal_marker(self) -> None:
        """测试提醒异常标记。"""
        full_response = '思考中...\n</think>```json toolcall\n{"name": "test", "arguments": {}}\n```'

        tool_calls = []
        await self.plugin.after_message_generation(
            MagicMock(spec=Answer), full_response, tool_calls
        )

        self.group_chat.send_if_exists.assert_called_once()
        self.agent.message_processor.add_new_message.assert_called_once()

        self.assertEqual(len(tool_calls), 0)

    async def test_multiple_abnormal_markers(self) -> None:
        """测试多个异常标记的提醒。"""
        full_response = '思考中...\n</think>```json toolcall\n{"name": "test1", "arguments": {}}\n```\n继续思考...\n</think>```json toolcall\n{"name": "test2", "arguments": {}}\n```'

        tool_calls = []
        await self.plugin.after_message_generation(
            MagicMock(spec=Answer), full_response, tool_calls
        )

        self.group_chat.send_if_exists.assert_called_once()
        self.agent.message_processor.add_new_message.assert_called_once()

        self.assertEqual(len(tool_calls), 0)

    async def test_no_abnormal_marker(self) -> None:
        """测试没有异常标记时插件不干预。"""
        full_response = (
            '思考中...\n```json toolcall\n{"name": "test", "arguments": {}}\n```'
        )

        tool_calls = []
        await self.plugin.after_message_generation(
            MagicMock(spec=Answer), full_response, tool_calls
        )

        self.group_chat.send_if_exists.assert_not_called()

        self.assertEqual(len(tool_calls), 0)

    async def test_interrupt_on_parse_failure(self) -> None:
        """测试插件不再中断agent，而是发送警告消息。"""
        full_response = "思考中...\n</think>```json toolcall\ninvalid json\n```"

        tool_calls = []
        self.agent.interrupt = AsyncMock()
        await self.plugin.after_message_generation(
            MagicMock(spec=Answer), full_response, tool_calls
        )

        self.agent.interrupt.assert_not_called()
        self.agent.message_processor.add_new_message.assert_called_once()
        self.assertEqual(len(tool_calls), 0)

    def test_plugin_registration(self) -> None:
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()
