#!/usr/bin/env python3
"""测试工具抛出异常时的secret泄漏问题 - issue #3

这个测试用于验证当工具抛出Exception而不是返回错误时，是否可能导致secret泄漏。
根据issue #3的要求，这个测试应该捕获到secret泄漏问题。
在issue #4中将会修复这个问题。
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

# 导入必要的模块
from linhai.secret import SecretInterceptorPlugin, load_secrets_from_config
from linhai.tool.main import ToolManager
from linhai.group_chat import GroupChat
from linhai.tool.base import ToolSet, ToolResultFailed
from linhai.llm import ToolCallMessage
from linhai.agent.base import RuntimeMessage


class TestSecretExceptionLeak(unittest.TestCase):
    """测试工具抛出异常时的secret泄漏问题"""

    def setUp(self):
        """设置测试环境"""
        # 创建测试用的secret字典
        self.secrets_dict = {
            "TEST_SECRET": {
                "value": "super-secret-password-123",
                "description": "Test secret for exception leak testing",
                "disabled_in_toolcall_argument": False,
            },
            "ANOTHER_SECRET": {
                "value": "another-secret-value",
                "description": "Another test secret",
                "disabled_in_toolcall_argument": False,
            },
        }

        # 创建模拟的GroupChat
        self.mock_group_chat = Mock(spec=GroupChat)
        self.mock_group_chat.get_member_typechecked = Mock()

        # 创建ToolManager的模拟
        self.mock_tool_manager = Mock(spec=ToolManager)
        self.mock_group_chat.get_member_typechecked.return_value = (
            self.mock_tool_manager
        )

        # 创建secret插件
        self.secret_plugin = SecretInterceptorPlugin(
            self.mock_group_chat, self.secrets_dict
        )

        # 创建测试用的ToolSet和会抛出异常的工具
        self.test_toolset = ToolSet()

        @self.test_toolset.register_tool(
            name="failing_tool_with_secret",
            desc="A tool that fails and potentially leaks secrets",
            args={"param": {"desc": "Parameter", "type": "str"}},
            required_args=["param"],
        )
        def failing_tool_with_secret(param: str):
            """一个会抛出异常的工具，异常信息中包含secret值"""
            # 模拟一个异常，异常信息中包含了secret值
            raise ValueError(
                f"Tool failed with parameter: {param} and secret: super-secret-password-123"
            )

        @self.test_toolset.register_tool(
            name="failing_tool_without_secret",
            desc="A tool that fails without leaking secrets",
            args={"param": {"desc": "Parameter", "type": "str"}},
            required_args=["param"],
        )
        def failing_tool_without_secret(param: str):
            """一个会抛出异常的工具，但异常信息中不包含secret值"""
            raise ValueError(f"Tool failed with parameter: {param}")

        # 设置ToolManager的工具集
        self.mock_tool_manager.toolsets = [self.test_toolset]
        self.mock_tool_manager.has_tool = lambda name: name in [
            "failing_tool_with_secret",
            "failing_tool_without_secret",
        ]
        self.mock_tool_manager.get_tool = lambda name: self.test_toolset.get_tool(name)

        # 模拟conversation_folder - 直接返回Path对象
        self.temp_dir = Path("/tmp/test_secret_leak")
        self.temp_dir.mkdir(exist_ok=True)

        # 确保secret_intercepted目录存在
        secret_dir = self.temp_dir / "secret_intercepted"
        secret_dir.mkdir(parents=True, exist_ok=True)

        def get_member_typechecked(name, _type=None):
            if name == "conversation_folder":
                # 在真实代码中，get_member_typechecked("conversation_folder", Path)返回Path对象
                return self.temp_dir
            raise ValueError(f"Member {name} not found")

        self.mock_group_chat.get_member_typechecked = get_member_typechecked

    def tearDown(self):
        """清理测试环境"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    async def test_tool_exception_leaks_secret_without_with_secret(self):
        """测试工具抛出异常时，如果没有指定with_secret，是否会泄漏secret"""
        # 创建一个会抛出异常的工具调用
        tool_call = ToolCallMessage(
            function_name="failing_tool_with_secret",
            function_arguments={"param": "test_value"},
            assert_success=False,
            with_secret=None,  # 没有指定with_secret
        )

        # 模拟ToolManager.process_tool_call抛出异常
        async def mock_process_tool_call(tool_call_msg, tool_index):
            # 模拟实际抛出异常的情况
            try:
                # 调用实际会抛出异常的工具
                func = self.test_toolset.get_tool(tool_call_msg.function_name)
                func(**tool_call_msg.function_arguments)
            except Exception as e:
                # ToolManager会捕获异常并返回ToolResultFailed
                from linhai.tool.base import ToolCallResultMessage, ToolResultFailed

                return ToolCallResultMessage(
                    tool_name=tool_call_msg.function_name,
                    tool_index=tool_index,
                    result=ToolResultFailed(content=str(e)),
                    toolcall_arguments=tool_call_msg.function_arguments,
                )

        self.mock_tool_manager.process_tool_call = mock_process_tool_call

        # 执行工具调用
        result = await self.mock_tool_manager.process_tool_call(tool_call, 1)

        # 获取结果内容
        result_content = result.get_content()

        # 验证异常信息中是否包含secret值
        # 当前实现中，异常信息会直接包含secret值，这是一个安全问题
        self.assertIn(
            "super-secret-password-123",
            result_content,
            "异常信息应该包含secret值（当前存在泄漏问题）",
        )

        # 现在测试secret插件是否会拦截这个泄漏
        # 创建一个包含结果的消息
        message = RuntimeMessage(result_content)

        # 调用secret插件的after_toolcall方法
        plugin_result = await self.secret_plugin.after_toolcall(
            tool_name="failing_tool_with_secret",
            tool_index=1,
            status="failed",
            message=message,
            toolcall_arguments=tool_call.function_arguments,
            with_secret=None,  # 没有指定with_secret
            is_tool_failed_duplicated_error=False,
        )

        # 验证secret插件是否拦截了包含secret的结果
        # 由于没有指定with_secret，但结果中包含secret，应该被拦截
        self.assertIsNotNone(
            plugin_result, "secret插件应该拦截包含secret的结果（没有指定with_secret）"
        )
        plugin_result_str = str(plugin_result)
        self.assertIn("已拦截", plugin_result_str, "应该显示拦截消息")
        self.assertNotIn(
            "super-secret-password-123",
            plugin_result_str,
            "拦截后的消息不应该包含secret值",
        )

    async def test_tool_exception_masked_with_with_secret(self):
        """测试工具抛出异常时，如果指定了with_secret，secret是否被正确掩码"""
        # 创建一个会抛出异常的工具调用，这次指定with_secret
        tool_call = ToolCallMessage(
            function_name="failing_tool_with_secret",
            function_arguments={"param": "test_value"},
            assert_success=False,
            with_secret=["TEST_SECRET"],  # 指定with_secret
        )

        # 模拟ToolManager.process_tool_call抛出异常
        async def mock_process_tool_call(tool_call_msg, tool_index):
            try:
                func = self.test_toolset.get_tool(tool_call_msg.function_name)
                func(**tool_call_msg.function_arguments)
            except Exception as e:
                from linhai.tool.base import ToolCallResultMessage, ToolResultFailed

                return ToolCallResultMessage(
                    tool_name=tool_call_msg.function_name,
                    tool_index=tool_index,
                    result=ToolResultFailed(content=str(e)),
                    toolcall_arguments=tool_call_msg.function_arguments,
                )

        self.mock_tool_manager.process_tool_call = mock_process_tool_call

        # 执行工具调用
        result = await self.mock_tool_manager.process_tool_call(tool_call, 1)
        result_content = result.get_content()

        # 验证异常信息中是否包含原始secret值
        self.assertIn(
            "super-secret-password-123",
            result_content,
            "异常信息应该包含secret值（当前存在泄漏问题）",
        )

        # 现在测试secret插件是否会掩码这个结果
        message = RuntimeMessage(result_content)

        plugin_result = await self.secret_plugin.after_toolcall(
            tool_name="failing_tool_with_secret",
            tool_index=1,
            status="failed",
            message=message,
            toolcall_arguments=tool_call.function_arguments,
            with_secret=["TEST_SECRET"],  # 指定了with_secret
            is_tool_failed_duplicated_error=False,
        )

        # 验证secret插件是否正确处理了结果
        self.assertIsNotNone(
            plugin_result, "secret插件应该处理包含secret的结果（指定了with_secret）"
        )
        plugin_result_str = str(plugin_result)

        # 结果应该被掩码，包含<<masked>>标记
        self.assertIn("<<masked>>", plugin_result_str, "应该显示掩码标记")
        # secret值应该被替换为占位符
        self.assertIn(
            "<$TEST_SECRET$>", plugin_result_str, "secret值应该被替换为占位符"
        )
        self.assertNotIn(
            "super-secret-password-123",
            plugin_result_str,
            "掩码后的消息不应该包含原始secret值",
        )

    async def test_tool_exception_without_secret_not_intercepted(self):
        """测试工具抛出异常时，如果不包含secret值，不应该被拦截"""
        # 创建一个不会泄漏secret的工具调用
        tool_call = ToolCallMessage(
            function_name="failing_tool_without_secret",
            function_arguments={"param": "test_value"},
            assert_success=False,
            with_secret=None,
        )

        async def mock_process_tool_call(tool_call_msg, tool_index):
            try:
                func = self.test_toolset.get_tool(tool_call_msg.function_name)
                func(**tool_call_msg.function_arguments)
            except Exception as e:
                from linhai.tool.base import ToolCallResultMessage, ToolResultFailed

                return ToolCallResultMessage(
                    tool_name=tool_call_msg.function_name,
                    tool_index=tool_index,
                    result=ToolResultFailed(content=str(e)),
                    toolcall_arguments=tool_call_msg.function_arguments,
                )

        self.mock_tool_manager.process_tool_call = mock_process_tool_call

        result = await self.mock_tool_manager.process_tool_call(tool_call, 1)
        result_content = result.get_content()

        # 验证异常信息中不包含secret值
        self.assertNotIn(
            "super-secret-password-123", result_content, "异常信息不应该包含secret值"
        )
        self.assertNotIn(
            "another-secret-value", result_content, "异常信息不应该包含其他secret值"
        )

        # 测试secret插件不会拦截这个结果
        message = RuntimeMessage(result_content)

        plugin_result = await self.secret_plugin.after_toolcall(
            tool_name="failing_tool_without_secret",
            tool_index=1,
            status="failed",
            message=message,
            toolcall_arguments=tool_call.function_arguments,
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )

        # 由于不包含secret，不应该被拦截
        self.assertIsNone(plugin_result, "不包含secret的结果不应该被拦截")

    def test_run_tests(self):
        """运行所有异步测试"""
        # 运行所有异步测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(
                self.test_tool_exception_leaks_secret_without_with_secret()
            )
            loop.run_until_complete(self.test_tool_exception_masked_with_with_secret())
            loop.run_until_complete(
                self.test_tool_exception_without_secret_not_intercepted()
            )
        finally:
            loop.close()


if __name__ == "__main__":
    # 为了在命令行中直接运行测试
    test = TestSecretExceptionLeak()
    test.setUp()
    test.test_run_tests()
    test.tearDown()
    print("所有测试通过！成功验证了secret泄漏问题。")
