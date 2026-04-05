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
        self.mock_agent.registry = Mock()
        self.mock_agent.registry.send_if_exists = AsyncMock()
        self.mock_agent.context = {
            "llms": [Mock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
        }
        self.mock_agent.large_messages = {}
        self.mock_agent.message_processor = Mock()
        self.mock_agent.message_processor.add_new_message = AsyncMock()
        self.mock_agent.message_processor.get_messages.return_value = []
        self.mock_agent.lifecycle = Mock()
        self.mock_agent.lifecycle.trigger_after_toolcall = AsyncMock(return_value=None)
        self.mock_agent.lifecycle.trigger_before_tool_call = AsyncMock(
            return_value=None
        )

        self.mock_tool_manager = Mock()
        self.mock_tool_manager.toolsets = []
        # 模拟llm_manager
        self.mock_llm_manager = Mock()
        # 创建模拟的LLM对象
        mock_llm = Mock()
        mock_llm.get_name = Mock(return_value="test_llm")
        mock_llm.get_token_limit = Mock(return_value=65536)
        self.mock_llm_manager.llms = [mock_llm]
        self.mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)
        self.mock_agent.llm_manager = self.mock_llm_manager
        self.mock_agent.get_current_model = Mock(return_value=mock_llm)

        self.mock_tool_manager = Mock()
        self.mock_tool_manager.toolsets = []
        self.mock_agent.registry.get_member_typechecked.return_value = (
            self.mock_tool_manager
        )

        self.toolcall_processor = AgentToolcall(self.mock_agent)

    def test_initialization(self):
        """测试AgentToolcall初始化。"""
        self.assertEqual(self.toolcall_processor.agent, self.mock_agent)
        self.assertEqual(self.toolcall_processor.registry, self.mock_agent.registry)
        # context属性已移除，不再检查

    def test_calculate_llm_toolset(self):
        """测试calculate_llm_toolset方法返回正确的toolset。"""
        toolset = self.toolcall_processor.calculate_llm_toolset()
        self.assertIsNotNone(toolset)
        self.assertIn("switch_llm", toolset.get_tools())
        self.assertIn("current_llm", toolset.get_tools())
        self.assertIn("list_llm", toolset.get_tools())
        self.assertIn("get_token_usage", toolset.get_tools())

    async def test_call_tool_without_confirmation_success(self):
        """测试无需确认的工具调用成功。"""

        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        mock_result = Mock()
        mock_result.__str__ = Mock(return_value="test result")
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)

        result = await self.toolcall_processor.call_tool(tool_call, tool_index=1)

        self.assertFalse(result)
        self.mock_tool_manager.process_tool_call.assert_called_once_with(tool_call, 1)
        # 新的on_tool_result回调会被调用两次：skipped和success
        self.assertGreaterEqual(
            self.mock_agent.lifecycle.trigger_after_toolcall.call_count, 1
        )
        # 获取最后一次调用
        last_call = self.mock_agent.lifecycle.trigger_after_toolcall.call_args
        # 检查最后一次调用是success状态
        self.assertEqual(last_call[1]["status"], "success")
        self.assertEqual(last_call[1]["tool_name"], "test_tool")
        self.assertEqual(last_call[1]["tool_index"], 1)

    async def test_call_tool_without_confirmation_failure_with_assert_success_false(
        self,
    ):
        """测试无需确认的工具调用失败且assert_success=False时不中断。"""

        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        from linhai.tool.base import ToolCallResultMessage, ToolResultFailed

        mock_error = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=0,
            result=ToolResultFailed(content="test error"),
            toolcall_arguments={},
        )
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_error)

        result = await self.toolcall_processor.call_tool(tool_call, tool_index=1)

        self.assertFalse(result)
        self.mock_tool_manager.process_tool_call.assert_called_once_with(tool_call, 1)
        # 新的on_tool_result回调会被调用两次：skipped和failed
        self.assertGreaterEqual(
            self.mock_agent.lifecycle.trigger_after_toolcall.call_count, 1
        )
        # 获取最后一次调用
        last_call = self.mock_agent.lifecycle.trigger_after_toolcall.call_args
        # 检查最后一次调用是failed状态，因为工具调用失败
        self.assertEqual(last_call[1]["status"], "failed")
        self.assertEqual(last_call[1]["tool_name"], "test_tool")
        self.assertEqual(last_call[1]["tool_index"], 1)

    async def test_call_tool_without_confirmation_failure(self):
        """测试无需确认的工具调用失败。"""

        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )

        from linhai.tool.base import ToolCallResultMessage, ToolResultFailed

        mock_error = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=0,
            result=ToolResultFailed(content="test error"),
            toolcall_arguments={},
        )
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_error)

        result = await self.toolcall_processor.call_tool(tool_call, tool_index=1)

        self.assertTrue(result)
        self.mock_tool_manager.process_tool_call.assert_called_once_with(tool_call, 1)
        # 新的on_tool_result回调会被调用两次：skipped和failed
        self.assertGreaterEqual(
            self.mock_agent.lifecycle.trigger_after_toolcall.call_count, 1
        )
        # 获取最后一次调用
        last_call = self.mock_agent.lifecycle.trigger_after_toolcall.call_args
        # 检查最后一次调用是failed状态
        self.assertEqual(last_call[1]["status"], "failed")
        self.assertEqual(last_call[1]["tool_name"], "test_tool")
        self.assertEqual(last_call[1]["tool_index"], 1)

    async def test_call_tool_state_change(self):
        """测试工具调用时状态改变。"""
        self.mock_agent.state = "waiting_user"

        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )

        mock_result = Mock()
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)

        await self.toolcall_processor.call_tool(tool_call, tool_index=1)

        self.assertEqual(self.mock_agent.state, "working")

    async def test_multiple_tool_calls_with_mixed_results(self):
        """测试多个工具调用混合成功和失败的情况。"""

        from linhai.tool.base import (
            ToolCallResultMessage,
            ToolResultSuccess,
            ToolResultFailed,
        )

        tool_call1 = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )
        mock_result1 = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=0,
            result=ToolResultSuccess(content="result1"),
            toolcall_arguments={},
        )

        tool_call2 = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )
        mock_error2 = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=ToolResultFailed(content="error2"),
            toolcall_arguments={},
        )

        tool_call3 = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )
        mock_error3 = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=2,
            result=ToolResultFailed(content="error3"),
            toolcall_arguments={},
        )

        self.mock_tool_manager.process_tool_call = AsyncMock(
            side_effect=[mock_result1, mock_error2, mock_error3]
        )

        result1 = await self.toolcall_processor.call_tool(tool_call1, tool_index=1)
        self.assertFalse(result1)

        result2 = await self.toolcall_processor.call_tool(tool_call2, tool_index=2)
        self.assertFalse(result2)

        result3 = await self.toolcall_processor.call_tool(tool_call3, tool_index=3)
        self.assertTrue(result3)

        self.assertEqual(self.mock_tool_manager.process_tool_call.call_count, 3)

    async def test_tool_conflict_detection(self):
        """测试工具冲突检测。"""

        self.mock_agent.registry.send_if_exists = AsyncMock()

        from linhai.tool.base import ToolSet, ToolArgInfo

        toolset1 = ToolSet()
        toolset2 = ToolSet()

        @toolset1.register_tool(
            name="tool_a",
            desc="工具A",
            args={},
            required_args=[],
            conflict_with=["tool_b"],
        )
        def tool_a():
            return "a"

        @toolset2.register_tool(
            name="tool_b",
            desc="工具B",
            args={},
            required_args=[],
            conflict_with=["tool_a"],
        )
        def tool_b():
            return "b"

        self.mock_tool_manager.toolsets = [toolset1, toolset2]
        self.mock_tool_manager.has_tool = lambda name: name in ["tool_a", "tool_b"]
        self.mock_tool_manager.get_tools = lambda: {
            **toolset1.get_tools(),
            **toolset2.get_tools(),
        }

        tool_call_a = ToolCallMessage(
            function_name="tool_a",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )
        mock_result_a = Mock()
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result_a)

        result_a = await self.toolcall_processor.call_tool(tool_call_a, tool_index=1)
        self.assertFalse(result_a)

        tool_call_b = ToolCallMessage(
            function_name="tool_b",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )

        result_b = await self.toolcall_processor.call_tool(tool_call_b, tool_index=2)
        self.assertTrue(result_b)  # 冲突导致早期返回
        self.assertTrue(self.toolcall_processor.early_return)

    async def test_start_new_tool_call_round(self):
        """测试开始新一轮工具调用。"""
        self.toolcall_processor.called_tools_in_round = ["tool1"]
        self.toolcall_processor.early_return = True

        self.toolcall_processor.start_new_tool_call_round()

        self.assertEqual(self.toolcall_processor.called_tools_in_round, [])
        self.assertFalse(self.toolcall_processor.early_return)

    async def test_tool_index_increment_and_passing(self):
        """测试tool_index正确递增和传递。"""
        from linhai.tool.base import ToolCallResultMessage, ToolResultSuccess
        from unittest.mock import call

        tool_call1 = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )
        tool_call2 = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )

        mock_result1 = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=ToolResultSuccess(content="result1"),
            toolcall_arguments={},
        )
        mock_result2 = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=2,
            result=ToolResultSuccess(content="result2"),
            toolcall_arguments={},
        )

        self.mock_tool_manager.process_tool_call = AsyncMock(
            side_effect=[mock_result1, mock_result2]
        )

        # 第一次调用，tool_index应为1
        result1 = await self.toolcall_processor.call_tool(tool_call1, tool_index=1)
        self.assertFalse(result1)
        # 第二次调用，tool_index应为2
        result2 = await self.toolcall_processor.call_tool(tool_call2, tool_index=2)
        self.assertFalse(result2)

        # 验证调用参数
        calls = self.mock_tool_manager.process_tool_call.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], call(tool_call1, 1))
        self.assertEqual(calls[1], call(tool_call2, 2))

    async def test_compress_tool_flag_setting(self):
        """测试压缩工具标志设置。"""

        tool_call = ToolCallMessage(
            function_name="mark_messages_as_garbage",
            function_arguments={"ids": ["msg1"]},
            assert_success=False,
            with_secret=None,
        )

        mock_result = Mock()
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)

        await self.toolcall_processor.call_tool(tool_call, tool_index=1)

        self.assertTrue(self.mock_agent.compress_tool_called_in_last_response)


if __name__ == "__main__":
    unittest.main()
