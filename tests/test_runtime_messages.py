"""测试运行时消息功能"""

import unittest
import asyncio
from linhai.tool.main import ToolManager
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.llm import ToolCallMessage
from linhai.utils import CliRuntimeNotice
from linhai.group_chat import GroupChat


class TestRuntimeMessages(unittest.IsolatedAsyncioTestCase):
    """测试运行时消息功能"""

    def setUp(self):
        """设置测试环境"""
        self.group_chat = GroupChat()
        # 注册ui_log队列以便ToolManager可以发送运行时消息
        self.group_chat.register_queue("ui_log")

        # 创建一个测试工具集
        self.toolset = ToolSet()

        @self.toolset.register_tool(
            name="test_tool",
            desc="测试工具",
            args={
                "param": ToolArgInfo(desc="测试参数", type="str"),
            },
            required_args=["param"],
        )
        def test_tool(param: str):
            """测试工具"""
            return f"测试结果: {param}"

        @self.toolset.register_tool(
            name="failing_tool",
            desc="会失败的测试工具",
            args={},
            required_args=[],
        )
        def failing_tool():
            """会失败的测试工具"""
            raise ValueError("工具执行失败")

        from linhai.config import ToolConfig
        from pathlib import Path

        self.tool_manager = ToolManager(
            group_chat=self.group_chat,
            toolsets=[self.toolset],
            config=ToolConfig(),
            mcp_config=[],
            mcp_basedir=Path("/tmp"),
        )

    def test_runtime_message_model(self):
        """测试运行时消息数据模型"""
        message = CliRuntimeNotice(level="INFO", content="测试消息")
        self.assertEqual(message.level, "INFO")
        self.assertEqual(message.content, "测试消息")

        message = CliRuntimeNotice(level="WARNING", content="警告消息")
        self.assertEqual(message.level, "WARNING")
        self.assertEqual(message.content, "警告消息")

        message = CliRuntimeNotice(level="ERROR", content="错误消息")
        self.assertEqual(message.level, "ERROR")
        self.assertEqual(message.content, "错误消息")

    async def test_tool_success_sends_runtime_messages(self):
        """测试工具成功执行时发送运行时消息"""
        # 监听运行时消息队列
        received_messages = []

        async def collect_messages():
            try:
                while True:
                    msg = await self.group_chat.receive("ui_log")
                    received_messages.append(msg)
            except asyncio.CancelledError:
                pass

        # 启动消息收集任务
        collector_task = asyncio.create_task(collect_messages())

        # 执行工具调用
        tool_call = ToolCallMessage(
            function_name="test_tool", function_arguments={"param": "test_value"}
        )

        result = await self.tool_manager.process_tool_call(tool_call)

        # 等待消息处理完成
        await asyncio.sleep(0.1)
        collector_task.cancel()

        # 验证发送了正确的运行时消息（成功时发送1条消息）
        self.assertEqual(len(received_messages), 1)

        # 检查执行成功消息
        success_msg = received_messages[0]
        self.assertIsInstance(success_msg, CliRuntimeNotice)
        self.assertEqual(success_msg.level, "INFO")
        self.assertEqual(success_msg.content, "工具执行成功: test_tool")

        # 验证工具执行结果
        self.assertEqual(result.content, "测试结果: test_value")  # type: ignore

    async def test_tool_failure_sends_runtime_messages(self):
        """测试工具执行失败时发送运行时消息"""
        # 监听运行时消息队列
        received_messages = []

        async def collect_messages():
            try:
                while True:
                    msg = await self.group_chat.receive("ui_log")
                    received_messages.append(msg)
            except asyncio.CancelledError:
                pass

        # 启动消息收集任务
        collector_task = asyncio.create_task(collect_messages())

        # 执行会失败的工具调用
        tool_call = ToolCallMessage(function_name="failing_tool", function_arguments={})

        result = await self.tool_manager.process_tool_call(tool_call)

        # 等待消息处理完成
        await asyncio.sleep(0.1)
        collector_task.cancel()

        # 验证发送了正确的运行时消息（现在发送1条消息）
        self.assertEqual(len(received_messages), 1)

        # 检查执行失败消息
        failure_msg = received_messages[0]
        self.assertIsInstance(failure_msg, CliRuntimeNotice)
        self.assertEqual(failure_msg.level, "ERROR")
        self.assertEqual(
            failure_msg.content, "工具执行失败: failing_tool - 工具执行失败"
        )

        # 验证工具执行结果
        self.assertEqual(result.content, "工具执行失败")  # type: ignore

    async def test_tool_not_found_sends_runtime_message(self):
        """测试工具未找到时发送运行时消息"""
        # 监听运行时消息队列
        received_messages = []

        async def collect_messages():
            try:
                while True:
                    msg = await self.group_chat.receive("ui_log")
                    received_messages.append(msg)
            except asyncio.CancelledError:
                pass

        # 启动消息收集任务
        collector_task = asyncio.create_task(collect_messages())

        # 执行不存在的工具调用
        tool_call = ToolCallMessage(
            function_name="nonexistent_tool", function_arguments={}
        )

        result = await self.tool_manager.process_tool_call(tool_call)

        # 等待消息处理完成
        await asyncio.sleep(0.1)
        collector_task.cancel()

        # 验证发送了正确的运行时消息（现在发送1条消息）
        self.assertEqual(len(received_messages), 1)

        # 检查错误消息
        error_msg = received_messages[0]
        self.assertIsInstance(error_msg, CliRuntimeNotice)
        self.assertEqual(error_msg.level, "ERROR")
        self.assertEqual(error_msg.content, "未找到工具: nonexistent_tool")

        # 验证工具执行结果
        self.assertEqual(result.content, "未找到工具: nonexistent_tool")  # type: ignore

    async def test_tool_error_message_sends_failure_notification(self):
        """测试工具返回ToolErrorMessage时发送失败通知"""
        # 监听运行时消息队列
        received_messages = []

        async def collect_messages():
            try:
                while True:
                    msg = await self.group_chat.receive("ui_log")
                    received_messages.append(msg)
            except asyncio.CancelledError:
                pass

        # 启动消息收集任务
        collector_task = asyncio.create_task(collect_messages())

        # 添加一个返回ToolErrorMessage的工具
        from linhai.tool.base import ToolErrorMessage

        @self.toolset.register_tool(
            name="error_tool",
            desc="返回错误消息的工具",
            args={},
            required_args=[],
        )
        def error_tool():
            """返回错误消息的工具"""
            return ToolErrorMessage("工具内部错误")

        # 执行工具调用
        tool_call = ToolCallMessage(function_name="error_tool", function_arguments={})

        result = await self.tool_manager.process_tool_call(tool_call)

        # 等待消息处理完成
        await asyncio.sleep(0.1)
        collector_task.cancel()

        # 验证发送了正确的运行时消息（现在发送1条消息）
        self.assertEqual(len(received_messages), 1)

        # 检查执行失败消息
        failure_msg = received_messages[0]
        self.assertIsInstance(failure_msg, CliRuntimeNotice)
        self.assertEqual(failure_msg.level, "ERROR")
        self.assertEqual(failure_msg.content, "工具执行失败: error_tool")

        # 验证工具执行结果
        self.assertEqual(result.content, "工具内部错误")  # type: ignore


if __name__ == "__main__":
    unittest.main()
