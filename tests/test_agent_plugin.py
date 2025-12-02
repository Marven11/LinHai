"""测试agent_plugin模块。"""

import unittest
from unittest.mock import MagicMock, AsyncMock
from linhai.agent.plugin import BadMultiToolCall, WeirdTokenPlugin, DirectoryChangePlugin, PromptFastAgentPlugin, PreventToolOutputPlugin
from linhai.agent.base import RuntimeMessage
from linhai.llm import OpenAi, UserMessage, AssistantMessage
import pathlib


class TestBadMultiToolCall(unittest.IsolatedAsyncioTestCase):
    """测试BadMultiToolCall类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        self.group_chat = MagicMock()
        self.group_chat.get_members = MagicMock(return_value=self.agent)
        self.plugin = BadMultiToolCall(self.group_chat)
        self.answer = MagicMock()
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )

    async def test_after_message_generation_with_bad_multi_tool_call(self):
        """测试有多个工具调用但没有输出原因的情况。"""
        full_response = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.update_appending_message = MagicMock()

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertTrue(self.agent.message_processor.update_appending_message.called)
        call_args_list = self.agent.message_processor.update_appending_message.call_args_list
        warning_call = None
        for call in call_args_list:
            if getattr(call, 'kwargs', {}).get("source") == "bad_multi_tool_call":
                warning_call = call
                break
        self.assertIsNotNone(warning_call, "没有找到source为'bad_multi_tool_call'的调用")
        assert warning_call is not None
        self.assertEqual(warning_call.args[0], "警告：你是不是忘记在多个工具调用之间输出可以同时调用的原因了？\n"
                                      "你需要在两个code block中间输出上下两个工具调用可以同时进行的原因！\n"
                                      + self.plugin.example)

    async def test_after_message_generation_with_good_multi_tool_call(self):
        """测试有正常分隔的工具调用块的情况。"""
        full_response = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

同时调用的原因：这两个工具没有顺序依赖

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(len(self.agent.message_processor.get_messages()), 0)

    async def test_after_message_generation_with_single_tool_call(self):
        """测试只有单个工具调用的情况。"""
        full_response = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

更多内容"""

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(len(self.agent.message_processor.get_messages()), 0)

    async def test_after_message_generation_with_reason_output_after_no_reason(self):
        """测试上一条消息没有输出原因，当前消息输出了原因的情况。"""
        full_response1 = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

更多内容"""

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()

        await self.plugin.after_message_generation(
            self.answer, full_response1, self.tool_calls
        )

        self.assertEqual(len(self.agent.message_processor.get_messages()), 0)

        full_response2 = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

同时调用的原因：这两个工具没有顺序依赖

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()

        await self.plugin.after_message_generation(
            self.answer, full_response2, self.tool_calls
        )

        self.assertEqual(len(self.agent.message_processor.get_messages()), 0)

    async def test_after_message_generation_with_reason_output_after_reason(self):
        """测试上一条消息输出了原因，当前消息也输出了原因的情况。"""
        self.plugin.last_message_had_reason = True
        
        full_response1 = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

同时调用的原因：这两个工具没有顺序依赖

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()

        await self.plugin.after_message_generation(
            self.answer, full_response1, self.tool_calls
        )

        self.assertEqual(len(self.agent.message_processor.get_messages()), 0)
    async def test_after_message_generation_with_multiple_tool_calls_no_reason(self):
        """测试有多个工具调用但没有输出原因的情况。"""
        full_response = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.update_appending_message = MagicMock()

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertTrue(self.agent.message_processor.update_appending_message.called)
        call_args_list = self.agent.message_processor.update_appending_message.call_args_list
        warning_call = None
        for call in call_args_list:
            if getattr(call, 'kwargs', {}).get("source") == "bad_multi_tool_call":
                warning_call = call
                break
        self.assertIsNotNone(warning_call, "没有找到source为'bad_multi_tool_call'的调用")
        assert warning_call is not None
        self.assertEqual(warning_call.args[0], "警告：你是不是忘记在多个工具调用之间输出可以同时调用的原因了？\n"
                                      "你需要在两个code block中间输出上下两个工具调用可以同时进行的原因！\n"
                                      + self.plugin.example)

    async def test_after_message_generation_with_multiple_tool_calls_and_reason(self):
        """测试有多个工具调用且输出了原因的情况。"""
        full_response = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

同时调用的原因：这两个工具没有顺序依赖

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(len(self.agent.message_processor.get_messages()), 0)


class TestWeirdEndOfSentencePlugin(unittest.IsolatedAsyncioTestCase):
    """测试WeirdEndOfSentencePlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        self.agent.group_chat = MagicMock()
        self.agent.group_chat.send = AsyncMock()
        self.agent.interrupt = AsyncMock(side_effect=lambda msg=None: self.agent.message_processor.append_message(RuntimeMessage(msg or "Agent被插件打断")))  # 添加interrupt mock并模拟添加消息
        self.agent.get_current_model = AsyncMock()
        self.group_chat = MagicMock()
        self.group_chat.get_members = MagicMock(return_value=self.agent)
        self.plugin = WeirdTokenPlugin(self.group_chat)
        self.answer = MagicMock()
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_during_message_generation.assert_called_once_with(
            self.plugin.during_message_generation
        )

    async def test_during_message_generation_with_chinese_end_marker(self):
        """测试有中文句子结束标记的情况。"""
        current_content = """这是一些内容
这是一行中文<｜end▁of▁thought｜><｜end▁of▁sentence｜>
这是另一行内容"""

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        self.agent.group_chat = MagicMock()
        self.agent.group_chat.send = AsyncMock()

        result = await self.plugin.during_message_generation(
            self.answer, current_content
        )

        self.assertTrue(result)
        self.agent.interrupt.assert_called_once()
        self.assertTrue(self.agent.message_processor.append_message.called)
        call_args = self.agent.message_processor.append_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn("结束标记", call_args[0].message)


