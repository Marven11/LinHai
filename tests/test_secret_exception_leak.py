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

from linhai.secret import SecretInterceptorPlugin, load_secrets_from_config
from linhai.tool.main import ToolManager
from linhai.registry import Registry
from linhai.tool.base import ToolSet, ToolResultFailed
from linhai.llm import ToolCallMessage
from linhai.agent.base import RuntimeMessage


class TestSecretExceptionLeak(unittest.TestCase):
    """测试工具抛出异常时的secret泄漏问题"""

    def setUp(self):
        """设置测试环境"""
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

        self.mock_registry = Mock(spec=Registry)
        self.mock_registry.get_member_typechecked = Mock()

        self.mock_tool_manager = Mock(spec=ToolManager)
        self.mock_registry.get_member_typechecked.return_value = self.mock_tool_manager

        self.secret_plugin = SecretInterceptorPlugin(
            self.mock_registry, self.secrets_dict
        )

        self.test_toolset = ToolSet()

        @self.test_toolset.register_tool(
            name="failing_tool_with_secret",
            desc="A tool that fails and potentially leaks secrets",
            args={"param": {"desc": "Parameter", "type": "str"}},
            required_args=["param"],
        )
        def failing_tool_with_secret(param: str):
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
            raise ValueError(f"Tool failed with parameter: {param}")

        self.mock_tool_manager.toolsets = [self.test_toolset]
        self.mock_tool_manager.has_tool = lambda name: name in [
            "failing_tool_with_secret",
            "failing_tool_without_secret",
        ]
        self.mock_tool_manager.get_tool = lambda name: self.test_toolset.get_tool(name)

        self.temp_dir = Path("/tmp/test_secret_leak")
        self.temp_dir.mkdir(exist_ok=True)

        secret_dir = self.temp_dir / "secret_intercepted"
        secret_dir.mkdir(parents=True, exist_ok=True)

        def get_member_typechecked(name, _type=None):
            if name == "conversation_folder":
                return self.temp_dir
            raise ValueError(f"Member {name} not found")

        self.mock_registry.get_member_typechecked = get_member_typechecked

    def tearDown(self):
        """清理测试环境"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_tool_exception_leaks_secret_without_with_secret(self):
        """测试工具抛出异常时，如果没有指定with_secret，是否会泄漏secret"""
        tool_call = ToolCallMessage(
            function_name="failing_tool_with_secret",
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

        async def run_test():
            result = await self.mock_tool_manager.process_tool_call(tool_call, 1)
            result_content = result.get_content()

            self.assertIn(
                "super-secret-password-123",
                result_content,
                "异常信息应该包含secret值（当前存在泄漏问题）",
            )

            message = RuntimeMessage(result_content)

            plugin_result = await self.secret_plugin.after_toolcall(
                tool_name="failing_tool_with_secret",
                tool_index=1,
                status="failed",
                message=message,
                toolcall_arguments=tool_call.function_arguments,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )

            self.assertIsNotNone(
                plugin_result,
                "secret插件应该拦截包含secret的结果（没有指定with_secret）",
            )
            plugin_result_str = str(plugin_result)
            self.assertIn("本插件拦截", plugin_result_str, "应该显示拦截消息")
            self.assertNotIn(
                "super-secret-password-123",
                plugin_result_str,
                "拦截后的消息不应该包含secret值",
            )

        asyncio.run(run_test())

    def test_tool_exception_masked_with_with_secret(self):
        """测试工具抛出异常时，如果指定了with_secret，secret是否被正确掩码"""
        tool_call = ToolCallMessage(
            function_name="failing_tool_with_secret",
            function_arguments={"param": "test_value"},
            assert_success=False,
            with_secret=["TEST_SECRET"],
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

        async def run_test():
            result = await self.mock_tool_manager.process_tool_call(tool_call, 1)
            result_content = result.get_content()

            self.assertIn(
                "super-secret-password-123",
                result_content,
                "异常信息应该包含secret值（当前存在泄漏问题）",
            )

            message = RuntimeMessage(result_content)

            plugin_result = await self.secret_plugin.after_toolcall(
                tool_name="failing_tool_with_secret",
                tool_index=1,
                status="failed",
                message=message,
                toolcall_arguments=tool_call.function_arguments,
                with_secret=["TEST_SECRET"],
                is_tool_failed_duplicated_error=False,
            )

            self.assertIsNotNone(
                plugin_result, "secret插件应该处理包含secret的结果（指定了with_secret）"
            )
            plugin_result_str = str(plugin_result)

            self.assertIn("<<masked>>", plugin_result_str, "应该显示掩码标记")
            self.assertIn(
                "<$TEST_SECRET$>", plugin_result_str, "secret值应该被替换为占位符"
            )
            self.assertNotIn(
                "super-secret-password-123",
                plugin_result_str,
                "掩码后的消息不应该包含原始secret值",
            )

        asyncio.run(run_test())

    def test_tool_exception_without_secret_not_intercepted(self):
        """测试工具抛出异常时，如果不包含secret值，不应该被拦截"""
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

        async def run_test():
            result = await self.mock_tool_manager.process_tool_call(tool_call, 1)
            result_content = result.get_content()

            self.assertNotIn(
                "super-secret-password-123",
                result_content,
                "异常信息不应该包含secret值",
            )
            self.assertNotIn(
                "another-secret-value", result_content, "异常信息不应该包含其他secret值"
            )

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

            self.assertIsNone(plugin_result, "不包含secret的结果不应该被拦截")

        asyncio.run(run_test())

    def test_run_tests(self):
        """运行所有异步测试"""
        self.test_tool_exception_leaks_secret_without_with_secret()
        self.test_tool_exception_masked_with_with_secret()
        self.test_tool_exception_without_secret_not_intercepted()


if __name__ == "__main__":
    test = TestSecretExceptionLeak()
    test.setUp()
    test.test_run_tests()
    test.tearDown()
    print("所有测试通过！成功验证了secret泄漏问题。")
