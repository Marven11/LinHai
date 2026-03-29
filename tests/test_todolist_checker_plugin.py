import unittest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import Mock, MagicMock, AsyncMock

from linhai.plugin.planning import TodolistCheckerPlugin
from linhai.plugin.file_operations import Plugin
from linhai.agent.lifecycle import Lifecycle
from linhai.registry import Registry
from linhai.agent.base import RuntimeMessage
from linhai.llm import UserMessage, Answer
from linhai.agent.planning import PlanningPromptMessage


class TestTodolistCheckerPlugin(unittest.IsolatedAsyncioTestCase):
    """测试TodolistCheckerPlugin插件。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = MagicMock(spec=Registry)
        self.plugin = TodolistCheckerPlugin(self.registry)

        self.temp_dir = Path(tempfile.mkdtemp())
        self.todolist_file = self.temp_dir / "TODOLIST.md"

        self.mock_agent = AsyncMock()
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.message_processor.add_new_message = AsyncMock()
        self.mock_agent.message_processor.get_messages = MagicMock(return_value=[])

        self.mock_planning_message = MagicMock(spec=PlanningPromptMessage)
        self.mock_planning_message.planning_folder = self.temp_dir

        def side_effect(name, cls):
            if name == "agent" and cls.__name__ == "Agent":
                return self.mock_agent
            return None

        self.registry.get_member_typechecked.side_effect = side_effect

    def tearDown(self):
        """清理测试环境。"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_plugin_inherits_from_base_class(self):
        """测试插件继承自Plugin基类。"""
        self.assertIsInstance(self.plugin, Plugin)

    async def test_register_method_adds_callback(self):
        """测试register方法正确注册before_waiting_user回调。"""
        mock_lifecycle = MagicMock(spec=Lifecycle)

        self.plugin.register(mock_lifecycle)

        mock_lifecycle.register_before_waiting_user.assert_called_once_with(
            self.plugin.before_waiting_user
        )

    async def test_no_action_when_no_planning_folder(self):
        """测试没有planning文件夹时不执行任何操作。"""
        self.mock_agent.message_processor.get_messages.return_value = []

        await self.plugin.before_waiting_user(self.mock_agent)

        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_no_action_when_todolist_not_exists(self):
        """测试TODOLIST.md文件不存在时不执行任何操作。"""
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]
        # 确保文件不存在
        if self.todolist_file.exists():
            self.todolist_file.unlink()

        await self.plugin.before_waiting_user(self.mock_agent)

        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_no_error_when_all_tasks_completed(self):
        """测试所有任务都完成时没有错误消息。"""
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        todolist_content = """# 待办任务列表

- [x] 任务1
  - 已完成
- [x] 任务2
  - 已完成
"""
        self.todolist_file.write_text(todolist_content)

        await self.plugin.before_waiting_user(self.mock_agent)

        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_error_when_todo_item_exists(self):
        """测试存在未完成任务时添加错误消息。"""
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        todolist_content = """# 待办任务列表

- [x] 已完成的任务
  - 已完成
- [ ] 未完成的任务
  - 还没做
- [.] 进行中的任务
  - 正在做
"""
        self.todolist_file.write_text(todolist_content)

        await self.plugin.before_waiting_user(self.mock_agent)

        self.mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = self.mock_agent.message_processor.add_new_message.call_args[0][0]
        self.assertIsInstance(call_args, RuntimeMessage)
        self.assertIn("错误", str(call_args))

    async def test_error_when_dot_task_exists(self):
        """测试存在进行中任务时添加错误消息。"""
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        todolist_content = """# 待办任务列表

- [x] 已完成的任务
- [.] 进行中的任务
"""
        self.todolist_file.write_text(todolist_content)

        await self.plugin.before_waiting_user(self.mock_agent)

        self.mock_agent.message_processor.add_new_message.assert_called_once()

    async def test_error_when_space_task_exists(self):
        """测试存在空格任务时添加错误消息。"""
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        todolist_content = """# 待办任务列表

- [x] 已完成
- [ ] 未完成
"""
        self.todolist_file.write_text(todolist_content)

        await self.plugin.before_waiting_user(self.mock_agent)

        self.mock_agent.message_processor.add_new_message.assert_called_once()

    async def test_handles_file_read_error_gracefully(self):
        """测试文件读取错误时优雅处理。"""
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        # 创建TODOLIST.md文件
        self.todolist_file.write_text("test")
        # 设置读取权限，使读取失败
        self.todolist_file.chmod(0o000)

        try:
            await self.plugin.before_waiting_user(self.mock_agent)
            # 不应该崩溃
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"插件抛出了异常: {e}")
        finally:
            # 恢复权限以便清理
            self.todolist_file.chmod(0o644)

        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_mixed_tasks_with_indentation(self):
        """测试混合任务和缩进的情况。"""
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        todolist_content = """# 待办任务列表

- [x] 已完成的任务
  - 子任务1
  - 子任务2
- [ ] 未完成的任务
  - [x] 子任务已完成
  - [ ] 子任务未完成
- [.] 进行中的任务
  - 正在进行
"""
        self.todolist_file.write_text(todolist_content)

        await self.plugin.before_waiting_user(self.mock_agent)

        self.mock_agent.message_processor.add_new_message.assert_called_once()

    async def test_empty_todolist(self):
        """测试空的TODOLIST.md文件。"""
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        self.todolist_file.write_text("")

        await self.plugin.before_waiting_user(self.mock_agent)

        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_todolist_with_only_comments(self):
        """测试只有注释的TODOLIST.md文件。"""
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        todolist_content = """# 待办任务列表

<!-- 这是一个注释 -->
<!-- 另一个注释 -->
"""
        self.todolist_file.write_text(todolist_content)

        await self.plugin.before_waiting_user(self.mock_agent)

        self.mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_todolist_with_markdown_formatting(self):
        """测试包含markdown格式的TODOLIST.md文件。"""
        self.mock_agent.message_processor.get_messages.return_value = [
            self.mock_planning_message
        ]

        todolist_content = """# 待办任务列表

**重要任务**:
- [x] 已完成的重要任务
- [ ] *未完成的强调任务*

普通任务:
1. [x] 第一个任务
2. [.] 第二个任务
3. [ ] 第三个任务

> 引用块中的任务不算
> - [ ] 这个不应该被统计
"""
        self.todolist_file.write_text(todolist_content)

        await self.plugin.before_waiting_user(self.mock_agent)

        self.mock_agent.message_processor.add_new_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
