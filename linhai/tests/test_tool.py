import asyncio
import json
import unittest
import unittest.mock
from unittest.mock import patch, AsyncMock, MagicMock

from linhai.tool.main import ToolManager, ToolResultMessage, ToolErrorMessage
from linhai.queue import Queue
from linhai.tool.base import call_tool, register_tool, ToolArgInfo, get_tools_info
from linhai.llm import ToolCallMessage


class TestToolManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool_input_queue = Queue()
        self.tool_output_queue = Queue()
        self.manager = ToolManager(self.tool_input_queue, self.tool_output_queue)

    async def test_successful_tool_call(self):
        """测试成功的工具调用"""
        mock_tool_call = ToolCallMessage(
            function_name="add_numbers", function_arguments=json.dumps({"a": 3, "b": 5})
        )

        # 模拟工具调用
        with unittest.mock.patch(
            "linhai.tool.main.call_tool", return_value=8
        ) as mock_call:
            await self.manager.process_tool_call(mock_tool_call)

            # 验证工具被正确调用
            mock_call.assert_called_once_with("add_numbers", {"a": 3, "b": 5})

            # 验证结果消息
            result = await self.tool_output_queue.get()
            self.assertIsInstance(result, ToolResultMessage)
            self.assertEqual(result.content, "8")

    async def test_failed_tool_call(self):
        """测试失败的工具调用"""
        mock_tool_call = ToolCallMessage(
            function_name="invalid_tool", function_arguments="{}"
        )

        # 模拟工具抛出异常
        with unittest.mock.patch(
            "linhai.tool.main.call_tool", side_effect=ValueError("Tool not found")
        ):
            await self.manager.process_tool_call(mock_tool_call)

            # 验证错误消息
            result = await self.tool_output_queue.get()
            self.assertIsInstance(result, ToolErrorMessage)
            self.assertEqual(result.content, "Tool not found")

    async def test_manager_run_loop(self):
        """测试管理器主循环"""
        mock_tool_call = ToolCallMessage(
            function_name="add_numbers", function_arguments=json.dumps({"a": 2, "b": 3})
        )

        # 启动管理器
        task = asyncio.create_task(self.manager.run())

        # 发送工具调用请求
        await self.tool_input_queue.put(mock_tool_call)

        # 模拟工具调用
        with unittest.mock.patch(
            "linhai.tool.main.call_tool", return_value=5
        ) as mock_call:
            # 验证处理结果
            result = await self.tool_output_queue.get()
            self.assertEqual(result.content, "5")
            mock_call.assert_called_once_with("add_numbers", {"a": 2, "b": 3})

        # 清理
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestToolFunctions(unittest.TestCase):
    def setUp(self):
        # 清空工具注册表
        from linhai.tool.base import tools

        tools.clear()

    def test_register_and_call_tool(self):
        """测试工具注册和调用"""

        # 注册测试工具
        @register_tool(
            name="add_numbers",
            desc="Add two numbers",
            args={
                "a": ToolArgInfo(desc="First number", type=int),
                "b": ToolArgInfo(desc="Second number", type=int),
            },
            required_args=["a", "b"],
        )
        def add_numbers(a, b):
            return a + b

        # 测试工具调用
        result = call_tool("add_numbers", {"a": 2, "b": 3})
        self.assertEqual(result, 5)

    def test_get_tools_info(self):
        """测试获取工具信息"""

        # 注册测试工具
        @register_tool(
            name="multiply_numbers",
            desc="Multiply two numbers",
            args={
                "x": ToolArgInfo(desc="First number", type=int),
                "y": ToolArgInfo(desc="Second number", type=int),
            },
            required_args=["x", "y"],
        )
        def multiply(x, y):
            return x * y

        # 获取工具信息
        tools_info = get_tools_info()
        self.assertEqual(len(tools_info), 1)
        self.assertEqual(tools_info[0]["function"]["name"], "multiply_numbers")
        self.assertEqual(
            tools_info[0]["function"]["description"], "Multiply two numbers"
        )

    def test_tool_not_found(self):
        """测试工具不存在的情况"""
        with self.assertRaises(ValueError) as context:
            call_tool("nonexistent_tool", {})
        self.assertEqual(str(context.exception), "Tool not found: nonexistent_tool")


if __name__ == "__main__":
    unittest.main()
