"""测试agent_plugin模块。"""

import unittest
import time
from unittest.mock import MagicMock, AsyncMock
from linhai.plugin import (
    WeirdTokenPlugin,
    DirectoryChangePlugin,
    PromptFastAgentPlugin,
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
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.group_chat = MagicMock()
        self.agent.group_chat.send = AsyncMock()
        self.agent.agent_llm = AsyncMock(
            side_effect=lambda msg=None: self.agent.message_processor.add_new_message(
                RuntimeMessage(msg or "Agent被插件打断")
            )
        )  # 添加interrupt mock并模拟添加消息
        self.agent.get_current_model = MagicMock()
        self.group_chat = MagicMock()
        self.group_chat.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )
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
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.group_chat = MagicMock()
        self.agent.group_chat.send = AsyncMock()

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertFalse(result)
        self.agent.agent_llm.interrupt.assert_not_called()
        self.assertTrue(self.agent.message_processor.add_new_message.called)
        call_args = self.agent.message_processor.add_new_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn("结束标记", call_args[0].message)


class TestDirectoryChangePlugin(unittest.IsolatedAsyncioTestCase):
    """测试DirectoryChangePlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.context = {"enable_directory_change_detection": False}  # 默认关闭
        self.group_chat = MagicMock()
        self.group_chat.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )
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

        await self.plugin.before_message_generation()

        self.assertIsNotNone(self.plugin.last_directory)

    async def test_before_message_generation_enabled_no_change(self):
        """测试目录更改检测开启但目录未更改的情况。"""
        self.agent.context["enable_directory_change_detection"] = True

        current_dir = pathlib.Path.cwd()
        self.plugin.last_directory = current_dir

        await self.plugin.before_message_generation()

        self.assertEqual(len(self.agent.message_processor.get_messages()), 0)

    async def test_before_message_generation_enabled_with_change(self):
        """测试目录更改检测开启且目录更改的情况。"""
        self.agent.context["enable_directory_change_detection"] = True

        self.plugin.last_directory = pathlib.Path("/old/path")

        current_dir = pathlib.Path.cwd()

        await self.plugin.before_message_generation()

        self.assertEqual(self.plugin.last_directory, current_dir)

    async def test_before_message_generation_no_duplicate_pathprompt(self):
        """测试避免重复添加相同路径的PathPrompt。"""
        self.agent.context["enable_directory_change_detection"] = True

        self.plugin.last_directory = pathlib.Path("/old/path")

        from linhai.agent.base import PathPrompt

        existing_pathprompt = PathPrompt(pathlib.Path.cwd() / "AGENTS.md")
        self.agent.message_processor.get_messages.return_value = [existing_pathprompt]

        await self.plugin.before_message_generation()


class TestSingleToolCallReminderPlugin(unittest.IsolatedAsyncioTestCase):
    """测试SingleToolCallReminderPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = AsyncMock()
        self.group_chat = MagicMock()
        self.group_chat.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )
        from linhai.plugin import SingleToolCallReminderPlugin

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
        self.agent.message_processor.update_notification_message = MagicMock()

        for _ in range(5):
            await self.plugin.after_message_generation(
                self.answer, full_response, tool_calls
            )

        self.assertEqual(self.plugin.single_tool_call_count, 5)
        call_args_list = (
            self.agent.message_processor.update_notification_message.call_args_list
        )
        last_call_args = call_args_list[-1]
        self.assertIsInstance(last_call_args[0][0], RuntimeMessage)
        self.assertIn("连续5次仅调用一个工具", last_call_args[0][0].message)
        self.assertEqual(last_call_args[1]["source"], "single_tool_call_reminder")

    async def test_after_message_generation_with_multiple_tool_calls(self):
        """测试调用多个工具时重置计数器。"""
        full_response = "一些内容"

        self.agent.message_processor.update_notification_message = MagicMock()

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

        last_call_args = (
            self.agent.message_processor.update_notification_message.call_args
        )
        self.assertEqual(last_call_args[0][0], None)
        self.assertEqual(last_call_args[1]["source"], "single_tool_call_reminder")

    async def test_after_message_generation_with_zero_tool_calls(self):
        """测试没有调用工具时重置计数器。"""
        full_response = "一些内容"

        self.agent.message_processor.update_notification_message = MagicMock()

        for _ in range(3):
            await self.plugin.after_message_generation(
                self.answer, full_response, [{"name": "tool1", "arguments": {}}]
            )

        self.assertEqual(self.plugin.single_tool_call_count, 3)

        await self.plugin.after_message_generation(self.answer, full_response, [])

        self.assertEqual(self.plugin.single_tool_call_count, 0)

        last_call_args = (
            self.agent.message_processor.update_notification_message.call_args
        )
        self.assertEqual(last_call_args[0][0], None)
        self.assertEqual(last_call_args[1]["source"], "single_tool_call_reminder")


