#!/usr/bin/env python3
"""ProcessArgvCheckerPlugin的单元测试"""

import unittest
from unittest.mock import Mock, AsyncMock
from linhai.plugin.security_config import ProcessArgvCheckerPlugin
from linhai.tool.base import FailedToolResult


class TestProcessArgvCheckerPlugin(unittest.IsolatedAsyncioTestCase):
    """ProcessArgvCheckerPlugin测试类"""

    def setUp(self):
        """测试前准备"""
        self.registry = Mock()
        self.plugin = ProcessArgvCheckerPlugin(self.registry)

    def test_initialization(self):
        """测试插件初始化"""
        self.assertEqual(self.plugin.registry, self.registry)
        self.assertTrue(hasattr(ProcessArgvCheckerPlugin, "BASH_OPERATOR_PATTERNS"))
        self.assertIsInstance(ProcessArgvCheckerPlugin.BASH_OPERATOR_PATTERNS, list)
        self.assertGreater(len(ProcessArgvCheckerPlugin.BASH_OPERATOR_PATTERNS), 0)

        sample_patterns = ProcessArgvCheckerPlugin.BASH_OPERATOR_PATTERNS
        self.assertTrue(any(p.search("&&") for p in sample_patterns))
        self.assertTrue(any(p.search("|") for p in sample_patterns))
        self.assertTrue(any(p.search(">") for p in sample_patterns))
        self.assertTrue(any(p.search(";") for p in sample_patterns))

    async def test_before_tool_call_no_argv(self):
        """测试process_create没有argv参数时不处理"""
        toolcall_arguments = {}

        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
        )

        self.assertIsNone(result)

    async def test_before_tool_call_not_process_create(self):
        """测试不是process_create工具时不处理"""
        toolcall_arguments = {"argv": ["echo", "test"]}

        result = await self.plugin.before_tool_call(
            tool_name="other_tool",
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
        )

        self.assertIsNone(result)

    async def test_before_tool_call_clean_argv(self):
        """测试干净的argv参数不产生警告"""
        toolcall_arguments = {"argv": ["echo", "test", "123"]}
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        # 模拟registry.get_member_typechecked返回mock_agent
        from linhai.agent import Agent

        self.plugin.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
        )

        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_before_tool_call_bash_operator(self):
        """测试包含bash操作符的argv参数产生警告"""
        test_cases = [
            (["echo", "test", "&&", "ls"], ["&&"]),
            (["echo", "test", "|", "grep", "hello"], ["|"]),
            (["echo", "test", ">", "output.txt"], [">"]),
            (["ls", ";", "pwd"], [";"]),
            (["ls", "-la", "2>&1"], ["2>&1"]),
            (["echo", "$(pwd)"], ["$("]),
        ]

        for argv, expected_operators in test_cases:
            with self.subTest(argv=argv):
                toolcall_arguments = {"argv": argv}
                mock_agent = Mock()
                mock_agent.message_processor = Mock()
                mock_agent.message_processor.add_new_message = AsyncMock()

                # 模拟registry.get_member_typechecked返回mock_agent
                from linhai.agent import Agent

                self.plugin.registry.get_member_typechecked = Mock(
                    return_value=mock_agent
                )

                result = await self.plugin.before_tool_call(
                    tool_name="process_create",
                    toolcall_arguments=toolcall_arguments,
                    with_secret=None,
                )

                self.assertIsNone(result)  # 不阻止工具调用
                mock_agent.message_processor.add_new_message.assert_called_once()

                # 验证警告消息包含预期的操作符
                call_args = mock_agent.message_processor.add_new_message.call_args
                warning_message = str(call_args[0][0])
                for operator in expected_operators:
                    self.assertIn(operator, warning_message)

                mock_agent.message_processor.reset_mock()

    async def test_before_tool_call_mixed_argv(self):
        """测试混合参数，包含操作符的字符串参数产生警告"""
        toolcall_arguments = {"argv": ["echo", "test", "&&", "ls", ">", "out.txt"]}
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        # 模拟registry.get_member_typechecked返回mock_agent
        from linhai.agent import Agent

        self.plugin.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
        )

        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = mock_agent.message_processor.add_new_message.call_args
        warning_message = str(call_args[0][0])
        # 检查是否报告了多个操作符
        self.assertIn("&&", warning_message)
        self.assertIn(">", warning_message)

    async def test_before_tool_call_no_false_positive_python_semicolon(self):
        """测试Python代码中的分号不应触发警告（issue #1516）"""
        false_positive_cases = [
            [
                "python3",
                "-c",
                "import sqlite3; conn = sqlite3.connect('/path/db.sqlite')",
            ],
            ["python3", "-c", "x = 1; y = 2; print(x + y)"],
            [
                "python3",
                "-c",
                "import os; print(os.getcwd())",
            ],
        ]

        for argv in false_positive_cases:
            with self.subTest(argv=argv):
                toolcall_arguments = {"argv": argv}
                mock_agent = Mock()
                mock_agent.message_processor = Mock()
                mock_agent.message_processor.add_new_message = AsyncMock()
                self.plugin.registry.get_member_typechecked = Mock(
                    return_value=mock_agent
                )

                result = await self.plugin.before_tool_call(
                    tool_name="process_create",
                    toolcall_arguments=toolcall_arguments,
                    with_secret=None,
                )

                self.assertIsNone(result)
                mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_before_tool_call_standalone_semicolon_detected(self):
        """测试独立的分号参数仍然触发警告"""
        toolcall_arguments = {"argv": ["ls", ";", "pwd"]}
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.plugin.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
        )

        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = mock_agent.message_processor.add_new_message.call_args
        warning_message = str(call_args[0][0])
        self.assertIn(";", warning_message)

    async def test_before_tool_call_no_false_positive_compound_operators(self):
        """测试复合操作符不应触发单字符操作符的误报"""
        toolcall_arguments = {"argv": ["echo", "a>>b"]}
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.plugin.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
        )

        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = mock_agent.message_processor.add_new_message.call_args
        warning_message = str(call_args[0][0])
        self.assertIn(">>", warning_message)

    def test_register_method(self):
        """测试插件的register方法"""
        mock_lifecycle = Mock()
        mock_lifecycle.before_tool_call.register = Mock()

        self.plugin.register(mock_lifecycle)

        mock_lifecycle.before_tool_call.register.assert_called_once_with(
            self.plugin.before_tool_call
        )

    async def test_plugin_rejects_non_list_argv(self):
        """测试argv不是列表类型时返回错误"""
        # argv是字符串
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": "ls -lah"},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是列表类型", result.content)

        # argv是数字
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": 123},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是列表类型", result.content)

        # argv是字典
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": {"command": "ls"}},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是列表类型", result.content)

    async def test_plugin_rejects_non_string_elements(self):
        """测试argv包含非字符串元素时返回错误"""
        # argv包含数字
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["ls", 123, "-lah"]},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是字符串类型", result.content)
        self.assertIn("第1个元素", result.content)  # 索引从0开始，123是第1个元素

        # argv包含列表
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["ls", ["-l", "-a"], "-h"]},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是字符串类型", result.content)

        # argv包含字典
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            toolcall_arguments={"argv": ["ls", {"option": "-l"}, "-a"]},
            with_secret=None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是字符串类型", result.content)


if __name__ == "__main__":
    unittest.main()
