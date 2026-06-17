import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.plugin import (
    OnlyReasoningPlugin,
    RuntimeImitationPlugin,
    ToolCallInReasoningPlugin,
)
from linhai.plugin.tool_call_managers import PromptFastAgentPlugin
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

    async def test_after_message_generation_with_only_reasoning_deepseek(self):
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_native_toolcall_format.return_value = False
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = ""

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
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
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_native_toolcall_format.return_value = False
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = "这是实际输出"

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_without_reasoning_deepseek(self):
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_native_toolcall_format.return_value = False
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = None
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = ""

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_with_content_only_deepseek(self):
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_native_toolcall_format.return_value = False
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = None
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = "这是实际输出"

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_with_whitespace_content_deepseek(self):
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_native_toolcall_format.return_value = False
        mock_model.get_compatibility.return_value = "deepseek"
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = "   \n\t  "

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        self.mock_agent.message_processor.update_notification_message.assert_called_once()
        self.registry.send_if_exists.assert_called_once()

    async def test_after_message_generation_non_deepseek_model(self):
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
        answer.get_reasoning_message.assert_not_called()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_non_openai_model(self):
        mock_model = MagicMock()
        self.mock_agent.get_current_model.return_value = mock_model

        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = "这是推理内容"
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = ""

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertIsNone(result)
        answer.get_reasoning_message.assert_not_called()
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_deepseek_with_tool_calls(self):
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_native_toolcall_format.return_value = False
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
        self.mock_agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_deepseek_with_openai_tool_calls(self):
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_native_toolcall_format.return_value = False
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
        self.mock_agent.message_processor.update_notification_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()


class TestRuntimeImitationPlugin(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = MagicMock()
        self.agent.agent_llm = AsyncMock()
        self.agent.get_current_model = MagicMock()

        self.registry = MagicMock()
        self.registry.get_member_typechecked = MagicMock(return_value=self.agent)
        self.registry.send_if_exists = AsyncMock()

        self.plugin = RuntimeImitationPlugin(self.registry)
        self.answer = MagicMock()

        default_model = MagicMock(spec=OpenAi)
        default_model.get_native_toolcall_format.return_value = False
        self.agent.get_current_model.return_value = default_model

    async def test_after_token_generation_deepseek_tool_tag_first_line(self):
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_native_toolcall_format.return_value = False
        self.agent.get_current_model = MagicMock(return_value=mock_model)

        current_content = "<<tool>>"

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)
        self.agent.agent_llm.interrupt.assert_called_once()
        interrupt_msg = self.agent.agent_llm.interrupt.call_args[0][0]
        self.assertIn("不要模仿tool的输出", interrupt_msg)

    async def test_after_token_generation_deepseek_agent_tag_first_line(self):
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_native_toolcall_format.return_value = False
        self.agent.get_current_model = MagicMock(return_value=mock_model)

        current_content = "<<agent>>"

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)
        self.agent.agent_llm.interrupt.assert_called_once()
        interrupt_msg = self.agent.agent_llm.interrupt.call_args[0][0]
        self.assertIn("不要输出<<agent>>这个tag", interrupt_msg)

    async def test_after_token_generation_non_deepseek_model(self):
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "qwen"
        mock_model.get_native_toolcall_format.return_value = False
        self.agent.get_current_model = MagicMock(return_value=mock_model)

        current_content = "<<tool>>"

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)
        self.agent.agent_llm.interrupt.assert_called_once()

    async def test_after_token_generation_tool_xml_start(self):
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        mock_model.get_native_toolcall_format.return_value = False
        self.agent.get_current_model = MagicMock(return_value=mock_model)

        current_content = "<tool>{"

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)
        self.agent.agent_llm.interrupt.assert_called_once()
        interrupt_msg = self.agent.agent_llm.interrupt.call_args[0][0]
        self.assertIn("工具调用的格式是```json toolcall不是XML", interrupt_msg)


