"""测试ToolCallInReasoningPlugin插件。"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.plugin import ToolCallInReasoningPlugin
from linhai.base import Answer


class TestToolCallInReasoningPlugin(unittest.IsolatedAsyncioTestCase):
    """测试ToolCallInReasoningPlugin插件。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = MagicMock()
        self.plugin = ToolCallInReasoningPlugin(self.registry)

        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()

        self.registry.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )
        self.registry.send_if_exists = AsyncMock()

    def test_plugin_initialization(self):
        """测试插件初始化。"""
        self.assertIsInstance(self.plugin, ToolCallInReasoningPlugin)
        self.assertEqual(self.plugin.registry, self.registry)

    async def test_after_message_generation_with_tool_call_in_reasoning_and_no_actual_tool_calls(
        self,
    ):
        """测试思考内容中包含工具调用但实际输出中没有工具调用时发出警告。"""
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

        self.assertFalse(result)  # 不应该中断
        answer.get_reasoning_message.assert_called_once()

        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args
        self.assertIsNotNone(call_args)
        self.assertIn("read_file", call_args[0][0].message)
        self.assertIn("list_files", call_args[0][0].message)
        self.assertIn("警告：你在推理内容中调用了工具", call_args[0][0].message)

        self.registry.send_if_exists.assert_called_once()
        ui_call_args = self.registry.send_if_exists.call_args
        self.assertEqual(ui_call_args[0][0], "ui_log")
        self.assertEqual(ui_call_args[0][1].level, "WARNING")
        self.assertIn("read_file", ui_call_args[0][1].content)
        self.assertIn("list_files", ui_call_args[0][1].content)

    async def test_after_message_generation_with_tool_call_in_reasoning_and_actual_tool_calls(
        self,
    ):
        """测试思考内容中包含工具调用且实际输出中也调用了工具时不发出警告。"""
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
        answer.get_reasoning_message.assert_called_once()
        self.agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_without_reasoning_content(self):
        """测试没有思考内容时不做任何操作。"""
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
            answer.get_reasoning_message.assert_called_once()
            self.registry.send_if_exists.assert_not_called()
            self.agent.message_processor.add_new_message.assert_not_called()

    async def test_after_message_generation_with_reasoning_but_no_tool_calls(self):
        """测试思考内容中没有工具调用时不做任何操作。"""
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
            answer.get_reasoning_message.assert_called_once()
            self.registry.send_if_exists.assert_not_called()
            self.agent.message_processor.add_new_message.assert_not_called()

    async def test_after_message_generation_with_duplicate_tool_names(self):
        """测试重复工具名称时去重。"""
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
        self.assertEqual(ui_call_args[0][1].level, "WARNING")
        self.assertIn("read_file", ui_call_args[0][1].content)
        self.assertEqual(ui_call_args[0][1].content.count("read_file"), 1)

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        lifecycle.after_message_generation.register = MagicMock()

        self.plugin.register(lifecycle)

        lifecycle.after_message_generation.register.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()
