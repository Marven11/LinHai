"""AgentToolcall token管理功能的Test Driven Development测试。"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from linhai.agent.toolcall import AgentToolcall
from linhai.base import ToolCallMessage
from linhai.agent.messages import RuntimeMessage
from linhai.tool.base import (
    ToolCallResultMessage,
    SuccessfulToolResult,
    FailedToolResult,
)


class TestToolcallTokenManagementTDD(unittest.IsolatedAsyncioTestCase):
    """AgentToolcall token管理功能的TDD测试用例。"""

    def setUp(self):
        """设置测试环境。"""
        self.mock_agent = Mock()
        self.mock_agent.message_processor = Mock()
        self.mock_agent.message_processor.get_messages.return_value = []
        self.mock_agent.lifecycle = Mock()
        self.mock_agent.lifecycle.after_toolcall.trigger = AsyncMock(return_value=None)
        self.mock_agent.lifecycle.before_tool_call.trigger = AsyncMock(
            return_value=None
        )

        self.mock_llm_manager = Mock()
        mock_llm = Mock()
        mock_llm.get_name = Mock(return_value="test_llm")
        mock_llm.get_token_limit = Mock(return_value=65536)
        self.mock_llm_manager.llms = [mock_llm]
        self.mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)

        self.mock_tool_manager = Mock()
        self.mock_tool_manager.toolsets = []

        self.temp_dir = tempfile.mkdtemp()

        self.mock_registry = Mock()
        self.mock_registry.send_if_exists = AsyncMock()

        def get_member_typechecked_side_effect(name, t):
            members = {
                "tool_manager": self.mock_tool_manager,
                "llm_manager": self.mock_llm_manager,
                "lifecycle": self.mock_agent.lifecycle,
                "agent_message": self.mock_agent.message_processor,
                "conversation_folder": Path(self.temp_dir),
            }
            return members[name]

        self.mock_registry.get_member_typechecked = Mock(
            side_effect=get_member_typechecked_side_effect
        )

        self.toolcall_processor = AgentToolcall(self.mock_registry)
        self.toolcall_processor.max_token_limit = 3000
        self.toolcall_processor.current_round_token_count = 0

        self.mock_conversation = Mock()
        self.mock_conversation.conversation_dir = Path(self.temp_dir)

    def tearDown(self):
        """清理测试环境。"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_single_tool_short_output(self):
        """测试单个工具输出小于限制长度的1/3时正常返回。"""
        short_content = "x" * 100
        tool_result = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=SuccessfulToolResult(content=short_content),
            toolcall_arguments=None,
        )

        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        result = await self.toolcall_processor._tool_result_token_management(
            tool_call, 1, tool_result
        )

        self.assertEqual(result, tool_result)
        self.assertGreater(self.toolcall_processor.current_round_token_count, 0)

    async def test_single_tool_long_output_exceeds_one_third_limit(self):
        """测试单个工具输出大于限制长度的1/3时保存到文件。"""
        long_content = "x" * 15000
        tool_result = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=SuccessfulToolResult(content=long_content),
            toolcall_arguments=None,
        )

        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        result = await self.toolcall_processor._tool_result_token_management(
            tool_call, 1, tool_result
        )

        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("工具输出过长", str(result))

        long_toolcall_dir = Path(self.temp_dir) / "long_toolcall"
        self.assertTrue(long_toolcall_dir.exists())
        files = list(long_toolcall_dir.glob("*.txt"))
        self.assertGreaterEqual(len(files), 1)
        combined_content = ""
        for file in sorted(files, key=lambda x: x.name):
            with open(file, "r", encoding="utf-8") as f:
                combined_content += f.read()
        self.assertEqual(combined_content, tool_result.get_content())

    async def test_two_tools_each_short_output(self):
        """测试2个工具，每个输出都远小于限制长度的1/3时正常返回。"""
        short_content1 = "x" * 100
        tool_result1 = ToolCallResultMessage(
            tool_name="test_tool1",
            tool_index=1,
            result=SuccessfulToolResult(content=short_content1),
            toolcall_arguments=None,
        )

        tool_call1 = ToolCallMessage(
            function_name="test_tool1",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        result1 = await self.toolcall_processor._tool_result_token_management(
            tool_call1, 1, tool_result1
        )

        token_count1 = self.toolcall_processor.current_round_token_count

        short_content2 = "y" * 100
        tool_result2 = ToolCallResultMessage(
            tool_name="test_tool2",
            tool_index=2,
            result=SuccessfulToolResult(content=short_content2),
            toolcall_arguments=None,
        )

        tool_call2 = ToolCallMessage(
            function_name="test_tool2",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        result2 = await self.toolcall_processor._tool_result_token_management(
            tool_call2, 2, tool_result2
        )
        token_count2 = self.toolcall_processor.current_round_token_count

        self.assertGreater(token_count2, token_count1)

    async def test_five_tools_each_short_output(self):
        """测试5个工具，每个输出都小于限制长度的1/5时正常返回。"""
        total_tokens = 0

        for i in range(5):
            content = "x" * 100
            tool_result = ToolCallResultMessage(
                tool_name=f"test_tool{i}",
                tool_index=i + 1,
                result=SuccessfulToolResult(content=content),
                toolcall_arguments=None,
            )

            tool_call = ToolCallMessage(
                function_name=f"test_tool{i}",
                function_arguments={},
                assert_success=False,
                with_secret=None,
            )

            result = await self.toolcall_processor._tool_result_token_management(
                tool_call, i + 1, tool_result
            )

            total_tokens = self.toolcall_processor.current_round_token_count

        self.assertLess(total_tokens, self.toolcall_processor.max_token_limit)

    async def test_three_tools_second_tool_long_output(self):
        """测试三个工具，只有第二个工具输出略大于限制长度的1/3。"""
        content1 = "x" * 100
        tool_result1 = ToolCallResultMessage(
            tool_name="test_tool1",
            tool_index=1,
            result=SuccessfulToolResult(content=content1),
            toolcall_arguments=None,
        )

        tool_call1 = ToolCallMessage(
            function_name="test_tool1",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        result1 = await self.toolcall_processor._tool_result_token_management(
            tool_call1, 1, tool_result1
        )

        for i in range(5):
            content = "x" * 100
            tool_result = ToolCallResultMessage(
                tool_name=f"test_tool{i}",
                tool_index=i + 1,
                result=SuccessfulToolResult(content=content),
                toolcall_arguments=None,
            )

            tool_call = ToolCallMessage(
                function_name=f"test_tool{i}",
                function_arguments={},
                assert_success=False,
                with_secret=None,
            )

            result = await self.toolcall_processor._tool_result_token_management(
                tool_call, i + 1, tool_result
            )
            total_tokens = self.toolcall_processor.current_round_token_count

        self.assertLess(total_tokens, self.toolcall_processor.max_token_limit)

    async def test_three_tools_second_tool_long_output(self):
        """测试三个工具，只有第二个工具输出略大于限制长度的1/3。"""
        content1 = "x" * 100
        tool_result1 = ToolCallResultMessage(
            tool_name="test_tool1",
            tool_index=1,
            result=SuccessfulToolResult(content=content1),
            toolcall_arguments=None,
        )

        tool_call1 = ToolCallMessage(
            function_name="test_tool1",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        result1 = await self.toolcall_processor._tool_result_token_management(
            tool_call1, 1, tool_result1
        )

        content2 = "x" * 12000
        tool_result2 = ToolCallResultMessage(
            tool_name="test_tool2",
            tool_index=2,
            result=SuccessfulToolResult(content=content2),
            toolcall_arguments=None,
        )

        tool_call2 = ToolCallMessage(
            function_name="test_tool2",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        result2 = await self.toolcall_processor._tool_result_token_management(
            tool_call2, 2, tool_result2
        )
        self.assertIsInstance(result2, RuntimeMessage)

        content3 = "x" * 100
        tool_result3 = ToolCallResultMessage(
            tool_name="test_tool3",
            tool_index=3,
            result=SuccessfulToolResult(content=content3),
            toolcall_arguments=None,
        )

        tool_call3 = ToolCallMessage(
            function_name="test_tool3",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        result3 = await self.toolcall_processor._tool_result_token_management(
            tool_call3, 3, tool_result3
        )

    async def test_on_tool_result_replacement(self):
        """测试当on_tool_result回调返回AfterToolcallResult时使用替换内容。"""
        from linhai.agent.lifecycle import AfterToolcallResult

        replacement_message = RuntimeMessage("替换消息")
        self.mock_agent.lifecycle.after_toolcall.trigger = AsyncMock(
            return_value=AfterToolcallResult(replacement=replacement_message)
        )

        content = "x" * 100
        tool_result = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=SuccessfulToolResult(content=content),
            toolcall_arguments=None,
        )
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )

        result = await self.toolcall_processor._tool_result_token_management(
            tool_call, 1, tool_result
        )

        self.assertIsInstance(result, ToolCallResultMessage)
        self.assertIn("替换消息", result.result.content)
