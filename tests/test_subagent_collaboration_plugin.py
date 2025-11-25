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
        self.agent = AsyncMock()
        self.agent.message_processor = AsyncMock()
        self.agent.message_processor.get_messages = AsyncMock(return_value=[])
        self.agent.message_processor.append_message = AsyncMock()
        
        self.group_chat = AsyncMock()
        self.group_chat.get_members = AsyncMock(return_value=self.agent)
        self.group_chat.send_if_exists = AsyncMock()
        
        self.plugin = SubAgentCollaborationPlugin(self.group_chat)

    async def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_tool_failure.assert_called_once_with(
            self.plugin.tool_failure
        )
        lifecycle.register_tool_conflict.assert_called_once_with(
            self.plugin.tool_conflict
        )

    async def test_tool_failure(self):
        """测试工具失败时启动subagent。"""
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={}
        )
        error = "测试错误"
        
        # 模拟subagent_manager
        mock_subagent_manager = AsyncMock()
        mock_subagent_manager.create_subagent = AsyncMock()
        self.group_chat.get_members.return_value = mock_subagent_manager
        
        # 模拟agent
        mock_agent = MagicMock()
        mock_agent.current_answer = MagicMock()
        mock_agent.current_answer.get_current_content = MagicMock(return_value="测试回答内容")
        
        # 工具调用失败，应该启动subagent
        await self.plugin.tool_failure(mock_agent, tool_call, error)
        
        # 验证发送了subagent启动通知
        self.group_chat.send_if_exists.assert_called_once()
        call_args = self.group_chat.send_if_exists.call_args
        self.assertEqual(call_args[0][0], "ui_log")
        self.assertEqual(call_args[0][1].level, "WARNING")

    async def test_tool_conflict(self):
        """测试工具冲突时启动subagent。"""
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={}
        )
        conflicting_tools = ["conflicting_tool1", "conflicting_tool2"]
        
        # 模拟subagent_manager
        mock_subagent_manager = AsyncMock()
        mock_subagent_manager.create_subagent = AsyncMock()
        self.group_chat.get_members.return_value = mock_subagent_manager
        
        # 模拟agent
        mock_agent = MagicMock()
        mock_agent.current_answer = MagicMock()
        mock_agent.current_answer.get_current_content = MagicMock(return_value="测试回答内容")
        
        # 工具调用冲突，应该启动subagent
        await self.plugin.tool_conflict(mock_agent, tool_call, conflicting_tools)
        
        # 验证发送了subagent启动通知
        self.group_chat.send_if_exists.assert_called_once()
        call_args = self.group_chat.send_if_exists.call_args
        self.assertEqual(call_args[0][0], "ui_log")
        self.assertEqual(call_args[0][1].level, "WARNING")

    async def test_check_violations_success(self):
        """测试规则检查成功启动subagent。"""
        mock_subagent_manager = MagicMock()
        mock_subagent_manager.create_subagent = AsyncMock()
        
        full_response = "测试回答内容"
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={}
        )
        error = "测试错误"
        
        # 执行检查
        await self.plugin._check_violations(
            mock_subagent_manager, full_response, tool_call, error
        )
        
        # 验证subagent被创建
        mock_subagent_manager.create_subagent.assert_called_once()
        call_args = mock_subagent_manager.create_subagent.call_args
        self.assertEqual(call_args[1]["agent_type"], "violation_checker")
        self.assertIn("violation_subagent", call_args[1]["name"])

    @patch("asyncio.create_task")
    async def test_check_violations_success_with_patch(self, mock_create_task):
        """测试规则检查成功启动subagent（使用patch）。"""
        mock_subagent_manager = MagicMock()
        mock_subagent_manager.create_subagent = AsyncMock()
        
        full_response = "测试回答内容"
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={}
        )
        error = "测试错误"
        
        # 执行检查
        await self.plugin._check_violations(
            mock_subagent_manager, full_response, tool_call, error
        )
        
        # 验证subagent被创建
        mock_subagent_manager.create_subagent.assert_called_once()
        call_args = mock_subagent_manager.create_subagent.call_args
        self.assertEqual(call_args[1]["agent_type"], "violation_checker")

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
        error = "测试错误"
        
        # 执行检查，应该捕获异常而不抛出
        await self.plugin._check_violations(
            mock_subagent_manager, full_response, tool_call, error
        )
        
        # 验证错误被记录
        mock_log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()