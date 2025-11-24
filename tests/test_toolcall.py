"""AgentToolcall类的单元测试。"""

import unittest
from unittest.mock import Mock, AsyncMock
from linhai.agent.toolcall import AgentToolcall
from linhai.llm import ToolCallMessage


class TestAgentToolcall(unittest.IsolatedAsyncioTestCase):
    """AgentToolcall类的测试用例。"""

    def setUp(self):
        """设置测试环境。"""
        self.mock_agent = Mock()
        self.mock_agent.group_chat = Mock()
        self.mock_agent.context = {
            "llms": [Mock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "tool_confirmation": {}
        }
        self.mock_agent.large_messages = {}
        self.mock_agent.message_processor = Mock()
        self.mock_agent.message_processor.get_messages.return_value = []
        self.mock_agent.lifecycle = Mock()
        self.mock_agent.lifecycle.trigger_before_tool_call = AsyncMock()
        self.mock_agent.lifecycle.trigger_after_tool_call = AsyncMock()
        
        # Mock tool manager
        self.mock_tool_manager = Mock()
        self.mock_tool_manager.toolsets = []
        self.mock_agent.group_chat.get_members.return_value = self.mock_tool_manager
        
        self.toolcall_processor = AgentToolcall(self.mock_agent)

    def test_initialization(self):
        """测试AgentToolcall初始化。"""
        self.assertEqual(self.toolcall_processor.agent, self.mock_agent)
        self.assertEqual(self.toolcall_processor.group_chat, self.mock_agent.group_chat)
        self.assertEqual(self.toolcall_processor.context, self.mock_agent.context)
        self.assertEqual(self.toolcall_processor.skip_confirmation, False)
        self.assertEqual(self.toolcall_processor.whitelist, [])

    def test_register_llm_toolset(self):
        """测试LLM工具集注册。"""
        # 检查tool_manager是否被调用添加工具集
        self.mock_tool_manager.add_toolset.assert_called()

    def test_register_dummy_toolset(self):
        """测试虚拟工具集注册。"""
        # 检查tool_manager是否被调用添加工具集
        self.mock_tool_manager.add_toolset.assert_called()

    def test_register_workflow_toolset(self):
        """测试工作流工具集注册。"""
        # 检查tool_manager是否被调用添加工具集
        self.mock_tool_manager.add_toolset.assert_called()

    async def test_call_tool_without_confirmation_success(self):
        """测试无需确认的工具调用成功。"""
        # 设置mock
        self.toolcall_processor.skip_confirmation = True
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False
        )
        
        mock_result = Mock()
        mock_result.__str__ = Mock(return_value="test result")
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)
        
        # 调用方法
        result = await self.toolcall_processor.call_tool(tool_call)
        
        # 验证结果
        self.assertFalse(result)
        self.mock_tool_manager.process_tool_call.assert_called_once_with(tool_call)
        self.mock_agent.lifecycle.trigger_before_tool_call.assert_called_once_with(tool_call)
        self.mock_agent.lifecycle.trigger_after_tool_call.assert_called_once_with(self.mock_agent, tool_call, mock_result, True)

    async def test_call_tool_without_confirmation_failure(self):
        """测试无需确认的工具调用失败。"""
        # 设置mock
        self.toolcall_processor.skip_confirmation = True
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True
        )
        
        from linhai.tool.base import ToolErrorMessage
        mock_error = ToolErrorMessage("test error")
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_error)
        
        # 调用方法
        result = await self.toolcall_processor.call_tool(tool_call)
        
        # 验证结果
        self.assertTrue(result)
        self.mock_tool_manager.process_tool_call.assert_called_once_with(tool_call)
        self.mock_agent.lifecycle.trigger_before_tool_call.assert_called_once_with(tool_call)
        self.mock_agent.lifecycle.trigger_after_tool_call.assert_called_once_with(self.mock_agent, tool_call, mock_error, False)

    async def test_call_tool_with_whitelist(self):
        """测试白名单工具调用。"""
        # 设置mock
        self.toolcall_processor.skip_confirmation = False
        self.toolcall_processor.whitelist = ["test_tool"]
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False
        )
        
        mock_result = Mock()
        mock_result.__str__ = Mock(return_value="test result")
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)
        
        # 调用方法
        result = await self.toolcall_processor.call_tool(tool_call)
        
        # 验证结果
        self.assertFalse(result)
        self.mock_tool_manager.process_tool_call.assert_called_once_with(tool_call)

    async def test_call_tool_with_confirmation(self):
        """测试需要确认的工具调用。"""
        # 设置mock
        self.toolcall_processor.skip_confirmation = False
        self.toolcall_processor.whitelist = []
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False
        )
        
        # Mock CLIApp确认
        mock_cli_app = Mock()
        mock_confirmation = Mock()
        mock_confirmation.tool_call.function_name = "test_tool"
        mock_confirmation.confirmed = True
        mock_cli_app.confirm_tool_request = AsyncMock(return_value=mock_confirmation)
        self.mock_agent.group_chat.get_members.return_value = mock_cli_app
        
        mock_result = Mock()
        mock_result.__str__ = Mock(return_value="test result")
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)
        
        # 调用方法
        result = await self.toolcall_processor.call_tool(tool_call)
        
        # 验证结果
        self.assertFalse(result)
        mock_cli_app.confirm_tool_request.assert_called_once_with(tool_call)
        self.mock_tool_manager.process_tool_call.assert_called_once_with(tool_call)

    async def test_call_tool_state_change(self):
        """测试工具调用时状态改变。"""
        self.mock_agent.state = "waiting_user"
        self.toolcall_processor.skip_confirmation = True
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False
        )
        
        mock_result = Mock()
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)
        
        await self.toolcall_processor.call_tool(tool_call)
        
        # 验证状态已改变
        self.assertEqual(self.mock_agent.state, "working")

if __name__ == "__main__":
    unittest.main()