"""测试SubAgentCollaborationPlugin"""

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from linhai.agent.plugin import SubAgentCollaborationPlugin
from linhai.agent.base import RuntimeMessage
from linhai.llm import ToolCallMessage, Answer
from linhai.utils import CliRuntimeNotice


class TestSubAgentCollaborationPlugin(unittest.IsolatedAsyncioTestCase):
    """测试SubAgentCollaborationPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        
        self.group_chat = MagicMock()
        self.group_chat.get_members = MagicMock(return_value=self.agent)
        self.group_chat.send_if_exists = AsyncMock()
        
        self.plugin = SubAgentCollaborationPlugin(self.group_chat)

    async def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )
        lifecycle.register_after_tool_call.assert_called_once_with(
            self.plugin.after_tool_call
        )

    async def test_after_message_generation(self):
        """测试缓存agent回答。"""
        answer = MagicMock()
        full_response = "测试完整回答"
        tool_calls = []
        
        await self.plugin.after_message_generation(answer, full_response, tool_calls)
        
        assert self.plugin.agent_answer_cache is not None
        self.assertEqual(self.plugin.agent_answer_cache["answer"], answer)
        self.assertEqual(self.plugin.agent_answer_cache["full_response"], full_response)
        self.assertEqual(self.plugin.agent_answer_cache["tool_calls"], tool_calls)

    async def test_after_tool_call_success(self):
        """测试工具调用成功时不启动subagent。"""
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={}
        )
        tool_result = "成功结果"
        
        # 工具调用成功，不应该启动subagent
        await self.plugin.after_tool_call(self.agent, tool_call, tool_result, True)
        
        # 验证没有发送subagent启动通知
        self.group_chat.send_if_exists.assert_not_called()

    async def test_after_tool_call_failure(self):
        """测试工具调用失败时启动subagent。"""
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={}
        )
        tool_result = "失败结果"
        
        # 设置缓存
        self.plugin.agent_answer_cache = {
            "full_response": "测试回答内容"
        }
        
        # 模拟subagent_manager
        mock_subagent_manager = MagicMock()
        mock_subagent_manager.create_subagent = AsyncMock()
        self.group_chat.get_members.return_value = mock_subagent_manager
        
        # 工具调用失败，应该启动subagent
        await self.plugin.after_tool_call(self.agent, tool_call, tool_result, False)
        
        # 验证发送了subagent启动通知
        self.group_chat.send_if_exists.assert_called_once()
        call_args = self.group_chat.send_if_exists.call_args
        self.assertEqual(call_args[0][0], "ui_log")
        self.assertIsInstance(call_args[0][1], CliRuntimeNotice)
        self.assertEqual(call_args[0][1].level, "WARNING")

    @patch("asyncio.create_task")
    async def test_check_violations_success(self, mock_create_task):
        """测试规则检查成功启动subagent。"""
        mock_subagent_manager = MagicMock()
        mock_subagent_manager.create_subagent = AsyncMock()
        
        full_response = "测试回答内容"
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={}
        )
        tool_result = "失败结果"
        
        # 模拟agent的get_current_model方法
        mock_model = MagicMock()
        self.agent.get_current_model = AsyncMock(return_value=mock_model)
        
        # 执行检查
        await self.plugin._check_violations(
            mock_subagent_manager, full_response, tool_call, tool_result
        )
        
        # 验证subagent被创建
        mock_subagent_manager.create_subagent.assert_called_once()
        call_args = mock_subagent_manager.create_subagent.call_args
        self.assertEqual(call_args[1]["agent_type"], "violation_checker")
        self.assertIn("violation_checker", call_args[1]["name"])

    @patch("logging.Logger.error")
    async def test_check_violations_exception_handling(self, mock_log_error):
        """测试规则检查异常处理。"""
        mock_subagent_manager = MagicMock()
        mock_subagent_manager.create_subagent = AsyncMock(side_effect=Exception("测试异常"))
        
        full_response = "测试回答内容"
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={}
        )
        tool_result = "失败结果"
        
        # 执行检查，应该捕获异常而不抛出
        await self.plugin._check_violations(
            mock_subagent_manager, full_response, tool_call, tool_result
        )
        
        # 验证错误被记录
        mock_log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()