class TestPromptFastAgentPlugin(unittest.IsolatedAsyncioTestCase):
    """测试PromptFastAgentPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.agent_llm = AsyncMock()
        self.agent.get_current_model = MagicMock()
        self.group_chat = MagicMock()
        self.group_chat.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )
        self.group_chat.send_if_exists = AsyncMock()
        # 模拟配置：minimax模型最多5个工具调用
        self.plugin = PromptFastAgentPlugin(self.group_chat, {"minimax": 5})
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
        mock_model.get_name.return_value = "minimax"  # 使用get_name()而不是name属性
        self.agent.get_current_model = MagicMock(return_value=mock_model)

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

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertFalse(result)

        self.assertTrue(self.agent.message_processor.add_new_message.called)
        call_args = self.agent.message_processor.add_new_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn("禁止超速", call_args[0].message)
        self.assertIn("minimax", call_args[0].message)

        self.answer.truncate.assert_called_once()
        self.agent.agent_llm.interrupt.assert_not_called()


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
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.agent_llm = AsyncMock()  # 设置为AsyncMock
        # 默认阈值信息：绿灯状态
        self.agent.get_threshold_info.return_value = {
            "hard_limit": 80000,
            "used_tokens": 40000,
            "remaining_tokens": 40000,
            "usage_ratio": 0.5,
        }

        # 模拟orchestration
        self.orchestration = MagicMock()
        self.orchestration.last_compress_or_clean_time = None
        self.orchestration.should_block_tool_call = MagicMock(return_value=False)

        # Mock get_tool_block_details返回实际的字典
        def mock_compute_orchestration_context(tool_name, threshold_info):
            if threshold_info is None:
                return {
                    "blocked_category": None,
                    "actual_category": "other",
                    "is_dirty": False,
                    "current_state": "绿灯",
                }

            current_state = "绿灯"
            usage_ratio = threshold_info["usage_ratio"]
            if usage_ratio >= 0.9:
                current_state = "红灯"
            elif usage_ratio >= 0.7:
                current_state = "黄灯"
            elif usage_ratio >= 0.5:
                current_state = "绿灯"

            is_dirty = self.orchestration.last_compress_or_clean_time is not None

            actual_category = (
                "cleanup"
                if tool_name
                in [
                    "context_forget_range_step1",
                    "context_forget_range_step2",
                    "context_forget_large_message",
                ]
                else "other"
            )

            # 根据 should_block_tool_call 的逻辑映射到具体的 blocked_category
            should_block = False
            if is_dirty:
                should_block = actual_category == "cleanup"
            elif current_state == "红灯":
                should_block = actual_category != "cleanup"

            blocked_category = None
            if should_block:
                if current_state == "红灯":
                    if is_dirty and actual_category == "cleanup":
                        blocked_category = "cleanup"
                    else:
                        blocked_category = "other"
                else:
                    blocked_category = "cleanup"

            return {
                "threshold_info": threshold_info,
                "current_state": current_state,
                "is_dirty": is_dirty,
                "notification_message": None,
                "tool_block_details": {
                    "blocked_category": blocked_category,
                    "actual_category": actual_category,
                    "is_dirty": is_dirty,
                    "current_state": current_state,
                },
            }

        self.orchestration.compute_orchestration_context = MagicMock(
            side_effect=mock_compute_orchestration_context
        )

        # 设置group_chat.get_member_typechecked返回值
        def get_member_typechecked_side_effect(name, cls):
            if name == "agent":
                return self.agent
            elif name == "agent_context_orchestration":
                return self.orchestration
            else:
                return None

        self.group_chat.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

    def test_init(self):
        """测试初始化。"""
        self.assertEqual(self.plugin.group_chat, self.group_chat)
        self.assertEqual(
            self.plugin.CLEANUP_TOOLS,
            {
                "context_forget_range_step1",
                "context_forget_range_step2",
                "context_forget_large_message",
            },
        )

    def test_register(self):
        """测试注册插件。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_toolcall.assert_called_once_with(
            self.plugin.after_toolcall
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
            with_secret=None,
        )

        # 调用插件
        import asyncio

        result = asyncio.run(
            self.plugin.after_toolcall(
                tool_name=tool_call.function_name,
                tool_index=0,
                status="skipped",
                message=None,
                toolcall_arguments=tool_call.function_arguments,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )

        # 验证不阻止
        self.assertFalse(result)
        self.agent.get_threshold_info.assert_called_once()
        self.agent.message_processor.add_new_message.assert_not_called()
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
            function_name="context_forget_large_message",  # 替换为现有工具
            function_arguments={"ids": ["test_id"]},
            assert_success=True,
            with_secret=None,
        )

        # 调用插件
        import asyncio

        result = asyncio.run(
            self.plugin.after_toolcall(
                tool_name=tool_call.function_name,
                tool_index=0,
                status="skipped",
                message=None,
                toolcall_arguments=tool_call.function_arguments,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )

        # 验证允许调用
        self.assertFalse(result)
        self.agent.get_threshold_info.assert_called_once()
        self.agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    def test_all_allowed_tools(self):
        """测试所有允许的清理类工具。"""
        # 设置模拟
        self.agent.get_threshold_info.return_value = None  # 无阈值信息，所以不拦截
        self.orchestration = MagicMock()
        self.orchestration.should_block_tool_call.return_value = False

        # 更新get_members模拟以返回正确的orchestration
        def get_member_typechecked_side_effect(name, cls):
            if name == "agent":
                return self.agent
            elif name == "agent_context_orchestration":
                return self.orchestration
            else:
                return None

        self.group_chat.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

        # 测试所有允许的工具
        allowed_tools = [
            "context_forget_range",
            "context_forget_large_message",
        ]

        for tool_name in allowed_tools:
            # 重置模拟调用计数
            self.agent.message_processor.add_new_message.reset_mock()
            self.group_chat.send_if_exists.reset_mock()

            # 创建工具调用
            from linhai.llm import ToolCallMessage

            tool_call = ToolCallMessage(
                function_name=tool_name,
                function_arguments={"test": "arg"},
                assert_success=True,
                with_secret=None,
            )

            # 调用插件
            import asyncio

            result = asyncio.run(
                self.plugin.after_toolcall(
                    tool_name=tool_call.function_name,
                    tool_index=0,
                    status="skipped",
                    message=None,
                    toolcall_arguments=tool_call.function_arguments,
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )
            )

            # 验证允许调用
            self.assertFalse(result, f"工具 {tool_name} 应该被允许")
            self.agent.message_processor.add_new_message.assert_not_called()
            self.group_chat.send_if_exists.assert_not_called()

    def test_red_state_recent_cleanup_block_cleanup_tool(self):
        """测试红灯状态、最近调用过清理工具、调用清理工具时被拦截并显示正确错误消息。"""
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
        self.orchestration.should_block_tool_call.return_value = True  # 应该拦截

        # 创建清理工具调用
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(
            function_name="context_forget_large_message",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )

        # 调用插件
        import asyncio

        result = asyncio.run(
            self.plugin.after_toolcall(
                tool_name=tool_call.function_name,
                tool_index=0,
                status="skipped",
                message=None,
                toolcall_arguments=tool_call.function_arguments,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )

        # 验证阻止
        self.assertTrue(result)
        self.agent.get_threshold_info.assert_called_once()
        self.agent.agent_llm.interrupt.assert_called_once_with(
            "token用量信息已失效，禁止调用context_forget_large_message工具",
            "token用量信息已失效，禁止调用清理工具",
        )

        # 检查错误消息是否包含token用量失效
        interrupt_call = self.agent.agent_llm.interrupt.call_args
        error_msg = interrupt_call[0][0]
        self.assertIn("token用量信息已失效", error_msg)
        self.assertIn("禁止调用context_forget_large_message工具", error_msg)

    def test_red_state_recent_cleanup_allow_other_tool(self):
        """测试红灯状态、最近调用过清理工具、调用其他工具时不被拦截。"""
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
        self.orchestration.should_block_tool_call.return_value = False  # 不应该拦截

        # 创建其他工具调用
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "./test.py"},
            assert_success=True,
            with_secret=None,
        )

        # 调用插件
        import asyncio

        result = asyncio.run(
            self.plugin.after_toolcall(
                tool_name=tool_call.function_name,
                tool_index=0,
                status="skipped",
                message=None,
                toolcall_arguments=tool_call.function_arguments,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )

        # 验证不阻止
        self.assertFalse(result)
        self.agent.get_threshold_info.assert_called_once()
        self.agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()


class TestPreviousReasoningPlugin(unittest.IsolatedAsyncioTestCase):
    """测试PreviousReasoningPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        from linhai.plugin import PreviousReasoningPlugin
        from linhai.llm import AssistantMessage

        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.update_notification_message = MagicMock()
        self.group_chat = MagicMock()
        self.group_chat.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )
        self.plugin = PreviousReasoningPlugin(self.group_chat)
        self.answer = MagicMock()
        self.tool_calls = []

        # 创建一些模拟的AssistantMessage，带有reasoning_message
        self.mock_messages = [
            AssistantMessage(message="msg1", reasoning_message="reasoning1"),
            AssistantMessage(message="msg2", reasoning_message="reasoning2"),
            AssistantMessage(message="msg3", reasoning_message="reasoning3"),
            AssistantMessage(message="msg4", reasoning_message="reasoning4"),
            AssistantMessage(message="msg5", reasoning_message="reasoning5"),
            AssistantMessage(message="msg6", reasoning_message="reasoning6"),
            AssistantMessage(message="msg7", reasoning_message="reasoning7"),
        ]

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )

    async def test_after_message_generation_with_reasoning_messages(self):
        """测试有推理消息时创建SpoofedReasoningMessage。"""
        # 设置模拟消息
        self.agent.message_processor.get_messages.return_value = self.mock_messages

        await self.plugin.after_message_generation(
            self.answer, "full response", self.tool_calls
        )

        # 验证update_notification_message被调用，并且传递了SpoofedReasoningMessage
        self.agent.message_processor.update_notification_message.assert_called_once()
        call_args = self.agent.message_processor.update_notification_message.call_args

        # 检查第一个参数是SpoofedReasoningMessage实例
        message_instance = call_args[0][0]
        self.assertEqual(message_instance.__class__.__name__, "SpoofedReasoningMessage")

        # 检查reasoning_contents包含最近的6个推理消息
        self.assertEqual(len(message_instance.reasoning_contents), 6)
        self.assertEqual(
            message_instance.reasoning_contents,
            [
                "reasoning2",
                "reasoning3",
                "reasoning4",
                "reasoning5",
                "reasoning6",
                "reasoning7",
            ],
        )

        # 检查source和sort_value
        self.assertEqual(call_args[1]["source"], "previous_reasoning")
        self.assertEqual(call_args[1]["sort_value"], 1000)

    async def test_after_message_generation_no_reasoning_messages(self):
        """测试没有推理消息时清除notification message。"""
        # 设置没有推理消息的模拟消息
        messages_without_reasoning = [
            AssistantMessage(message="msg1", reasoning_message=None),
            AssistantMessage(message="msg2", reasoning_message=None),
        ]
        self.agent.message_processor.get_messages.return_value = (
            messages_without_reasoning
        )

        await self.plugin.after_message_generation(
            self.answer, "full response", self.tool_calls
        )

        # 验证update_notification_message被调用，传递None
        self.agent.message_processor.update_notification_message.assert_called_once()
        call_args = self.agent.message_processor.update_notification_message.call_args
        self.assertIsNone(call_args[0][0])
        self.assertEqual(call_args[1]["source"], "previous_reasoning")
        self.assertEqual(call_args[1]["sort_value"], 1000)

    async def test_after_message_generation_spoofed_reasoning_message_format(self):
        """测试SpoofedReasoningMessage的格式符合预期。"""
        from linhai.agent.base import SpoofedReasoningMessage

        # 创建SpoofedReasoningMessage实例
        reasoning_contents = ["reasoning1", "reasoning2", "reasoning3"]
        message = SpoofedReasoningMessage(reasoning_contents)

        # 检查to_llm_message返回的格式
        llm_message = message.to_llm_message()
        self.assertEqual(llm_message["role"], "assistant")
        self.assertEqual(llm_message["content"], "")
        self.assertEqual(
            llm_message["reasoning_content"], "reasoning1\nreasoning2\nreasoning3"
        )


class TestKimiK25ToolCallPlugin(unittest.IsolatedAsyncioTestCase):
    """测试KimiK25ToolCallPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.group_chat = MagicMock()
        self.group_chat.get_member_typechecked = MagicMock(return_value=self.agent)
        self.group_chat.send_if_exists = AsyncMock()
        from linhai.plugin import KimiK25ToolCallPlugin

        self.plugin = KimiK25ToolCallPlugin(self.group_chat)
        self.answer = MagicMock()
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )

    async def test_after_message_generation_with_kimi_format_no_json_toolcall(self):
        """测试检测到kimi特殊格式但没有json toolcall时发送警告。"""
        full_response = '<|tool_calls_section_begin|><|tool_call_begin|>\n{"name": "tool1", "arguments": {}}'

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn("检测到不支持的kimi k2.5特殊工具调用格式", call_args[0].message)
        self.group_chat.send_if_exists.assert_called_once()

    async def test_after_message_generation_with_kimi_format_with_json_toolcall(self):
        """测试检测到kimi特殊格式但已有json toolcall时不警告。"""
        full_response = '<|tool_calls_section_begin|><|tool_call_begin|>\n```json toolcall\n{"name": "tool1", "arguments": {}}\n```'

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    async def test_after_message_generation_without_kimi_format(self):
        """测试没有kimi特殊格式时不处理。"""
        full_response = "正常的工具调用"

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    async def test_after_message_generation_empty_response(self):
        """测试空响应时不处理。"""
        full_response = ""

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    async def test_mixed_kimi_format_with_code_block(self):
        """测试检测到混用格式 - ```<|tool_call_end|> 代码块。"""
        full_response = (
            "正常内容\n"
            "```json toolcall\n"
            '{"name": "tool1", "arguments": {}}\n'
            "```\n"
            "```<|tool_call_end|>\n"
            '{"name": "tool2", "arguments": {}}\n'
            "```"
        )

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(self.agent.message_processor.add_new_message.call_count, 1)
        call_args = self.agent.message_processor.add_new_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn(
            "混用json toolcall和kimi k2.5的特殊工具调用格式", call_args[0].message
        )
        self.assertIn("```<|tool_call_end|>", full_response)
        self.group_chat.send_if_exists.assert_called_once()

    async def test_mixed_kimi_format_with_inline(self):
        """测试检测到混用格式 - }<|tool_call_end|> 行内格式。"""
        full_response = (
            "正常内容\n"
            "```json toolcall\n"
            '{"name": "tool1", "arguments": {}}\n'
            "```\n"
            '<|tool_calls_section_begin|><|tool_call_begin|>{"name": "tool2", "arguments": {}}<|tool_call_end|>'
        )

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(self.agent.message_processor.add_new_message.call_count, 1)
        call_args = self.agent.message_processor.add_new_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn(
            "混用json toolcall和kimi k2.5的特殊工具调用格式", call_args[0].message
        )
        self.group_chat.send_if_exists.assert_called_once()

    async def test_both_kimi_warnings(self):
        """测试同时触发两种kimi格式警告。"""
        full_response = (
            "<|tool_calls_section_begin|><|tool_call_begin|>\n"
            '{"name": "tool1", "arguments": {}}<|tool_call_end|>'
        )

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertEqual(self.agent.message_processor.add_new_message.call_count, 2)
        call_args_list = self.agent.message_processor.add_new_message.call_args_list

        first_msg = call_args_list[0][0][0]
        self.assertIn("检测到不支持的kimi k2.5特殊工具调用格式", first_msg.message)

        second_msg = call_args_list[1][0][0]
        self.assertIn(
            "混用json toolcall和kimi k2.5的特殊工具调用格式", second_msg.message
        )

        self.assertEqual(self.group_chat.send_if_exists.call_count, 2)


