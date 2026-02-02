#!/usr/bin/env python3
"""ProcessArgvCheckerPlugin的单元测试"""

import unittest
from unittest.mock import Mock, AsyncMock
from linhai.plugin.security_config import ProcessArgvCheckerPlugin


class TestProcessArgvCheckerPlugin(unittest.IsolatedAsyncioTestCase):
    """ProcessArgvCheckerPlugin测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.group_chat = Mock()
        self.plugin = ProcessArgvCheckerPlugin(self.group_chat)
    
    def test_initialization(self):
        """测试插件初始化"""
        self.assertEqual(self.plugin.group_chat, self.group_chat)
        self.assertTrue(hasattr(ProcessArgvCheckerPlugin, 'BASH_OPERATORS'))
        self.assertIsInstance(ProcessArgvCheckerPlugin.BASH_OPERATORS, list)
        self.assertGreater(len(ProcessArgvCheckerPlugin.BASH_OPERATORS), 0)
        
        # 检查是否包含常见的bash操作符
        self.assertIn('&&', ProcessArgvCheckerPlugin.BASH_OPERATORS)
        self.assertIn('|', ProcessArgvCheckerPlugin.BASH_OPERATORS)
        self.assertIn('>', ProcessArgvCheckerPlugin.BASH_OPERATORS)
        self.assertIn(';', ProcessArgvCheckerPlugin.BASH_OPERATORS)
    
    async def test_before_tool_call_no_argv(self):
        """测试process_create没有argv参数时不处理"""
        toolcall_arguments = {}
        
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            tool_index=0,
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
            agent=Mock(),
            context=Mock(),
        )
        
        self.assertIsNone(result)
    
    async def test_before_tool_call_not_process_create(self):
        """测试不是process_create工具时不处理"""
        toolcall_arguments = {"argv": ["echo", "test"]}
        
        result = await self.plugin.before_tool_call(
            tool_name="other_tool",
            tool_index=0,
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
            agent=Mock(),
            context=Mock(),
        )
        
        self.assertIsNone(result)
    
    async def test_before_tool_call_clean_argv(self):
        """测试干净的argv参数不产生警告"""
        toolcall_arguments = {"argv": ["echo", "test", "123"]}
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            tool_index=0,
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
            agent=mock_agent,
            context=Mock(),
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
                
                result = await self.plugin.before_tool_call(
                    tool_name="process_create",
                    tool_index=0,
                    toolcall_arguments=toolcall_arguments,
                    with_secret=None,
                    agent=mock_agent,
                    context=Mock(),
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
        
        result = await self.plugin.before_tool_call(
            tool_name="process_create",
            tool_index=0,
            toolcall_arguments=toolcall_arguments,
            with_secret=None,
            agent=mock_agent,
            context=Mock(),
        )
        
        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = mock_agent.message_processor.add_new_message.call_args
        warning_message = str(call_args[0][0])
        # 检查是否报告了多个操作符
        self.assertIn("&&", warning_message)
        self.assertIn(">", warning_message)
    
    def test_register_method(self):
        """测试插件的register方法"""
        mock_lifecycle = Mock()
        mock_lifecycle.register_before_tool_call = Mock()
        
        self.plugin.register(mock_lifecycle)
        
        mock_lifecycle.register_before_tool_call.assert_called_once_with(
            self.plugin.before_tool_call
        )


if __name__ == "__main__":
    unittest.main()