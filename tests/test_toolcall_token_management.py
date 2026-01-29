"""AgentToolcall token管理功能的Test Driven Development测试。"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from linhai.agent.toolcall import AgentToolcall
from linhai.llm import ToolCallMessage
from linhai.agent.base import RuntimeMessage
from linhai.tool.base import ToolCallResultMessage, ToolResultSuccess, ToolResultFailed


class TestToolcallTokenManagementTDD(unittest.IsolatedAsyncioTestCase):
    """AgentToolcall token管理功能的TDD测试用例。"""

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
        self.mock_agent.lifecycle.trigger_on_tool_result = AsyncMock(return_value=None)
        self.mock_agent.lifecycle.trigger_before_tool_call = AsyncMock(return_value=None)
        
        # 模拟配置
        self.mock_agent.config = Mock()
        self.mock_agent.config.tools = Mock()
        self.mock_agent.config.tools.max_toolcall_token_in_round = 3000  # 降低限制以方便测试
        
        self.mock_tool_manager = Mock()
        self.mock_tool_manager.toolsets = []
        self.mock_agent.group_chat.get_members.return_value = self.mock_tool_manager

        self.toolcall_processor = AgentToolcall(self.mock_agent)
        # 设置较低的token限制，这样15000字符就能超过限制
        self.toolcall_processor.max_token_limit = 3000
        self.toolcall_processor.current_round_token_count = 0
        
        # 创建临时目录用于测试文件保存
        self.temp_dir = tempfile.mkdtemp()
        
        # 模拟conversation目录
        self.mock_conversation = Mock()
        self.mock_conversation.conversation_dir = Path(self.temp_dir)
        
    def tearDown(self):
        """清理测试环境。"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_single_tool_short_output(self):
        """测试单个工具输出小于限制长度的1/3时正常返回。"""
        # 创建短输出（约100 tokens，远小于1000限制）
        short_content = "x" * 100
        tool_result = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=ToolResultSuccess(content=short_content),
            toolcall_arguments=None,
        )
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )
        
        with patch('linhai.agent.conversation.get_current_conversation', return_value=self.mock_conversation):
            result, skip_handle = await self.toolcall_processor._tool_result_token_management(
                tool_call, 1, tool_result
            )
            
            self.assertFalse(skip_handle)
            self.assertEqual(result, tool_result)
            self.assertGreater(self.toolcall_processor.current_round_token_count, 0)

    async def test_single_tool_long_output_exceeds_one_third_limit(self):
        """测试单个工具输出大于限制长度的1/3时保存到文件。"""
        # 单个工具限制是1000 tokens（3000/3）
        # 创建长输出（约15000字符，约1875 tokens，大于1000限制）
        long_content = "x" * 15000
        tool_result = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=ToolResultSuccess(content=long_content),
            toolcall_arguments=None,
        )
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )
        
        with patch('linhai.agent.conversation.get_current_conversation', return_value=self.mock_conversation):
            result, skip_handle = await self.toolcall_processor._tool_result_token_management(
                tool_call, 1, tool_result
            )
            
            self.assertTrue(skip_handle)
            self.assertIsInstance(result, RuntimeMessage)
            self.assertIn("工具输出过长", str(result))
            
            # 检查文件是否保存
            long_toolcall_dir = Path(self.temp_dir) / "long_toolcall"
            self.assertTrue(long_toolcall_dir.exists())
            files = list(long_toolcall_dir.glob("*.txt"))
            self.assertEqual(len(files), 1)

    async def test_two_tools_each_short_output(self):
        """测试2个工具，每个输出都远小于限制长度的1/3时正常返回。"""
        # 第一个短输出
        short_content1 = "x" * 100
        tool_result1 = ToolCallResultMessage(
            tool_name="test_tool1",
            tool_index=1,
            result=ToolResultSuccess(content=short_content1),
            toolcall_arguments=None,
        )
        
        tool_call1 = ToolCallMessage(
            function_name="test_tool1",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )
        
        with patch('linhai.agent.conversation.get_current_conversation', return_value=self.mock_conversation):
            result1, skip_handle1 = await self.toolcall_processor._tool_result_token_management(
                tool_call1, 1, tool_result1
            )
            
            self.assertFalse(skip_handle1)
            token_count1 = self.toolcall_processor.current_round_token_count
            
            # 第二个短输出
            short_content2 = "y" * 100
            tool_result2 = ToolCallResultMessage(
                tool_name="test_tool2",
                tool_index=2,
                result=ToolResultSuccess(content=short_content2),
                toolcall_arguments=None,
            )
            
            tool_call2 = ToolCallMessage(
                function_name="test_tool2",
                function_arguments={},
                assert_success=False,
                with_secret=None,
            )
            
            result2, skip_handle2 = await self.toolcall_processor._tool_result_token_management(
                tool_call2, 2, tool_result2
            )
            
            self.assertFalse(skip_handle2)
            token_count2 = self.toolcall_processor.current_round_token_count
            
            # 验证token累加
            self.assertGreater(token_count2, token_count1)

    async def test_five_tools_each_short_output(self):
        """测试5个工具，每个输出都小于限制长度的1/5时正常返回。"""
        total_tokens = 0
        
        with patch('linhai.agent.conversation.get_current_conversation', return_value=self.mock_conversation):
            for i in range(5):
                # 每个约100字符，远小于600限制(1/5)
                content = "x" * 100
                tool_result = ToolCallResultMessage(
                    tool_name=f"test_tool{i}",
                    tool_index=i+1,
                    result=ToolResultSuccess(content=content),
                    toolcall_arguments=None,
                )
                
                tool_call = ToolCallMessage(
                    function_name=f"test_tool{i}",
                    function_arguments={},
                    assert_success=False,
                    with_secret=None,
                )
                
                result, skip_handle = await self.toolcall_processor._tool_result_token_management(
                    tool_call, i+1, tool_result
                )
                
                self.assertFalse(skip_handle)
                total_tokens = self.toolcall_processor.current_round_token_count
            
            self.assertLess(total_tokens, self.toolcall_processor.max_token_limit)

    async def test_three_tools_second_tool_long_output(self):
        """测试三个工具，只有第二个工具输出略大于限制长度的1/3。"""
        with patch('linhai.agent.conversation.get_current_conversation', return_value=self.mock_conversation):
            # 第一个短工具
            content1 = "x" * 100
            tool_result1 = ToolCallResultMessage(
                tool_name="test_tool1",
                tool_index=1,
                result=ToolResultSuccess(content=content1),
                toolcall_arguments=None,
            )
            
            tool_call1 = ToolCallMessage(
                function_name="test_tool1",
                function_arguments={},
                assert_success=False,
                with_secret=None,
            )
            
            result1, skip_handle1 = await self.toolcall_processor._tool_result_token_management(
                tool_call1, 1, tool_result1
            )
            
            self.assertFalse(skip_handle1)
            
            # 第二个长工具（略大于1000限制）
            content2 = "x" * 11000  # 约1375 tokens，大于1000限制
            tool_result2 = ToolCallResultMessage(
                tool_name="test_tool2",
                tool_index=2,
                result=ToolResultSuccess(content=content2),
                toolcall_arguments=None,
            )
            
            tool_call2 = ToolCallMessage(
                function_name="test_tool2",
                function_arguments={},
                assert_success=False,
                with_secret=None,
            )
            
            result2, skip_handle2 = await self.toolcall_processor._tool_result_token_management(
                tool_call2, 2, tool_result2
            )
            
            self.assertTrue(skip_handle2)
            self.assertIsInstance(result2, RuntimeMessage)
            
            # 第三个短工具
            content3 = "x" * 100
            tool_result3 = ToolCallResultMessage(
                tool_name="test_tool3",
                tool_index=3,
                result=ToolResultSuccess(content=content3),
                toolcall_arguments=None,
            )
            
            tool_call3 = ToolCallMessage(
                function_name="test_tool3",
                function_arguments={},
                assert_success=False,
                with_secret=None,
            )
            
            result3, skip_handle3 = await self.toolcall_processor._tool_result_token_management(
                tool_call3, 3, tool_result3
            )
            
            self.assertFalse(skip_handle3)

    async def test_on_tool_result_replacement(self):
        """测试当on_tool_result回调返回RuntimeMessage时使用替换内容。"""
        # 模拟on_tool_result返回RuntimeMessage
        replacement_message = RuntimeMessage("替换后的消息")
        self.mock_agent.lifecycle.trigger_on_tool_result = AsyncMock(return_value=replacement_message)
        
        content = "x" * 100
        tool_result = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=1,
            result=ToolResultSuccess(content=content),
            toolcall_arguments=None,
        )
        
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=False,
            with_secret=None,
        )
        
        with patch('linhai.agent.conversation.get_current_conversation', return_value=self.mock_conversation):
            result, skip_handle = await self.toolcall_processor._tool_result_token_management(
                tool_call, 1, tool_result
            )
            
            self.assertFalse(skip_handle)
            self.assertEqual(result, replacement_message)


if __name__ == "__main__":
    unittest.main()