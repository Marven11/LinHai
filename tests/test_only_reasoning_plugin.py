import unittest
from unittest.mock import MagicMock, AsyncMock
import asyncio

from linhai.agent.plugin import OnlyReasoningPlugin
from linhai.group_chat import GroupChat
from linhai.llm import Answer, OpenAi
from linhai.agent.base import RuntimeMessage
from linhai.utils import CliRuntimeNotice


class TestOnlyReasoningPlugin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.group_chat = MagicMock(spec=GroupChat)
        self.plugin = OnlyReasoningPlugin(self.group_chat)

        self.mock_agent = MagicMock()
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.message_processor.add_new_message = MagicMock()
        self.mock_agent.message_processor.update_appending_message = MagicMock()
        self.mock_agent.get_current_model = AsyncMock()

        self.group_chat.get_members = MagicMock(return_value=self.mock_agent)

        self.group_chat.send_if_exists = AsyncMock()

    def test_plugin_initialization(self):
        """测试插件初始化。"""
        self.assertIsInstance(self.plugin, OnlyReasoningPlugin)
        self.assertEqual(self.plugin.group_chat, self.group_chat)

    async def test_after_message_generation_with_only_reasoning_deepseek(self):
        """测试deepseek模型只有推理内容没有实际输出时发出警告。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"

        result = await self.plugin.after_message_generation(answer, "", [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.update_appending_message.assert_called_once()
        self.group_chat.send_if_exists.assert_called_once()

        call_args = self.mock_agent.message_processor.update_appending_message.call_args
        warning_message = call_args[0][0]
        self.assertIsInstance(warning_message, RuntimeMessage)
        self.assertIn("不要只思考，不输出", warning_message.message)

        ui_call_args = self.group_chat.send_if_exists.call_args
        self.assertEqual(ui_call_args[0][0], "ui_log")
        self.assertIsInstance(ui_call_args[0][1], CliRuntimeNotice)
        self.assertEqual(ui_call_args[0][1].level, "WARNING")
        self.assertIn("只思考不输出", ui_call_args[0][1].content)

    async def test_after_message_generation_with_reasoning_and_content_deepseek(self):
        """测试deepseek模型既有推理内容又有实际输出时不发出警告。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"

        result = await self.plugin.after_message_generation(answer, "这是实际输出", [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    async def test_after_message_generation_without_reasoning_deepseek(self):
        """测试deepseek模型没有推理内容时不发出警告。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = None

        result = await self.plugin.after_message_generation(answer, "", [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    async def test_after_message_generation_with_content_only_deepseek(self):
        """测试deepseek模型只有实际输出没有推理内容时不发出警告。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = None

        result = await self.plugin.after_message_generation(answer, "这是实际输出", [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    async def test_after_message_generation_with_whitespace_content_deepseek(self):
        """测试deepseek模型推理内容有但实际输出只有空白字符时发出警告。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"

        result = await self.plugin.after_message_generation(answer, "   \n\t  ", [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.update_appending_message.assert_called_once()
        self.group_chat.send_if_exists.assert_called_once()

    async def test_after_message_generation_non_deepseek_model(self):
        """测试非deepseek模型时不检查只思考不输出。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "minimax"
        self.mock_agent.get_current_model.return_value = mock_model

        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"

        result = await self.plugin.after_message_generation(answer, "", [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_not_called()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    async def test_after_message_generation_non_openai_model(self):
        """测试非OpenAi模型时不检查只思考不输出。"""
        mock_model = MagicMock()  # 不是OpenAi实例
        self.mock_agent.get_current_model.return_value = mock_model

        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"

        result = await self.plugin.after_message_generation(answer, "", [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_not_called()  # 因为模型检查失败，提前返回
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    async def test_after_message_generation_deepseek_with_tool_calls(self):
        """测试deepseek模型有工具调用时不发出警告（因为full_response不为空）。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"

        tool_call_content = """```json toolcall
{"name": "read_file", "arguments": {"filepath": "test.txt"}}
```"""
        result = await self.plugin.after_message_generation(
            answer, tool_call_content, []
        )

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    def test_register(self):
        """测试插件注册。"""
        mock_lifecycle = MagicMock()
        mock_lifecycle.register_after_message_generation = MagicMock()

        self.plugin.register(mock_lifecycle)

        mock_lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()
