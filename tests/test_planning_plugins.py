import unittest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from linhai.plugin.planning import (
    PlanningStatusReminderPlugin,
    UserInputRuntimeMessagePlugin,
    DesignMdReminderPlugin,
    PlanningInitOverridePlugin,
    PlanningHeadingCheckPlugin,
    DeepseekTodolistProtectionPlugin,
    BANNED_DELETE_COMMANDS,
    TODOLIST_DELETE_BLOCK_MESSAGE,
)
from linhai.plugin.file_operations import Plugin
from linhai.agent.lifecycle import Lifecycle
from linhai.registry import Registry
from linhai.agent.messages import RuntimeMessage
from linhai.base import UserMessage, Answer
from linhai.tool.base import FailedToolResult


class TestPlanningStatusReminderPlugin(unittest.IsolatedAsyncioTestCase):
    """测试PlanningStatusReminderPlugin插件。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = MagicMock(spec=Registry)
        self.plugin = PlanningStatusReminderPlugin(self.registry)

        self.temp_dir = Path(tempfile.mkdtemp())
        self.planning_dir = self.temp_dir / "planning"
        self.planning_dir.mkdir()
        self.status_file = self.planning_dir / "STATUS.md"
        self.todolist_file = self.planning_dir / "TODOLIST.md"

        self.status_file.write_text("# Test Status\n")
        self.todolist_file.write_text("# Test TodoList\n")

        self.mock_agent = AsyncMock()
        self.mock_agent.planning = True
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.get_threshold_info = MagicMock(
            return_value={"threshold": 1000, "current": 500}
        )

        from linhai.agent.planning import PlanningPromptMessage

        self.mock_planning_message = MagicMock(spec=PlanningPromptMessage)
        self.mock_planning_message.planning_folder = self.planning_dir

        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        self.orchestration = MagicMock()
        self.orchestration.compute_orchestration_context = MagicMock(
            return_value={"current_state": "绿灯"}
        )

        def side_effect(name, cls):
            if name == "agent":
                return self.mock_agent
            elif name == "agent_context_orchestration":
                return self.orchestration
            elif name == "conversation_folder":
                return self.temp_dir
            else:
                return None

        self.registry.get_member_typechecked.side_effect = side_effect

    def tearDown(self):
        """清理测试环境。"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_planning_folder_detection(self):
        """测试planning文件夹检测逻辑。"""
        planning_folder = self.plugin._get_planning_folder()

        self.assertIsNotNone(planning_folder)
        self.assertEqual(planning_folder, self.planning_dir)

    async def test_planning_folder_not_found_when_conversation_folder_missing(self):
        """测试conversation_folder为None时返回None。"""
        # 临时修改side_effect，使conversation_folder返回None
        original_side_effect = self.registry.get_member_typechecked.side_effect

        def new_side_effect(name, cls):
            if name == "conversation_folder":
                return None
            return original_side_effect(name, cls)

        self.registry.get_member_typechecked.side_effect = new_side_effect

        planning_folder = self.plugin._get_planning_folder()

        # 恢复side_effect
        self.registry.get_member_typechecked.side_effect = original_side_effect
        self.assertIsNone(planning_folder)

    async def test_counters_increment_on_non_write_tools(self):
        """测试非写文件工具调用时计数器递增。"""
        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {
                    "name": "read_file",
                    "arguments": {"filepath": str(self.status_file)},
                },
            ],
        )

        self.assertIsNone(result)
        self.assertEqual(self.plugin.status_counter, 1)
        self.assertEqual(self.plugin.todolist_counter, 1)

    async def test_no_increment_when_no_tool_calls(self):
        """测试消息没有工具调用时计数器不递增。"""
        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[],
        )

        self.assertIsNone(result)
        self.assertEqual(self.plugin.status_counter, 0)
        self.assertEqual(self.plugin.todolist_counter, 0)

    async def test_notifications_updated_when_no_tool_calls_red_state(self):
        """测试没有工具调用且处于红灯状态时应该更新通知。"""
        with (
            patch.object(self.plugin, "_get_current_state", return_value="红灯"),
            patch.object(
                self.plugin, "_update_notifications", return_value=None
            ) as mock_update_notifications,
        ):
            result = await self.plugin.after_message_generation(
                parsed_answer=MagicMock(),
                tool_calls=[],
            )

            self.assertIsNone(result)
            mock_update_notifications.assert_awaited_once_with("红灯")
            self.assertEqual(self.plugin.status_counter, 0)
            self.assertEqual(self.plugin.todolist_counter, 0)

    async def test_notifications_based_on_counter_when_no_tool_calls_non_red_state(
        self,
    ):
        """测试没有工具调用且非红灯状态时，根据计数器状态判断提示。"""
        # 测试计数器低于阈值时不显示提示。
        self.plugin.status_counter = 2  # 低于阈值3
        self.plugin.todolist_counter = 7  # 低于阈值8

        with (
            patch.object(self.plugin, "_get_current_state", return_value="绿灯"),
            patch.object(
                self.plugin, "_update_notifications", return_value=None
            ) as mock_update_notifications,
        ):
            result = await self.plugin.after_message_generation(
                parsed_answer=MagicMock(),
                tool_calls=[],
            )

            self.assertIsNone(result)
            mock_update_notifications.assert_awaited_once_with("绿灯")

        # 测试计数器达到阈值时显示提示。
        self.plugin.status_counter = 3  # 达到阈值
        self.plugin.todolist_counter = 8  # 达到阈值

        with (
            patch.object(self.plugin, "_get_current_state", return_value="黄灯"),
            patch.object(
                self.plugin, "_update_notifications", return_value=None
            ) as mock_update_notifications,
        ):
            result = await self.plugin.after_message_generation(
                parsed_answer=MagicMock(),
                tool_calls=[],
            )

            self.assertIsNone(result)
            mock_update_notifications.assert_awaited_once_with("黄灯")

    async def test_status_counter_reset_on_status_file_write(self):
        """测试写入STATUS.md文件时状态计数器重置。"""
        self.plugin.status_counter = 2
        self.plugin.todolist_counter = 2

        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {
                    "name": "write_file",
                    "arguments": {"filepath": str(self.status_file)},
                },
            ],
        )

        self.assertIsNone(result)
        self.assertEqual(self.plugin.status_counter, 0)
        self.assertEqual(
            self.plugin.todolist_counter, 3
        )  # todolist_counter should increment when writing STATUS.md

    async def test_todolist_counter_reset_on_todolist_file_write(self):
        """测试写入TODOLIST.md文件时待办列表计数器重置。"""
        self.plugin.status_counter = 2
        self.plugin.todolist_counter = 2

        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {
                    "name": "write_file",
                    "arguments": {"filepath": str(self.todolist_file)},
                },
            ],
        )

        self.assertIsNone(result)
        self.assertEqual(
            self.plugin.status_counter, 3
        )  # status_counter should increment when writing TODOLIST.md
        self.assertEqual(self.plugin.todolist_counter, 0)

    async def test_no_warning_below_threshold(self):
        """测试计数器低于阈值时不触发警告。"""
        self.plugin.status_counter = 2
        self.plugin.todolist_counter = 7

        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {"name": "read_file", "arguments": {"filepath": "test.txt"}},
            ],
        )

        self.assertIsNone(result)

    async def test_status_warning_at_threshold(self):
        """测试状态计数器达到阈值时触发警告。"""
        self.plugin.status_counter = 3

        with patch.object(
            self.plugin, "_update_notifications", return_value=None
        ) as mock_update_notifications:
            result = await self.plugin.after_message_generation(
                parsed_answer=MagicMock(),
                tool_calls=[
                    {"name": "read_file", "arguments": {"filepath": "test.txt"}},
                ],
            )

            self.assertIsNone(result)
            mock_update_notifications.assert_awaited_once()

    async def test_todolist_warning_at_threshold(self):
        """测试待办列表计数器达到阈值时触发警告。"""
        self.plugin.todolist_counter = 8

        with patch.object(
            self.plugin, "_update_notifications", return_value=None
        ) as mock_update_notifications:
            result = await self.plugin.after_message_generation(
                parsed_answer=MagicMock(),
                tool_calls=[
                    {"name": "read_file", "arguments": {"filepath": "test.txt"}},
                ],
            )

            self.assertIsNone(result)
            mock_update_notifications.assert_awaited_once()

    async def test_mixed_tools_message_with_file_modification(self):
        """测试混合工具调用，其中包含文件修改时计数器清零。"""
        self.plugin.status_counter = 2
        self.plugin.todolist_counter = 2

        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {"name": "read_file", "arguments": {"filepath": "test.txt"}},
                {
                    "name": "write_file",
                    "arguments": {"filepath": str(self.status_file)},
                },
                {"name": "quickjs_calculator", "arguments": {"expression": "1+1"}},
            ],
        )

        self.assertIsNone(result)
        self.assertEqual(self.plugin.status_counter, 0)
        self.assertEqual(
            self.plugin.todolist_counter, 3
        )  # todolist_counter should increment when STATUS.md is modified

    async def test_replace_file_content_tool_resets_counter(self):
        """测试replace_file_content工具也能重置计数器。"""
        self.plugin.status_counter = 2
        self.plugin.todolist_counter = 2

        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {
                    "name": "replace_file_content",
                    "arguments": {
                        "filepath": str(self.status_file),
                        "old": "Test",
                        "new": "Updated",
                    },
                },
            ],
        )

        self.assertIsNone(result)
        self.assertEqual(self.plugin.status_counter, 0)
        self.assertEqual(self.plugin.todolist_counter, 3)

    async def test_notification_message_contains_counter_values(self):
        agent = self.registry.get_member_typechecked("agent", MagicMock)
        self.plugin.status_counter = 4
        self.plugin.todolist_counter = 5

        with patch.object(self.plugin, "_get_current_state", return_value="绿灯"):
            await self.plugin.after_message_generation(
                parsed_answer=MagicMock(),
                tool_calls=[
                    {"name": "read_file", "arguments": {"filepath": "test.txt"}},
                ],
            )

        status_calls = [
            c
            for c in agent.message_processor.update_notification_message.call_args_list
            if c.kwargs.get("source") == "planning_status_reminder"
        ]
        self.assertEqual(len(status_calls), 1)
        status_msg = status_calls[0][0][0]
        self.assertIsNotNone(status_msg)
        self.assertIn("5", status_msg.message)

        todolist_calls = [
            c
            for c in agent.message_processor.update_notification_message.call_args_list
            if c.kwargs.get("source") == "planning_todolist_reminder"
        ]
        self.assertEqual(len(todolist_calls), 1)
        todolist_msg = todolist_calls[0][0][0]
        self.assertIsNotNone(todolist_msg)
        self.assertIn("6", todolist_msg.message)


