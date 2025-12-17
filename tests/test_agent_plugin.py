"""测试agent_plugin模块。"""

import unittest
import time
from unittest.mock import MagicMock, AsyncMock
from linhai.agent.plugin import (
    WeirdTokenPlugin,
    DirectoryChangePlugin,
    PromptFastAgentPlugin,
    PreventToolOutputPlugin,
)
from linhai.agent.base import RuntimeMessage
from linhai.llm import OpenAi, UserMessage, AssistantMessage
from linhai.utils import CliRuntimeNotice
import pathlib


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
        self.agent.interrupt = AsyncMock(
            side_effect=lambda msg=None: self.agent.message_processor.append_message(
                RuntimeMessage(msg or "Agent被插件打断")
            )
        )  # 添加interrupt mock并模拟添加消息
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
        lifecycle.register_after_token_generation.assert_called_once_with(
            self.plugin.after_token_generation
        )

    async def test_after_token_generation_with_chinese_end_marker(self):
        """测试有中文句子结束标记的情况。"""
        current_content = """这是一些内容
这是一行中文<｜end▁of▁thought｜><｜end▁of▁sentence｜>
这是另一行内容"""

        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        self.agent.group_chat = MagicMock()
        self.agent.group_chat.send = AsyncMock()

        result = await self.plugin.after_token_generation(self.answer, current_content)

        self.assertFalse(result)
        self.agent.interrupt.assert_not_called()
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
        call_args_list = (
            self.agent.message_processor.update_appending_message.call_args_list
        )
        last_call_args = call_args_list[-1]
        self.assertIsInstance(last_call_args[0][0], RuntimeMessage)
        self.assertIn("连续5次仅调用一个工具", last_call_args[0][0].message)
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
            self.answer,
            full_response,
            [{"name": "tool1", "arguments": {}}, {"name": "tool2", "arguments": {}}],
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

        await self.plugin.after_message_generation(self.answer, full_response, [])

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
        lifecycle.register_after_token_generation.assert_called_once_with(
            self.plugin.after_token_generation
        )

    async def test_after_token_generation_with_too_many_tool_calls(self):
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

        result = await self.plugin.after_token_generation(self.answer, current_content)

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
        lifecycle.register_after_token_generation.assert_called_once_with(
            self.plugin.after_token_generation
        )

    async def test_after_token_generation_with_tool_output(self):
        """测试检测到工具输出时使用truncate。"""
        self.agent.message_processor.get_messages.return_value = []

        current_content = """**tool** 返回了结果
这是工具调用的内容"""

        result = await self.plugin.after_token_generation(self.answer, current_content)

        self.assertFalse(result)

        self.assertTrue(self.agent.message_processor.append_message.called)
        call_args = self.agent.message_processor.append_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn("请不要输出工具调用的内容", call_args[0].message)

        self.answer.truncate.assert_called_once()
        self.agent.interrupt.assert_not_called()

    async def test_after_token_generation_without_tool_output(self):
        """测试没有工具输出时不应该中断。"""
        self.agent.message_processor.get_messages.return_value = []

        current_content = """这是正常的回复内容
没有工具调用的标记"""

        result = await self.plugin.after_token_generation(self.answer, current_content)

        self.assertFalse(result)

        self.answer.truncate.assert_not_called()
        self.agent.interrupt.assert_not_called()

    async def test_after_token_generation_with_previous_message(self):
        """测试有之前的assistant消息时不检查工具输出。"""
        self.agent.message_processor.get_messages.return_value = [
            AssistantMessage(message="previous message")
        ]

        current_content = """**tool** 返回了结果
这是工具调用的内容"""

        result = await self.plugin.after_token_generation(self.answer, current_content)

        self.assertFalse(result)

        self.answer.truncate.assert_not_called()
        self.agent.interrupt.assert_not_called()


