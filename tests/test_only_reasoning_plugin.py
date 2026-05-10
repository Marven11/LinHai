import unittest
from unittest.mock import MagicMock, AsyncMock
import asyncio

from linhai.plugin import OnlyReasoningPlugin
from linhai.registry import Registry
from linhai.base import Answer
from linhai.llm import OpenAi
from linhai.agent.messages import RuntimeMessage
from linhai.utils.common import UiNotice


class TestOnlyReasoningPlugin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = MagicMock(spec=Registry)
        self.plugin = OnlyReasoningPlugin(self.registry)

        self.mock_agent = MagicMock()
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.message_processor.add_new_message = MagicMock()
        self.mock_agent.message_processor.update_notification_message = MagicMock()
        self.mock_agent.get_current_model = MagicMock()

        self.registry.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.mock_agent
        )

        self.registry.send_if_exists = AsyncMock()

    def test_plugin_initialization(self):
        """测试插件初始化。"""
        self.assertIsInstance(self.plugin, OnlyReasoningPlugin)
        self.assertEqual(self.plugin.registry, self.registry)

    async def test_after_message_generation_with_only_reasoning_deepseek(self):
        """测试deepseek模型只有推理内容没有实际输出时发出警告。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = ""

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.update_notification_message.assert_called_once()
        self.registry.send_if_exists.assert_called_once()

        call_args = (
            self.mock_agent.message_processor.update_notification_message.call_args
        )
        warning_message = call_args[0][0]
        self.assertIsInstance(warning_message, RuntimeMessage)
        self.assertIn("</thinking>", warning_message.message)

        ui_call_args = self.registry.send_if_exists.call_args
        self.assertEqual(ui_call_args[0][0], "ui_log")
        self.assertIsInstance(ui_call_args[0][1], UiNotice)
        self.assertEqual(ui_call_args[0][1].level, "INFO")
        self.assertIn("只思考不输出", ui_call_args[0][1].content)

    async def test_after_message_generation_with_reasoning_and_content_deepseek(self):
        """测试deepseek模型既有推理内容又有实际输出时不发出警告。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = "这是实际输出"

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_without_reasoning_deepseek(self):
        """测试deepseek模型没有推理内容时不发出警告。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = None
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = ""

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_with_content_only_deepseek(self):
        """测试deepseek模型只有实际输出没有推理内容时不发出警告。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = None
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = "这是实际输出"

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_with_whitespace_content_deepseek(self):
        """测试deepseek模型推理内容有但实际输出只有空白字符时发出警告。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = "   \n\t  "

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.update_notification_message.assert_called_once()
        self.registry.send_if_exists.assert_called_once()

    async def test_after_message_generation_non_deepseek_model(self):
        """测试非deepseek模型时不检查只思考不输出。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "minimax"
        mock_model.get_compatibility.return_value = "minimax"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = ""

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_not_called()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_non_openai_model(self):
        """测试非OpenAi模型时不检查只思考不输出。"""
        mock_model = MagicMock()  # 不是OpenAi实例
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = ""

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_not_called()  # 因为模型检查失败，提前返回
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_deepseek_with_tool_calls(self):
        """测试deepseek模型有工具调用时不发出警告（因为full_response不为空）。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer

        tool_call_content = """```json toolcall
{"name": "read_file", "arguments": {"filepath": "test.txt"}}
```"""
        parsed_answer.get_message.return_value.get_content.return_value = (
            tool_call_content
        )
        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_deepseek_with_openai_tool_calls(self):
        """测试deepseek模型使用OpenAI工具调用时不发出警告（tool_calls参数非空）。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = ""

        tool_calls = [{"name": "read_file", "arguments": {"filepath": "test.txt"}}]
        result = await self.plugin.after_message_generation(parsed_answer, tool_calls)

        self.assertIsNone(result)
        self.mock_agent.get_current_model.assert_called_once()
        answer.get_reasoning_message.assert_called_once()
        self.mock_agent.message_processor.update_notification_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    def test_register(self):
        """测试插件注册。"""
        mock_lifecycle = MagicMock()
        mock_lifecycle.after_message_generation.register = MagicMock()

        self.plugin.register(mock_lifecycle)

        mock_lifecycle.after_message_generation.register.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()