class TestUserInputRuntimeMessagePlugin(unittest.IsolatedAsyncioTestCase):
    """测试UserInputRuntimeMessagePlugin插件。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = MagicMock(spec=Registry)
        self.plugin = UserInputRuntimeMessagePlugin(self.registry)

        self.mock_agent = AsyncMock()
        self.mock_agent.planning = True
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.message_processor.add_new_message = AsyncMock()
        self.mock_agent.message_processor.get_messages = MagicMock(return_value=[])

        self.registry.get_member_typechecked.return_value = self.mock_agent

    async def test_runtime_message_added_after_user_message(self):
        """测试用户消息后添加RuntimeMessage。"""
        mock_user_message = MagicMock(spec=UserMessage)
        self.mock_agent.message_processor.get_messages.return_value = [
            mock_user_message
        ]

        await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            _tool_calls=[],
        )

        self.mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = self.mock_agent.message_processor.add_new_message.call_args[0][0]
        self.assertIsInstance(call_args, RuntimeMessage)

    async def test_no_runtime_message_when_last_message_not_user(self):
        """测试最后一条消息不是用户消息时不添加RuntimeMessage。"""
        from linhai.base import AssistantMessage

        mock_assistant_message = MagicMock(spec=AssistantMessage)
        self.mock_agent.message_processor.get_messages.return_value = [
            mock_assistant_message
        ]

        await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            _tool_calls=[],
        )

        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_no_action_when_agent_not_found(self):
        """测试找不到agent时不执行任何操作。"""
        self.registry.get_member_typechecked.return_value = None

        await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            _tool_calls=[],
        )

        self.mock_agent.message_processor.add_new_message.assert_not_called()


class TestDesignMdReminderPlugin(unittest.IsolatedAsyncioTestCase):
    """测试DesignMdReminderPlugin插件。"""

    def setUp(self):
        self.registry = MagicMock(spec=Registry)
        self.plugin = DesignMdReminderPlugin(self.registry)

        self.temp_dir = Path(tempfile.mkdtemp())
        self.planning_dir = self.temp_dir / "planning"
        self.planning_dir.mkdir()
        self.design_file = self.planning_dir / "DESIGN.md"
        self.design_file.write_text("# Design\n")

        self.mock_agent = MagicMock()
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.message_processor.add_new_message = AsyncMock()
        self.mock_agent.message_processor.update_notification_message = MagicMock()

        from linhai.agent.planning import PlanningPromptMessage

        self.mock_planning_message = MagicMock(spec=PlanningPromptMessage)
        self.mock_planning_message.planning_folder = self.planning_dir

        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        def side_effect(name, cls):
            if name == "agent":
                return self.mock_agent
            elif name == "conversation_folder":
                return self.temp_dir
            return None

        self.registry.get_member_typechecked.side_effect = side_effect

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_notification_added_after_cache_invalidate_without_design(self):
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        await self.plugin.after_cache_invalidate(self.mock_agent, [])

        self.assertTrue(self.plugin._design_notification_active)
        self.assertFalse(self.plugin._design_reminded)
        self.mock_agent.message_processor.update_notification_message.assert_called_once()
        call_args = (
            self.mock_agent.message_processor.update_notification_message.call_args
        )
        self.assertIsInstance(call_args[0][0], RuntimeMessage)
        self.assertEqual(call_args[1]["source"], "planning_design_reminder")

    async def test_no_notification_when_design_present(self):
        from linhai.tool.base import ToolCallResultMessage, FileContentToolResult

        design_msg = ToolCallResultMessage(
            tool_name="read_file",
            tool_index=0,
            result=FileContentToolResult(
                filepath=str(self.design_file),
                content="# Design\n",
                show_line_numbers=False,
            ),
            toolcall_arguments={},
        )
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message,
            design_msg,
        ]

        await self.plugin.after_cache_invalidate(self.mock_agent, [])

        self.assertFalse(self.plugin._design_notification_active)
        self.mock_agent.message_processor.update_notification_message.assert_not_called()

    async def test_reminder_added_after_design_reread(self):
        self.plugin._design_notification_active = True
        self.plugin._design_reminded = False

        from linhai.tool.base import ToolCallResultMessage, FileContentToolResult

        design_msg = ToolCallResultMessage(
            tool_name="read_file",
            tool_index=0,
            result=FileContentToolResult(
                filepath=str(self.design_file),
                content="# Design\nUpdated\n",
                show_line_numbers=False,
            ),
            toolcall_arguments={},
        )
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message,
            design_msg,
        ]

        await self.plugin.before_message_generation()

        self.assertFalse(self.plugin._design_notification_active)
        self.assertTrue(self.plugin._design_reminded)
        self.mock_agent.message_processor.update_notification_message.assert_called_once_with(
            None, source="planning_design_reminder"
        )
        self.mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = self.mock_agent.message_processor.add_new_message.call_args[0][0]
        self.assertIsInstance(call_args, RuntimeMessage)

    async def test_no_duplicate_reminder(self):
        self.plugin._design_notification_active = True
        self.plugin._design_reminded = True

        from linhai.tool.base import ToolCallResultMessage, FileContentToolResult

        design_msg = ToolCallResultMessage(
            tool_name="read_file",
            tool_index=0,
            result=FileContentToolResult(
                filepath=str(self.design_file),
                content="# Design\nUpdated\n",
                show_line_numbers=False,
            ),
            toolcall_arguments={},
        )
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message,
            design_msg,
        ]

        await self.plugin.before_message_generation()

        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_no_action_when_no_notification_active(self):
        self.plugin._design_notification_active = False

        await self.plugin.before_message_generation()

        self.mock_agent.message_processor.add_new_message.assert_not_called()


class TestPlanningInitOverridePlugin(unittest.IsolatedAsyncioTestCase):
    """测试PlanningInitOverridePlugin插件。"""

    def setUp(self):
        self.registry = MagicMock(spec=Registry)
        self.plugin = PlanningInitOverridePlugin(self.registry)

        self.mock_agent = MagicMock()
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.message_processor.add_new_message = AsyncMock()

    async def test_before_agent_loop_adds_runtime_message(self):
        await self.plugin.before_agent_loop(self.mock_agent)
        self.mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = self.mock_agent.message_processor.add_new_message.call_args[0][0]
        self.assertIsInstance(call_args, RuntimeMessage)
        self.assertIn("override=true", call_args.message)

    async def test_message_content_mentions_planning_files(self):
        await self.plugin.before_agent_loop(self.mock_agent)
        call_args = self.mock_agent.message_processor.add_new_message.call_args[0][0]
        self.assertIn("STATUS.md", call_args.message)
        self.assertIn("TODOLIST.md", call_args.message)
        self.assertIn("DESIGN.md", call_args.message)


class TestPlanningHeadingCheckPlugin(unittest.IsolatedAsyncioTestCase):
    """测试PlanningHeadingCheckPlugin插件。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = MagicMock(spec=Registry)
        self.plugin = PlanningHeadingCheckPlugin(self.registry)

        self.temp_dir = Path(tempfile.mkdtemp())
        self.planning_dir = self.temp_dir / "planning"
        self.planning_dir.mkdir()
        self.status_file = self.planning_dir / "STATUS.md"
        self.todolist_file = self.planning_dir / "TODOLIST.md"
        self.design_file = self.planning_dir / "DESIGN.md"

        self.mock_agent = AsyncMock()
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.message_processor.add_new_message = AsyncMock()

        def side_effect(name, cls):
            if name == "agent":
                return self.mock_agent
            elif name == "conversation_folder":
                return self.temp_dir
            else:
                return None

        self.registry.get_member_typechecked.side_effect = side_effect

    def tearDown(self):
        """清理测试环境。"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_contains_heading_detection(self):
        """测试一级标题检测逻辑。"""
        # 包含一级标题
        content_with_heading = "# 标题\n一些内容"
        self.assertTrue(self.plugin._contains_heading(content_with_heading))

        # 不包含一级标题
        content_without_heading = "## 二级标题\n一些内容"
        self.assertFalse(self.plugin._contains_heading(content_without_heading))

        # 包含以# 开头的行但中间有空格
        content_with_heading_space = "#  标题"
        self.assertTrue(self.plugin._contains_heading(content_with_heading_space))

        # 包含#但后面没有空格
        content_with_hash_no_space = "#标题"
        self.assertFalse(self.plugin._contains_heading(content_with_hash_no_space))

    async def test_planning_folder_detection(self):
        """测试planning文件夹检测逻辑。"""
        planning_folder = self.plugin._get_planning_folder()
        self.assertIsNotNone(planning_folder)
        self.assertEqual(planning_folder, self.planning_dir)

    async def test_no_action_when_no_planning_folder(self):
        """测试没有planning文件夹时不执行操作。"""
        # 使conversation_folder返回None
        self.registry.get_member_typechecked.side_effect = lambda name, cls: None

        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {
                    "name": "write_file",
                    "arguments": {"filepath": str(self.status_file)},
                },
            ],
        )
        self.assertIsNone(result)
        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_no_action_when_not_planning_file(self):
        """测试写入非planning文件时不执行操作。"""
        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {
                    "name": "write_file",
                    "arguments": {"filepath": "/tmp/other.txt"},
                },
            ],
        )
        self.assertIsNone(result)
        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_runtime_message_added_when_heading_detected(self):
        """测试检测到一级标题时添加RuntimeMessage。"""
        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {
                    "name": "write_file",
                    "arguments": {
                        "filepath": str(self.status_file),
                        "content": "# STATUS.md\n一些内容",
                    },
                },
            ],
        )
        self.assertIsNone(result)
        self.mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = self.mock_agent.message_processor.add_new_message.call_args[0][0]
        from linhai.agent.messages import RuntimeMessage

        self.assertIsInstance(call_args, RuntimeMessage)
        self.assertIn("一级标题", call_args.message)
        self.assertIn("STATUS.md", call_args.message)

    async def test_no_runtime_message_when_no_heading(self):
        """测试没有一级标题时不添加RuntimeMessage。"""
        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {
                    "name": "write_file",
                    "arguments": {
                        "filepath": str(self.status_file),
                        "content": "一些内容",
                    },
                },
            ],
        )
        self.assertIsNone(result)
        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_replace_file_content_tool_also_checked(self):
        """测试replace_file_content工具也会被检查。"""
        result = await self.plugin.after_message_generation(
            parsed_answer=MagicMock(),
            tool_calls=[
                {
                    "name": "replace_file_content",
                    "arguments": {
                        "filepath": str(self.status_file),
                        "old": "旧内容",
                        "new": "# 新标题\n新内容",
                    },
                },
            ],
        )
        self.assertIsNone(result)
        self.mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = self.mock_agent.message_processor.add_new_message.call_args[0][0]
        from linhai.agent.messages import RuntimeMessage

        self.assertIsInstance(call_args, RuntimeMessage)
        self.assertIn("一级标题", call_args.message)


if __name__ == "__main__":
    unittest.main()


class TestDeepseekTodolistProtectionPlugin(unittest.IsolatedAsyncioTestCase):
    """测试DeepseekTodolistProtectionPlugin插件。"""

    def setUp(self):
        self.registry = MagicMock(spec=Registry)
        self.plugin = DeepseekTodolistProtectionPlugin(self.registry)

        self.temp_dir = Path(tempfile.mkdtemp())
        self.planning_dir = self.temp_dir / "planning"
        self.planning_dir.mkdir()
        self.todolist_file = self.planning_dir / "TODOLIST.md"
        self.todolist_file.write_text("- [ ] test task\n")

        self.mock_agent = MagicMock()
        self.mock_model = MagicMock()
        self.mock_model.get_compatibility = MagicMock(return_value="deepseek")
        self.mock_agent.get_current_model = MagicMock(return_value=self.mock_model)

        def side_effect(name, cls):
            if name == "agent":
                return self.mock_agent
            elif name == "conversation_folder":
                return self.temp_dir
            return None

        self.registry.get_member_typechecked.side_effect = side_effect

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_blocks_rm_of_todolist_when_deepseek(self):
        result = await self.plugin.before_tool_call(
            "process_create",
            {"argv": ["rm", str(self.todolist_file)]},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        assert isinstance(result, FailedToolResult)
        self.assertIn("不要删除TODOLIST.md", result.content)

    async def test_blocks_trash_of_todolist_when_deepseek(self):
        result = await self.plugin.before_tool_call(
            "process_create",
            {"argv": ["trash", str(self.todolist_file)]},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)

    async def test_blocks_with_extra_flags(self):
        result = await self.plugin.before_tool_call(
            "process_create",
            {"argv": ["rm", "-rf", str(self.todolist_file)]},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)

    async def test_does_not_block_when_not_deepseek(self):
        self.mock_model.get_compatibility.return_value = "kimi"
        result = await self.plugin.before_tool_call(
            "process_create",
            {"argv": ["rm", str(self.todolist_file)]},
            None,
        )
        self.assertIsNone(result)

    async def test_does_not_block_non_delete_command(self):
        result = await self.plugin.before_tool_call(
            "process_create",
            {"argv": ["ls", str(self.todolist_file)]},
            None,
        )
        self.assertIsNone(result)

    async def test_does_not_block_rm_of_other_file(self):
        result = await self.plugin.before_tool_call(
            "process_create",
            {"argv": ["rm", "/tmp/other.txt"]},
            None,
        )
        self.assertIsNone(result)

    async def test_does_not_block_non_process_create(self):
        result = await self.plugin.before_tool_call(
            "write_file",
            {"filepath": str(self.todolist_file), "content": "test"},
            None,
        )
        self.assertIsNone(result)

    async def test_does_not_block_when_no_argv(self):
        result = await self.plugin.before_tool_call(
            "process_create",
            {},
            None,
        )
        self.assertIsNone(result)

    async def test_does_not_block_when_agent_none(self):
        self.registry.get_member_typechecked.side_effect = lambda name, cls: None
        result = await self.plugin.before_tool_call(
            "process_create",
            {"argv": ["rm", str(self.todolist_file)]},
            None,
        )
        self.assertIsNone(result)

    async def test_does_not_block_when_no_conversation_folder(self):
        def side_effect(name, cls):
            if name == "agent":
                return self.mock_agent
            return None

        self.registry.get_member_typechecked.side_effect = side_effect
        result = await self.plugin.before_tool_call(
            "process_create",
            {"argv": ["rm", str(self.todolist_file)]},
            None,
        )
        self.assertIsNone(result)

    async def test_blocks_case_insensitive_tool_name(self):
        result = await self.plugin.before_tool_call(
            "PROCESS_CREATE",
            {"argv": ["rm", str(self.todolist_file)]},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)

    async def test_block_message_matches_issue_spec(self):
        result = await self.plugin.before_tool_call(
            "process_create",
            {"argv": ["rm", str(self.todolist_file)]},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        assert isinstance(result, FailedToolResult)
        self.assertEqual(result.content, TODOLIST_DELETE_BLOCK_MESSAGE)

    def test_banned_delete_commands(self):
        self.assertEqual(BANNED_DELETE_COMMANDS, {"rm", "trash"})
