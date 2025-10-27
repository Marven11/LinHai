"""测试agent_plugin模块。"""

import unittest
from unittest.mock import AsyncMock, MagicMock
from linhai.agent_plugin import TaskPlanningPlugin


class TestTaskPlanningPlugin(unittest.IsolatedAsyncioTestCase):
    """测试TaskPlanningPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.plugin = TaskPlanningPlugin()
        self.agent = MagicMock()
        self.answer = MagicMock()
        self.answer.get_reasoning_message = MagicMock(return_value=None)
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )

    async def test_after_message_generation_with_task_planning(self):
        """测试有任务规划标记的情况。"""
        full_response = """当前任务规划

- [ ] 任务1
- [x] 任务2
- [ ] 任务3"""
        
        self.agent.messages = []
        
        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response, self.tool_calls
        )
        
        # 有任务规划标记，不应该添加警告消息
        self.assertEqual(len(self.agent.messages), 0)

    async def test_after_message_generation_without_task_planning(self):
        """测试没有任务规划标记的情况。"""
        full_response = """当前任务

任务1
任务2
任务3"""
        
        self.agent.messages = []
        
        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response, self.tool_calls
        )
        
        # 没有任务规划标记，应该添加警告消息
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIn("你没有输出任务规划", self.agent.messages[0].message)

    async def test_after_message_generation_with_long_content(self):
        """测试长内容中的任务规划检查。"""
        # 创建一个长内容，确保超过8000字符
        long_content = "任务描述" + "x" * 8000
        
        self.agent.messages = []
        
        await self.plugin.after_message_generation(
            self.agent, self.answer, long_content, self.tool_calls
        )
        
        # 长内容中没有任务规划标记，应该添加警告消息
        self.assertEqual(len(self.agent.messages), 1)


if __name__ == "__main__":
    unittest.main()