class TestDirectoryChangePlugin(unittest.IsolatedAsyncioTestCase):
    """测试DirectoryChangePlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        self.agent.context = {"enable_directory_change_detection": False}  # 默认关闭
        self.group_chat = MagicMock()
        self.group_chat.get_members = MagicMock(return_value=self.agent)
        self.plugin = DirectoryChangePlugin(self.group_chat)

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_before_message_generation.assert_called_once_with(
            self.plugin.before_message_generation
        )

    async def test_before_message_generation_disabled(self):
        """测试目录更改检测关闭的情况。"""
        self.plugin.last_directory = pathlib.Path("/old/path")
        
        await self.plugin.before_message_generation(True, False)
        
        self.assertIsNotNone(self.plugin.last_directory)

    async def test_before_message_generation_enabled_no_change(self):
        """测试目录更改检测开启但目录未更改的情况。"""
        self.agent.context["enable_directory_change_detection"] = True
        
        current_dir = pathlib.Path.cwd()
        self.plugin.last_directory = current_dir
        
        await self.plugin.before_message_generation(True, False)
        
        self.assertEqual(len(self.agent.message_processor.get_messages()), 0)

    async def test_before_message_generation_enabled_with_change(self):
        """测试目录更改检测开启且目录更改的情况。"""
        self.agent.context["enable_directory_change_detection"] = True
        
        self.plugin.last_directory = pathlib.Path("/old/path")
        
        current_dir = pathlib.Path.cwd()
        
        await self.plugin.before_message_generation(True, False)
        
        self.assertEqual(self.plugin.last_directory, current_dir)

    async def test_before_message_generation_no_duplicate_pathmemory(self):
        """测试避免重复添加相同路径的PathMemory。"""
        self.agent.context["enable_directory_change_detection"] = True
        
        self.plugin.last_directory = pathlib.Path("/old/path")
        
        from linhai.agent.base import PathMemory
        existing_pathmemory = PathMemory(pathlib.Path.cwd() / "LINHAI.md")
        self.agent.message_processor.get_messages.return_value = [existing_pathmemory]
        
        await self.plugin.before_message_generation(True, False)
        







class TestSingleToolCallReminderPlugin(unittest.IsolatedAsyncioTestCase):
    """测试SingleToolCallReminderPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        self.group_chat = MagicMock()
        self.group_chat.get_members = MagicMock(return_value=self.agent)
        from linhai.agent.plugin import SingleToolCallReminderPlugin
        self.plugin = SingleToolCallReminderPlugin(self.group_chat)
        self.answer = MagicMock()
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )

    async def test_after_message_generation_with_single_tool_call(self):
        """测试连续多次只调用一个工具的情况。"""
        full_response = "一些内容"
        tool_calls = [{"name": "tool1", "arguments": {}}]

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.update_appending_message = MagicMock()

        for _ in range(5):
            await self.plugin.after_message_generation(
                self.answer, full_response, tool_calls
            )

        self.assertEqual(self.plugin.single_tool_call_count, 5)
        call_args_list = self.agent.message_processor.update_appending_message.call_args_list
        last_call_args = call_args_list[-1]
        self.assertIn("连续5次仅调用一个工具", last_call_args[0][0])
        self.assertEqual(last_call_args[1]["source"], "single_tool_call_reminder")

    async def test_after_message_generation_with_multiple_tool_calls(self):
        """测试调用多个工具时重置计数器。"""
        full_response = "一些内容"
        
        self.agent.message_processor.update_appending_message = MagicMock()
        
        for _ in range(4):
            await self.plugin.after_message_generation(
                self.answer, full_response, [{"name": "tool1", "arguments": {}}]
            )
        
        self.assertEqual(self.plugin.single_tool_call_count, 4)
        
        await self.plugin.after_message_generation(
            self.answer, full_response, [
                {"name": "tool1", "arguments": {}},
                {"name": "tool2", "arguments": {}}
            ]
        )
        
        self.assertEqual(self.plugin.single_tool_call_count, 0)
        
        last_call_args = self.agent.message_processor.update_appending_message.call_args
        self.assertEqual(last_call_args[0][0], None)
        self.assertEqual(last_call_args[1]["source"], "single_tool_call_reminder")

    async def test_after_message_generation_with_zero_tool_calls(self):
        """测试没有调用工具时重置计数器。"""
        full_response = "一些内容"
        
        self.agent.message_processor.update_appending_message = MagicMock()
        
        for _ in range(3):
            await self.plugin.after_message_generation(
                self.answer, full_response, [{"name": "tool1", "arguments": {}}]
            )
        
        self.assertEqual(self.plugin.single_tool_call_count, 3)
        
        await self.plugin.after_message_generation(
            self.answer, full_response, []
        )
        
        self.assertEqual(self.plugin.single_tool_call_count, 0)
        
        last_call_args = self.agent.message_processor.update_appending_message.call_args
        self.assertEqual(last_call_args[0][0], None)
        self.assertEqual(last_call_args[1]["source"], "single_tool_call_reminder")