class TestToolCallInReasoningPlugin(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.registry = MagicMock()
        self.plugin = ToolCallInReasoningPlugin(self.registry)

        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()

        self.registry.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )
        self.registry.send_if_exists = AsyncMock()
        self.agent.get_current_model.return_value.get_native_toolcall_format.return_value = (
            False
        )

    async def test_after_message_generation_with_tool_call_in_reasoning_and_no_actual_tool_calls(
        self,
    ):
        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        reasoning_content = """我需要调用工具来完成任务。
```json toolcall
{"name": "read_file", "arguments": {"filepath": "test.txt"}}
```
然后调用另一个工具。
```json toolcall
{"name": "list_files", "arguments": {"dirpath": "."}}
```
"""
        answer.get_reasoning_message.return_value = reasoning_content
        answer.reasoning_message = reasoning_content
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = (
            "当前实际输出内容"
        )

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertFalse(result)
        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args
        self.assertIsNotNone(call_args)
        self.assertIn("read_file", call_args[0][0].message)
        self.assertIn("list_files", call_args[0][0].message)
        self.assertIn("警告：你在推理内容中调用了工具", call_args[0][0].message)

        self.registry.send_if_exists.assert_called_once()
        ui_call_args = self.registry.send_if_exists.call_args
        self.assertEqual(ui_call_args[0][0], "ui_log")
        self.assertEqual(ui_call_args[0][1].level, "INFO")
        self.assertIn("read_file", ui_call_args[0][1].content)
        self.assertIn("list_files", ui_call_args[0][1].content)

    async def test_after_message_generation_with_tool_call_in_reasoning_and_actual_tool_calls(
        self,
    ):
        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        reasoning_content = """我需要调用工具来完成任务。
```json toolcall
{"name": "read_file", "arguments": {"filepath": "test.txt"}}
```
然后调用另一个工具。
```json toolcall
{"name": "list_files", "arguments": {"dirpath": "."}}
```
"""
        answer.get_reasoning_message.return_value = reasoning_content
        answer.reasoning_message = reasoning_content
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = (
            "当前实际输出内容"
        )

        actual_tool_calls = [
            {"name": "read_file", "arguments": {"filepath": "test.txt"}},
            {"name": "list_files", "arguments": {"dirpath": "."}},
        ]

        result = await self.plugin.after_message_generation(
            parsed_answer, actual_tool_calls
        )

        self.assertFalse(result)
        self.agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_without_reasoning_content(self):
        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        answer.get_reasoning_message.return_value = None
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = (
            "当前实际输出内容"
        )

        with patch.object(
            self.plugin.registry, "get_member_typechecked", return_value=self.agent
        ):
            result = await self.plugin.after_message_generation(parsed_answer, [])

            self.assertFalse(result)
            self.registry.send_if_exists.assert_not_called()
            self.agent.message_processor.add_new_message.assert_not_called()

    async def test_after_message_generation_with_reasoning_but_no_tool_calls(self):
        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        reasoning_content = "我只是在思考，没有工具调用。"
        answer.get_reasoning_message.return_value = reasoning_content
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = (
            "当前实际输出内容"
        )

        with patch.object(
            self.plugin.registry, "get_member_typechecked", return_value=self.agent
        ):
            result = await self.plugin.after_message_generation(parsed_answer, [])

            self.assertFalse(result)
            self.registry.send_if_exists.assert_not_called()
            self.agent.message_processor.add_new_message.assert_not_called()

    async def test_after_message_generation_with_duplicate_tool_names(self):
        parsed_answer = MagicMock()
        answer = MagicMock(spec=Answer)
        reasoning_content = """```json toolcall
{"name": "read_file", "arguments": {"filepath": "test1.txt"}}
```
```json toolcall
{"name": "read_file", "arguments": {"filepath": "test2.txt"}}
```
"""
        answer.get_reasoning_message.return_value = reasoning_content
        parsed_answer._answer = answer
        parsed_answer.get_message.return_value.get_content.return_value = (
            "当前实际输出内容"
        )

        result = await self.plugin.after_message_generation(parsed_answer, [])

        self.assertFalse(result)

        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args
        self.assertIsNotNone(call_args)
        self.assertIn("read_file", call_args[0][0].message)
        self.assertEqual(call_args[0][0].message.count("read_file"), 1)
        self.assertIn("警告：你在推理内容中调用了工具", call_args[0][0].message)

        self.registry.send_if_exists.assert_called_once()
        ui_call_args = self.registry.send_if_exists.call_args
        self.assertEqual(ui_call_args[0][0], "ui_log")
        self.assertEqual(ui_call_args[0][1].level, "INFO")
        self.assertIn("read_file", ui_call_args[0][1].content)
        self.assertEqual(ui_call_args[0][1].content.count("read_file"), 1)