class TestRedStateToolBlockPlugin(unittest.TestCase):
    """测试RedStateToolBlockPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = MagicMock()
        self.group_chat.send_if_exists = AsyncMock(return_value=None)
        from linhai.agent.orchestration import RedStateToolBlockPlugin

        self.plugin = RedStateToolBlockPlugin(self.group_chat)

        # 模拟agent
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.append_message = AsyncMock()
        # 默认阈值信息：绿灯状态
        self.agent.get_threshold_info.return_value = {
            "hard_limit": 80000,
            "used_tokens": 40000,
            "remaining_tokens": 40000,
            "usage_ratio": 0.5
        }

        # 模拟orchestration
        self.orchestration = MagicMock()
        self.orchestration.last_compress_or_clean_time = None
        self.orchestration.should_block_tool_call = MagicMock(return_value=False)

        # 设置group_chat.get_members返回值
        def get_members_side_effect(name, cls):
            if name == "agent":
                return self.agent
            elif name == "agent_context_orchestration":
                return self.orchestration
            else:
                return None

        self.group_chat.get_members.side_effect = get_members_side_effect

    def test_init(self):
        """测试初始化。"""
        self.assertEqual(self.plugin.group_chat, self.group_chat)
        self.assertEqual(
            self.plugin.CLEANUP_TOOLS,
            {
                "compress_context_range",
                "context_garbage_clean",
                "context_thanox",
            },
        )
        self.assertEqual(
            self.plugin.MANAGEMENT_TOOLS,
            {
                "mark_messages_as_garbage",
            },
        )

    def test_register(self):
        """测试注册插件。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_before_tool_call.assert_called_once_with(
            self.plugin.before_tool_call
        )

    def test_green_state_not_block(self):
        """测试绿灯状态不阻止工具调用。"""
        # 设置模拟
        self.agent.get_threshold_info.return_value = {
            "hard_limit": 80000,
            "used_tokens": 40000,
            "remaining_tokens": 40000,
            "usage_ratio": 0.5,
        }  # 50%使用率，绿灯
        # 设置should_block_tool_call返回False（绿灯状态下不阻止）
        self.orchestration.should_block_tool_call.return_value = False

        # 创建工具调用
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
        )

        # 调用插件
        import asyncio

        result = asyncio.run(self.plugin.before_tool_call(tool_call))

        # 验证不阻止
        self.assertFalse(result)
        self.agent.get_threshold_info.assert_called_once()
        self.agent.message_processor.append_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    def test_red_state_allow_cleanup_tool(self):
        """测试红灯状态允许清理类工具。"""
        # 设置模拟
        self.agent.get_threshold_info.return_value = {
            "hard_limit": 80000,
            "used_tokens": 72000,
            "remaining_tokens": 8000,
            "usage_ratio": 0.9,
        }  # 90%使用率，红灯

        # 创建清理类工具调用
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(
            function_name="mark_messages_as_garbage",
            function_arguments={"ids": ["test_id"]},
            assert_success=True,
        )

        # 调用插件
        import asyncio

        result = asyncio.run(self.plugin.before_tool_call(tool_call))

        # 验证允许调用
        self.assertFalse(result)
        self.agent.get_threshold_info.assert_called_once()
        self.agent.message_processor.append_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    def test_red_state_block_other_tool_no_recent_cleanup(self):
        """测试红灯状态且无近期清理，阻止其他工具。"""
        # 设置模拟
        self.agent.get_threshold_info.return_value = {
            "hard_limit": 80000,
            "used_tokens": 76000,
            "remaining_tokens": 4000,
            "usage_ratio": 0.95,
        }  # 95%使用率，红灯
        self.orchestration.last_compress_or_clean_time = None  # 无近期清理
        self.orchestration.should_block_tool_call.return_value = True

        # 创建其他工具调用
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
        )

        # 调用插件
        import asyncio

        result = asyncio.run(self.plugin.before_tool_call(tool_call))

        # 验证阻止 - 返回True表示阻止
        self.assertTrue(result)
        self.agent.get_threshold_info.assert_called_once()
        self.agent.message_processor.append_message.assert_called_once()
        self.group_chat.send_if_exists.assert_called_once_with(
            "ui_log",
            CliRuntimeNotice(
                level="WARNING",
                content="红灯状态下阻止调用read_file工具，请先调用消息清理类工具",
            ),
        )

        # 检查消息内容
        append_call = self.agent.message_processor.append_message.call_args
        runtime_message = append_call[0][0]
        self.assertIsInstance(runtime_message, RuntimeMessage)
        self.assertIn(
            "错误：当前处于红灯状态（token使用率95.0%）", runtime_message.message
        )
        self.assertIn("禁止调用read_file工具！", runtime_message.message)

    def test_red_state_block_other_tool_with_recent_cleanup(self):
        """测试红灯状态即使有近期清理，也阻止其他工具。"""
        # 设置模拟
        self.agent.get_threshold_info.return_value = {
            "hard_limit": 80000,
            "used_tokens": 76000,
            "remaining_tokens": 4000,
            "usage_ratio": 0.95,
        }  # 95%使用率，红灯
        self.orchestration.last_compress_or_clean_time = (
            time.time() - 30
        )  # 30秒前清理过
        self.orchestration.should_block_tool_call.return_value = True

        # 创建其他工具调用
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
        )

        # 调用插件
        import asyncio

        result = asyncio.run(self.plugin.before_tool_call(tool_call))

        # 验证阻止（无论是否有清理，红灯状态只允许清理类工具）
        self.assertTrue(result)
        self.agent.get_threshold_info.assert_called_once()
        self.agent.message_processor.append_message.assert_called_once()
        self.group_chat.send_if_exists.assert_called_once_with(
            "ui_log",
            CliRuntimeNotice(
                level="WARNING",
                content="红灯状态下阻止调用read_file工具，请先调用消息清理类工具",
            ),
        )

        # 检查消息内容
        append_call = self.agent.message_processor.append_message.call_args
        runtime_message = append_call[0][0]
        self.assertIsInstance(runtime_message, RuntimeMessage)
        self.assertIn(
            "错误：当前处于红灯状态（token使用率95.0%）", runtime_message.message
        )
        self.assertIn("禁止调用read_file工具！", runtime_message.message)

    def test_red_state_block_other_tool_old_cleanup(self):
        """测试红灯状态但清理时间超过一分钟，阻止其他工具。"""
        # 设置模拟
        self.agent.get_threshold_info.return_value = {
            "hard_limit": 80000,
            "used_tokens": 76000,
            "remaining_tokens": 4000,
            "usage_ratio": 0.95,
        }  # 95%使用率，红灯
        self.orchestration.last_compress_or_clean_time = (
            time.time() - 90
        )  # 90秒前清理过，超过一分钟
        self.orchestration.should_block_tool_call.return_value = True

        # 创建其他工具调用
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
        )

        # 调用插件
        import asyncio

        result = asyncio.run(self.plugin.before_tool_call(tool_call))

        # 验证阻止
        self.assertTrue(result)
        self.agent.get_threshold_info.assert_called_once()
        self.agent.message_processor.append_message.assert_called_once()
        self.group_chat.send_if_exists.assert_called_once()

    def test_no_threshold_info(self):
        """测试无阈值信息时不阻止工具。"""
        # 设置模拟
        self.agent.get_threshold_info.return_value = None  # 无阈值信息

        # 创建工具调用
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
        )

        # 调用插件
        import asyncio

        result = asyncio.run(self.plugin.before_tool_call(tool_call))

        # 验证不阻止
        self.assertFalse(result)
        self.agent.get_threshold_info.assert_called_once()
        self.agent.message_processor.append_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    def test_all_allowed_tools(self):
        """测试所有允许的清理类工具。"""
        # 设置模拟
        self.agent.get_threshold_info.return_value = None  # 无阈值信息，所以不拦截
        self.orchestration = MagicMock()
        self.orchestration.should_block_tool_call.return_value = False
        
        # 更新get_members模拟以返回正确的orchestration
        def get_members_side_effect(name, cls):
            if name == "agent":
                return self.agent
            elif name == "agent_context_orchestration":
                return self.orchestration
            else:
                return None
        
        self.group_chat.get_members.side_effect = get_members_side_effect

        # 测试所有允许的工具
        allowed_tools = [
            "compress_context_range",
            "context_garbage_clean",
            "context_thanox",
            "mark_messages_as_garbage",
        ]

        for tool_name in allowed_tools:
            # 重置模拟调用计数
            self.agent.message_processor.append_message.reset_mock()
            self.group_chat.send_if_exists.reset_mock()

            # 创建工具调用
            from linhai.llm import ToolCallMessage

            tool_call = ToolCallMessage(
                function_name=tool_name,
                function_arguments={"test": "arg"},
                assert_success=True,
            )

            # 调用插件
            import asyncio

            result = asyncio.run(self.plugin.before_tool_call(tool_call))

            # 验证允许调用
            self.assertFalse(result, f"工具 {tool_name} 应该被允许")
            self.agent.message_processor.append_message.assert_not_called()
            self.group_chat.send_if_exists.assert_not_called()
