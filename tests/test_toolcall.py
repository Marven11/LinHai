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
        self.mock_agent.group_chat.send_if_exists = AsyncMock()
        self.mock_agent.context = {
            "llms": [Mock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
        }
        self.mock_agent.large_messages = {}
        self.mock_agent.message_processor = Mock()
        self.mock_agent.message_processor.get_messages.return_value = []
        self.mock_agent.lifecycle = Mock()
        self.mock_agent.lifecycle.trigger_before_tool_call = AsyncMock(return_value=False)
        self.mock_agent.lifecycle.trigger_tool_success = AsyncMock()
        self.mock_agent.lifecycle.trigger_tool_failure = AsyncMock()
        self.mock_agent.lifecycle.trigger_tool_conflict = AsyncMock()
        
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
        self.mock_agent.lifecycle.trigger_tool_success.assert_called_once_with(self.mock_agent, tool_call, mock_result)

    async def test_call_tool_without_confirmation_failure_with_assert_success_false(self):
        """测试无需确认的工具调用失败且assert_success=False时不中断。"""
        # 设置mock
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False
        )
        
        from linhai.tool.base import ToolErrorMessage
        mock_error = ToolErrorMessage("test error")
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_error)
        
        # 调用方法
        result = await self.toolcall_processor.call_tool(tool_call)
        
        # 验证结果：应该返回False表示不中断
        self.assertFalse(result)
        self.mock_tool_manager.process_tool_call.assert_called_once_with(tool_call)
        self.mock_agent.lifecycle.trigger_before_tool_call.assert_called_once_with(tool_call)
        self.mock_agent.lifecycle.trigger_tool_failure.assert_called_once_with(self.mock_agent, tool_call, mock_error)

    async def test_call_tool_without_confirmation_failure(self):
        """测试无需确认的工具调用失败。"""
        # 设置mock
        
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
        # 确保process_tool_call被调用
        self.mock_tool_manager.process_tool_call.assert_called_once_with(tool_call)
        self.mock_agent.lifecycle.trigger_before_tool_call.assert_called_once_with(tool_call)
        self.mock_agent.lifecycle.trigger_tool_failure.assert_called_once_with(self.mock_agent, tool_call, mock_error)



    async def test_call_tool_state_change(self):
        """测试工具调用时状态改变。"""
        self.mock_agent.state = "waiting_user"
        
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

    async def test_call_tool_blocked_by_before_tool_call(self):
        """测试before_tool_call返回True时阻止工具调用。"""
        # 设置mock
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False
        )
        
        # 设置before_tool_call返回True，表示应该阻止工具调用
        self.mock_agent.lifecycle.trigger_before_tool_call = AsyncMock(return_value=True)
        
        # 调用方法
        result = await self.toolcall_processor.call_tool(tool_call)
        
        # 验证结果：应该返回True表示需要早期返回，且工具没有被调用
        self.assertTrue(result)
        self.mock_tool_manager.process_tool_call.assert_not_called()
        self.mock_agent.lifecycle.trigger_before_tool_call.assert_called_once_with(tool_call)

    async def test_multiple_tool_calls_with_mixed_results(self):
        """测试多个工具调用混合成功和失败的情况。"""
        
        # 第一个工具调用成功
        tool_call1 = ToolCallMessage(
            function_name="test_tool1",
            function_arguments={},
            assert_success=False
        )
        mock_result1 = Mock()
        mock_result1.__str__ = Mock(return_value="result1")
        
        # 第二个工具调用失败但assert_success=False
        tool_call2 = ToolCallMessage(
            function_name="test_tool2",
            function_arguments={},
            assert_success=False
        )
        from linhai.tool.base import ToolErrorMessage
        mock_error2 = ToolErrorMessage("error2")
        
        # 第三个工具调用失败且assert_success=True
        tool_call3 = ToolCallMessage(
            function_name="test_tool3",
            function_arguments={},
            assert_success=True
        )
        mock_error3 = ToolErrorMessage("error3")
        
        # 模拟不同的返回结果
        self.mock_tool_manager.process_tool_call = AsyncMock(side_effect=[
            mock_result1, mock_error2, mock_error3
        ])
        
        # 调用第一个工具
        result1 = await self.toolcall_processor.call_tool(tool_call1)
        self.assertFalse(result1)
        
        # 调用第二个工具（失败但不中断）
        result2 = await self.toolcall_processor.call_tool(tool_call2)
        self.assertFalse(result2)
        
        # 调用第三个工具（失败且中断）
        result3 = await self.toolcall_processor.call_tool(tool_call3)
        self.assertTrue(result3)
        
        # 验证所有工具都被调用
        self.assertEqual(self.mock_tool_manager.process_tool_call.call_count, 3)

    async def test_tool_call_with_exception_handling(self):
        """测试工具调用异常处理。"""
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False
        )
        
        # 模拟抛出RuntimeError
        self.mock_tool_manager.process_tool_call = AsyncMock(side_effect=RuntimeError("runtime error"))
        
        result = await self.toolcall_processor.call_tool(tool_call)
        
        # 验证返回False（不中断）
        self.assertFalse(result)
        self.mock_agent.lifecycle.trigger_tool_failure.assert_called_once()



    async def test_tool_conflict_detection(self):
        """测试工具冲突检测。"""
        
        # Mock send_if_exists to avoid await issues
        self.mock_agent.group_chat.send_if_exists = AsyncMock()
        
        # 创建两个冲突的工具
        from linhai.tool.base import ToolSet, ToolArgInfo
        
        toolset1 = ToolSet()
        toolset2 = ToolSet()
        
        @toolset1.register_tool(
            name="tool_a",
            desc="工具A",
            args={},
            required_args=[],
            conflict_with=["tool_b"]
        )
        def tool_a():
            return "a"
        
        @toolset2.register_tool(
            name="tool_b",
            desc="工具B",
            args={},
            required_args=[],
            conflict_with=["tool_a"]
        )
        def tool_b():
            return "b"
        
        self.mock_tool_manager.toolsets = [toolset1, toolset2]
        self.mock_tool_manager.has_tool = lambda name: name in ["tool_a", "tool_b"]
        self.mock_tool_manager.get_tools = lambda: {**toolset1.get_tools(), **toolset2.get_tools()}
        
        # 先调用tool_a
        tool_call_a = ToolCallMessage(
            function_name="tool_a",
            function_arguments={},
            assert_success=False
        )
        mock_result_a = Mock()
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result_a)
        
        result_a = await self.toolcall_processor.call_tool(tool_call_a)
        self.assertFalse(result_a)
        
        # 再调用tool_b应该触发冲突
        tool_call_b = ToolCallMessage(
            function_name="tool_b",
            function_arguments={},
            assert_success=False
        )
        
        result_b = await self.toolcall_processor.call_tool(tool_call_b)
        self.assertTrue(result_b)  # 冲突导致早期返回
        self.assertTrue(self.toolcall_processor.early_return)

    async def test_start_new_tool_call_round(self):
        """测试开始新一轮工具调用。"""
        # 先调用一个工具
        self.toolcall_processor.called_tools_in_round = ["tool1"]
        self.toolcall_processor.early_return = True
        
        # 开始新一轮
        self.toolcall_processor.start_new_tool_call_round()
        
        # 验证状态重置
        self.assertEqual(self.toolcall_processor.called_tools_in_round, [])
        self.assertFalse(self.toolcall_processor.early_return)

    async def test_compress_tool_flag_setting(self):
        """测试压缩工具标志设置。"""
        
        # 调用压缩工具
        tool_call = ToolCallMessage(
            function_name="mark_messages_as_garbage",
            function_arguments={"ids": ["msg1"]},
            assert_success=False
        )
        
        mock_result = Mock()
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)
        
        await self.toolcall_processor.call_tool(tool_call)
        
        # 验证标志被设置
        self.assertTrue(self.mock_agent.compress_tool_called_in_last_response)

if __name__ == "__main__":
    unittest.main()