class TestPromptFastAgentPlugin(unittest.TestCase):

    def setUp(self):
        self.registry = MagicMock(spec=Registry)
        self.max_toolcall_for_llm = {"test-llm": 3, "another-llm": 5}
        self.plugin = PromptFastAgentPlugin(self.registry, self.max_toolcall_for_llm)

    def test_get_max_toolcall_for_current_model_with_configured_llm(self):
        agent = MagicMock()
        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "test-llm"
        model.get_native_toolcall_format.return_value = False
        agent.get_current_model.return_value = model

        result = self.plugin._get_max_toolcall_for_current_model(agent)

        self.assertEqual(result, 3)

    def test_get_max_toolcall_for_current_model_with_unconfigured_llm(self):
        agent = MagicMock()
        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "unconfigured-llm"
        agent.get_current_model.return_value = model

        result = self.plugin._get_max_toolcall_for_current_model(agent)

        self.assertIsNone(result)

    def test_before_message_generation_with_configured_llm(self):
        agent = MagicMock()
        agent.get_current_model = MagicMock()
        agent.message_processor.update_notification_message = MagicMock()

        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "test-llm"
        model.get_native_toolcall_format.return_value = False
        agent.get_current_model.return_value = model

        self.registry.get_member_typechecked = MagicMock(return_value=agent)
        self.registry.send_if_exists = AsyncMock()

        asyncio.run(self.plugin.before_message_generation())

        agent.message_processor.update_notification_message.assert_called_once()
        self.registry.send_if_exists.assert_not_called()

        agent.message_processor.update_notification_message.reset_mock()
        self.registry.send_if_exists.reset_mock()

        asyncio.run(self.plugin.before_message_generation())

        agent.message_processor.update_notification_message.assert_called_once()
        self.registry.send_if_exists.assert_not_called()

    def test_before_message_generation_with_unconfigured_llm(self):
        agent = MagicMock()
        agent.get_current_model = MagicMock()
        agent.message_processor.update_notification_message = MagicMock()

        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "unconfigured-llm"
        agent.get_current_model.return_value = model

        self.registry.get_member_typechecked = MagicMock(return_value=agent)
        self.registry.send_if_exists = AsyncMock()

        asyncio.run(self.plugin.before_message_generation())

        agent.message_processor.update_notification_message.assert_called_once_with(
            None, source="prompt_fast_agent"
        )
        self.registry.send_if_exists.assert_not_called()

    def test_after_token_generation_exceeds_limit(self):
        agent = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()
        self.registry.send_if_exists = AsyncMock()

        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "test-llm"
        model.get_native_toolcall_format.return_value = False
        agent.get_current_model.return_value = model

        answer = MagicMock(spec=Answer)

        current_content = "\n```json toolcall\n{}```\n" * 4

        result = asyncio.run(
            self.plugin.after_token_generation(agent, answer, current_content)
        )

        self.assertFalse(result)
        answer.truncate.assert_called_once()
        agent.message_processor.add_new_message.assert_called_once()
        self.assertEqual(self.plugin.speeding_counter, 1)

    def test_after_token_generation_within_limit(self):
        agent = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()
        self.registry.send_if_exists = AsyncMock()

        model = MagicMock(spec=OpenAi)
        model.get_name.return_value = "test-llm"
        model.get_native_toolcall_format.return_value = False
        agent.get_current_model.return_value = model

        answer = MagicMock(spec=Answer)

        current_content = "\n```json toolcall\n{}```\n" * 2

        result = asyncio.run(
            self.plugin.after_token_generation(agent, answer, current_content)
        )

        self.assertFalse(result)
        answer.truncate.assert_not_called()
        agent.message_processor.add_new_message.assert_not_called()
        self.assertEqual(self.plugin.speeding_counter, 0)

    def test_after_token_generation_unconfigured_llm(self):
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

    def test_switch_llm_with_different_limits(self):
        max_toolcall_for_llm = {"llm-a": 3, "llm-b": 5}
        plugin = PromptFastAgentPlugin(self.registry, max_toolcall_for_llm)

        agent = MagicMock()
        model_a = MagicMock(spec=OpenAi)
        model_a.get_name.return_value = "llm-a"
        agent.get_current_model.return_value = model_a

        max_toolcall = plugin._get_max_toolcall_for_current_model(agent)
        self.assertEqual(max_toolcall, 3)

        model_b = MagicMock(spec=OpenAi)
        model_b.get_name.return_value = "llm-b"
        agent.get_current_model.return_value = model_b

        max_toolcall = plugin._get_max_toolcall_for_current_model(agent)
        self.assertEqual(max_toolcall, 5)

        model_c = MagicMock(spec=OpenAi)
        model_c.get_name.return_value = "llm-c"
        agent.get_current_model.return_value = model_c

        max_toolcall = plugin._get_max_toolcall_for_current_model(agent)
        self.assertIsNone(max_toolcall)


if __name__ == "__main__":
    unittest.main()