class TestMinimaxToolCallPlugin(unittest.IsolatedAsyncioTestCase):
    """测试MinimaxToolCallPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.agent_llm = AsyncMock()
        self.group_chat = MagicMock()
        self.group_chat.get_member_typechecked = MagicMock(return_value=self.agent)
        self.group_chat.send_if_exists = AsyncMock()
        from linhai.plugin import MinimaxToolCallPlugin

        self.plugin = MinimaxToolCallPlugin(self.group_chat)
        self.answer = MagicMock()
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )
        lifecycle.register_after_token_generation.assert_called_once_with(
            self.plugin.after_token_generation
        )

    async def test_after_message_generation_with_minimax_format_no_json_toolcall(self):
        """测试检测到minimax特殊格式但没有json toolcall时设置错误时间。"""
        full_response = '<minimax:tool_call>{"name": "tool1", "arguments": {}}'

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        # 验证设置了错误时间
        self.assertIsNotNone(self.plugin._last_error_format_time)
        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn("检测到不支持的minimax特殊工具调用格式", call_args[0].message)
        self.group_chat.send_if_exists.assert_called_once()

    async def test_after_message_generation_with_minimax_format_with_json_toolcall(
        self,
    ):
        """测试检测到minimax特殊格式但已有json toolcall时不设置错误时间。"""
        full_response = """<minimax:tool_call>```json toolcall
{"name": "tool1", "arguments": {}}
```"""

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        # 验证没有设置错误时间
        self.assertIsNone(self.plugin._last_error_format_time)
        self.agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    async def test_after_message_generation_without_minimax_format(self):
        """测试没有minimax特殊格式时不处理。"""
        full_response = "正常的工具调用"

        await self.plugin.after_message_generation(
            self.answer, full_response, self.tool_calls
        )

        self.assertIsNone(self.plugin._last_error_format_time)
        self.agent.message_processor.add_new_message.assert_not_called()
        self.group_chat.send_if_exists.assert_not_called()

    async def test_after_token_generation_within_time_window(self):
        """测试在时间窗口内检测到minimax格式时打断agent。"""
        # 设置错误时间
        self.plugin._last_error_format_time = time.time()

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, "<minimax:tool_call>some content"
        )

        self.assertTrue(result)
        self.agent.agent_llm.interrupt.assert_called_once()
        interrupt_call = self.agent.agent_llm.interrupt.call_args
        self.assertIn("minimax特殊工具调用格式", interrupt_call[0][0])

    async def test_after_token_generation_time_window_expired(self):
        """测试时间窗口过期后不打断agent。"""
        # 设置过期的错误时间
        self.plugin._last_error_format_time = time.time() - 120

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, "<minimax:tool_call>some content"
        )

        self.assertFalse(result)
        self.agent.agent_llm.interrupt.assert_not_called()

    async def test_after_token_generation_not_first_line(self):
        """测试minimax标记不在第一行时不打断。"""
        self.plugin._last_error_format_time = time.time()

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, "first line\nsecond line <minimax:tool_call>"
        )

        self.assertFalse(result)
        self.agent.agent_llm.interrupt.assert_not_called()
