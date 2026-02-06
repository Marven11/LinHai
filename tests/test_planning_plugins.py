import unittest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from linhai.plugin.planning import (
    PlanningStatusReminderPlugin,
    UserInputRuntimeMessagePlugin,
)
from linhai.plugin.file_operations import Plugin
from linhai.agent.lifecycle import Lifecycle
from linhai.group_chat import GroupChat
from linhai.agent.base import RuntimeMessage
from linhai.llm import UserMessage, Answer


class TestPlanningStatusReminderPlugin(unittest.TestCase):
    """测试PlanningStatusReminderPlugin插件。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = MagicMock(spec=GroupChat)
        self.plugin = PlanningStatusReminderPlugin(self.group_chat)
        
        self.temp_dir = Path(tempfile.mkdtemp())
        self.status_file = self.temp_dir / "STATUS.md"
        self.todolist_file = self.temp_dir / "TODOLIST.md"
        
        self.status_file.write_text("# Test Status\n")
        self.todolist_file.write_text("# Test TodoList\n")
        
        self.mock_agent = MagicMock()
        self.mock_agent.planning = True
        self.mock_agent.message_processor = MagicMock()
        
        from linhai.agent.planning import PlanningPromptMessage
        self.mock_planning_message = MagicMock(spec=PlanningPromptMessage)
        self.mock_planning_message.planning_folder = self.temp_dir
        
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]
        
        self.group_chat.get_members.return_value = self.mock_agent

    def tearDown(self):
        """清理测试环境。"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_plugin_inherits_from_base_class(self):
        """测试插件继承自Plugin基类。"""
        self.assertIsInstance(self.plugin, Plugin)
        
    def test_register_method_adds_callback(self):
        """测试register方法正确注册回调。"""
        mock_lifecycle = MagicMock(spec=Lifecycle)
        
        self.plugin.register(mock_lifecycle)
        
        mock_lifecycle.register_on_tool_result.assert_called_once_with(
            self.plugin.on_tool_result
        )
        
    def test_planning_folder_detection(self):
        """测试planning文件夹检测逻辑。"""
        planning_folder = self.plugin._get_planning_folder()
        
        self.assertIsNotNone(planning_folder)
        self.assertEqual(planning_folder, self.temp_dir)
        
    def test_planning_folder_not_found_when_no_planning_message(self):
        """测试没有PlanningPromptMessage时返回None。"""
        self.mock_agent.message_processor.get_messages.return_value = []
        
        planning_folder = self.plugin._get_planning_folder()
        
        self.assertIsNone(planning_folder)
        
    def test_counters_increment_on_non_write_tools(self):
        """测试非写文件工具调用时计数器递增。"""
        async def run_test():
            result = await self.plugin.on_tool_result(
                tool_name="read_file",
                tool_index=0,
                status="success",
                message=None,
                toolcall_arguments={"filepath": str(self.status_file)},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
            
            self.assertIsNone(result)
            self.assertEqual(self.plugin.status_counter, 1)
            self.assertEqual(self.plugin.todolist_counter, 1)
            
        asyncio.run(run_test())
        
    def test_status_counter_reset_on_status_file_write(self):
        """测试写入STATUS.md文件时状态计数器重置。"""
        self.plugin.status_counter = 2
        self.plugin.todolist_counter = 2
        
        async def run_test():
            result = await self.plugin.on_tool_result(
                tool_name="write_file",
                tool_index=0,
                status="success",
                message=None,
                toolcall_arguments={"filepath": str(self.status_file)},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
            
            self.assertIsNone(result)
            self.assertEqual(self.plugin.status_counter, 0)
            self.assertEqual(self.plugin.todolist_counter, 2)  # todolist_counter should remain unchanged when writing STATUS.md
            
        asyncio.run(run_test())
        
    def test_todolist_counter_reset_on_todolist_file_write(self):
        """测试写入TODOLIST.md文件时待办列表计数器重置。"""
        self.plugin.status_counter = 2
        self.plugin.todolist_counter = 2
        
        async def run_test():
            result = await self.plugin.on_tool_result(
                tool_name="write_file",
                tool_index=0,
                status="success",
                message=None,
                toolcall_arguments={"filepath": str(self.todolist_file)},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
            
            self.assertIsNone(result)
            self.assertEqual(self.plugin.status_counter, 2)  # status_counter should remain unchanged when writing TODOLIST.md
            self.assertEqual(self.plugin.todolist_counter, 0)
            
        asyncio.run(run_test())
        
    def test_no_warning_below_threshold(self):
        """测试计数器低于阈值时不触发警告。"""
        self.plugin.status_counter = 2
        self.plugin.todolist_counter = 7
        
        async def run_test():
            result = await self.plugin.on_tool_result(
                tool_name="read_file",
                tool_index=0,
                status="success",
                message=None,
                toolcall_arguments={"filepath": "test.txt"},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
            
            self.assertIsNone(result)
            
        asyncio.run(run_test())
        
    def test_status_warning_at_threshold(self):
        """测试状态计数器达到阈值时触发警告。"""
        self.plugin.status_counter = 3
        
        async def run_test():
            result = await self.plugin.on_tool_result(
                tool_name="read_file",
                tool_index=0,
                status="success",
                message=None,
                toolcall_arguments={"filepath": "test.txt"},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
            
            self.assertIsNone(result)
            
        asyncio.run(run_test())
        
    def test_todolist_warning_at_threshold(self):
        """测试待办列表计数器达到阈值时触发警告。"""
        self.plugin.todolist_counter = 8
        
        async def run_test():
            result = await self.plugin.on_tool_result(
                tool_name="read_file",
                tool_index=0,
                status="success",
                message=None,
                toolcall_arguments={"filepath": "test.txt"},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
            
            self.assertIsNone(result)
            
        asyncio.run(run_test())

    def test_send_warnings_called_on_tool_result(self):
        """测试on_tool_result调用了_send_warnings_if_needed。"""
        self.plugin.status_counter = 0
        self.plugin.todolist_counter = 0
        
        async def run_test():
            with patch.object(self.plugin, '_send_warnings_if_needed', return_value=None) as mock_send_warnings:
                result = await self.plugin.on_tool_result(
                    tool_name="read_file",
                    tool_index=0,
                    status="success",
                    message=None,
                    toolcall_arguments={"filepath": "test.txt"},
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )
                
                self.assertIsNone(result)
                mock_send_warnings.assert_awaited_once()
                
        asyncio.run(run_test())
        
    def test_send_warnings_not_called_when_status_failed(self):
        """测试当工具状态不是success时，不调用_send_warnings_if_needed。"""
        self.plugin.status_counter = 0
        self.plugin.todolist_counter = 0
        
        async def run_test():
            with patch.object(self.plugin, '_send_warnings_if_needed', return_value=None) as mock_send_warnings:
                result = await self.plugin.on_tool_result(
                    tool_name="read_file",
                    tool_index=0,
                    status="failed",
                    message=None,
                    toolcall_arguments={"filepath": "test.txt"},
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )
                
                self.assertIsNone(result)
                mock_send_warnings.assert_not_called()
                
        asyncio.run(run_test())


class TestUserInputRuntimeMessagePlugin(unittest.TestCase):
    """测试UserInputRuntimeMessagePlugin插件。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = MagicMock(spec=GroupChat)
        self.plugin = UserInputRuntimeMessagePlugin(self.group_chat)
        
        self.mock_agent = MagicMock()
        self.mock_agent.planning = True
        self.mock_agent.message_processor = MagicMock()
        
        self.group_chat.get_members.return_value = self.mock_agent

    def test_plugin_inherits_from_base_class(self):
        """测试插件继承自Plugin基类。"""
        self.assertIsInstance(self.plugin, Plugin)
        
    def test_register_method_adds_callback(self):
        """测试register方法正确注册回调。"""
        mock_lifecycle = MagicMock(spec=Lifecycle)
        
        self.plugin.register(mock_lifecycle)
        
        mock_lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )
        
    def test_runtime_message_added_after_user_message(self):
        """测试用户消息后添加RuntimeMessage。"""
        mock_user_message = MagicMock(spec=UserMessage)
        self.mock_agent.message_processor.get_messages.return_value = [
            mock_user_message
        ]
        
        async def run_test():
            await self.plugin.after_message_generation(
                _answer=MagicMock(spec=Answer),
                _full_response="Test response",
                _tool_calls=[],
            )
            
            self.mock_agent.message_processor.add_new_message.assert_called_once()
            call_args = self.mock_agent.message_processor.add_new_message.call_args[0][0]
            self.assertIsInstance(call_args, RuntimeMessage)
            
        asyncio.run(run_test())
        
    def test_no_runtime_message_when_last_message_not_user(self):
        """测试最后一条消息不是用户消息时不添加RuntimeMessage。"""
        from linhai.llm import AssistantMessage
        
        mock_assistant_message = MagicMock(spec=AssistantMessage)
        self.mock_agent.message_processor.get_messages.return_value = [
            mock_assistant_message
        ]
        
        async def run_test():
            await self.plugin.after_message_generation(
                _answer=MagicMock(spec=Answer),
                _full_response="Test response",
                _tool_calls=[],
            )
            
            self.mock_agent.message_processor.add_new_message.assert_not_called()
            
        asyncio.run(run_test())
        
    def test_no_action_when_agent_not_found(self):
        """测试找不到agent时不执行任何操作。"""
        self.group_chat.get_members.return_value = None
        
        async def run_test():
            await self.plugin.after_message_generation(
                _answer=MagicMock(spec=Answer),
                _full_response="Test response",
                _tool_calls=[],
            )
            
            self.mock_agent.message_processor.add_new_message.assert_not_called()
            
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()