class TestPromptFastAgentPlugin(unittest.IsolatedAsyncioTestCase):
    """测试PromptFastAgentPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        self.agent.interrupt = AsyncMock()
        self.agent.get_current_model = AsyncMock()
        self.group_chat = MagicMock()
        self.group_chat.get_members = MagicMock(return_value=self.agent)
        self.group_chat.send_if_exists = AsyncMock()
        self.plugin = PromptFastAgentPlugin(self.group_chat)
        self.answer = MagicMock()
        self.answer.truncate = MagicMock()
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_during_message_generation.assert_called_once_with(
            self.plugin.during_message_generation
        )

    async def test_during_message_generation_with_too_many_tool_calls(self):
        """测试工具调用超过限制时使用truncate。"""
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "minimax"
        self.agent.get_current_model = AsyncMock(return_value=mock_model)
        
        self.agent.message_processor.get_messages.return_value = [
            AssistantMessage(message="previous message")
        ]
        
        current_content = """
```json toolcall
{"name": "tool1", "arguments": {}}
```
```json toolcall
{"name": "tool2", "arguments": {}}
```
```json toolcall
{"name": "tool3", "arguments": {}}
```
```json toolcall
{"name": "tool4", "arguments": {}}
```
```json toolcall
{"name": "tool5", "arguments": {}}
```
```json toolcall
{"name": "tool6", "arguments": {}}
```
"""
        
        result = await self.plugin.during_message_generation(
            self.answer, current_content
        )
        
        self.assertFalse(result)
        
        self.assertTrue(self.agent.message_processor.append_message.called)
        call_args = self.agent.message_processor.append_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn("禁止超速", call_args[0].message)
        self.assertIn("minimax", call_args[0].message)
        
        self.answer.truncate.assert_called_once()
        self.agent.interrupt.assert_not_called()


class TestPreventToolOutputPlugin(unittest.IsolatedAsyncioTestCase):
    """测试PreventToolOutputPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        self.agent.interrupt = AsyncMock()
        self.group_chat = MagicMock()
        self.group_chat.get_members = MagicMock(return_value=self.agent)
        self.group_chat.send_if_exists = AsyncMock()
        self.plugin = PreventToolOutputPlugin(self.group_chat)
        self.answer = MagicMock()
        self.answer.truncate = MagicMock()
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_during_message_generation.assert_called_once_with(
            self.plugin.during_message_generation
        )

    async def test_during_message_generation_with_tool_output(self):
        """测试检测到工具输出时使用truncate。"""
        self.agent.message_processor.get_messages.return_value = []
        
        current_content = """**tool** 返回了结果
这是工具调用的内容"""
        
        result = await self.plugin.during_message_generation(
            self.answer, current_content
        )
        
        self.assertFalse(result)
        
        self.assertTrue(self.agent.message_processor.append_message.called)
        call_args = self.agent.message_processor.append_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn("请不要输出工具调用的内容", call_args[0].message)
        
        self.answer.truncate.assert_called_once()
        self.agent.interrupt.assert_not_called()

    async def test_during_message_generation_without_tool_output(self):
        """测试没有工具输出时不应该中断。"""
        self.agent.message_processor.get_messages.return_value = []
        
        current_content = """这是正常的回复内容
没有工具调用的标记"""
        
        result = await self.plugin.during_message_generation(
            self.answer, current_content
        )
        
        self.assertFalse(result)
        
        self.answer.truncate.assert_not_called()
        self.agent.interrupt.assert_not_called()

    async def test_during_message_generation_with_previous_message(self):
        """测试有之前的assistant消息时不检查工具输出。"""
        self.agent.message_processor.get_messages.return_value = [
            AssistantMessage(message="previous message")
        ]
        
        current_content = """**tool** 返回了结果
这是工具调用的内容"""
        
        result = await self.plugin.during_message_generation(
            self.answer, current_content
        )
        
        self.assertFalse(result)
        
        self.answer.truncate.assert_not_called()
        self.agent.interrupt.assert_not_called()
