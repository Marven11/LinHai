"""Unit tests for LLM switching functionality."""

# pylint: disable=protected-access
import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.agent import Agent, AgentConfig
from linhai.llm import SystemMessage, ToolCallMessage
from linhai.tool.base import ToolErrorMessage, ToolResultMessage
from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager
from linhai.tool.base import global_tools


class TestLLMSwitching(unittest.IsolatedAsyncioTestCase):
    """Test cases for LLM switching tools."""

    def setUp(self):
        # 创建两个模拟LLM
        self.mock_llm1 = MagicMock()
        self.mock_llm1.answer_stream = AsyncMock(return_value=AsyncMock())
        self.mock_llm2 = MagicMock()
        self.mock_llm2.answer_stream = AsyncMock(return_value=AsyncMock())

        config: AgentConfig = {
            "system_prompt": "Test system prompt",
            "llms": [self.mock_llm1, self.mock_llm2],
            "llm_names": ["primary", "secondary"],
            "current_llm_index": 0,
            "compress_threshold_soft": 500,
            "compress_threshold_hard": 800,
            "tool_confirmation": {
                "skip_confirmation": True,
                "whitelist": [],
            },
        }

        # 使用GroupChat架构
        self.group_chat = GroupChat()

        # 注册必要的队列
        self.group_chat.register_queue("cli_agent_output")
        self.group_chat.register_queue("cli_runtime_output")
        
        # 创建并注册ToolManager
        from linhai.tool.tools.terminal import terminal_toolset
        self.tool_manager = ToolManager(group_chat=self.group_chat, toolsets=[global_tools, terminal_toolset])



        # 创建初始消息列表
        init_messages = [
            SystemMessage(
                template="Test system prompt",
                current_time="2025-10-26 17:00:00",
                group_chat=self.group_chat,
            )
        ]

        self.agent = Agent(
            config=config,
            group_chat=self.group_chat,
            init_messages=init_messages,
        )
        # 在Agent创建后获取ToolManager（包含Agent注册的工具）
        self.tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

    async def test_current_llm_tool(self):
        """Test current_llm tool functionality."""
        # 通过ToolManager调用current_llm工具
        tool_call = ToolCallMessage(function_name="current_llm", function_arguments={})

        # 调用工具
        result = await self.tool_manager.process_tool_call(tool_call)

        # 验证工具调用成功并返回ToolResultMessage
        # 如果返回ToolErrorMessage，检查错误内容
        if isinstance(result, ToolErrorMessage):
            self.fail(f"current_llm tool failed: {result.content}")  # type: ignore
        
        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("primary", str(result.content))  # type: ignore

    async def test_switch_llm_tool_success(self):
        """Test successful LLM switching."""
        # 调用switch_llm工具切换到secondary
        tool_call = ToolCallMessage(
            function_name="switch_llm", function_arguments={"llm_name": "secondary"}
        )

        # 通过ToolManager调用工具
        result = await self.tool_manager.process_tool_call(tool_call)

        # 验证工具调用成功并返回ToolResultMessage
        # 如果返回ToolErrorMessage，检查错误内容
        if isinstance(result, ToolErrorMessage):
            self.fail(f"switch_llm tool failed: {result.content}")
        
        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("已切换到LLM: secondary", str(result.content))  # type: ignore

        # 验证LLM索引已更新
        self.assertEqual(self.agent.config["current_llm_index"], 1)

    async def test_switch_llm_tool_failure(self):
        """Test LLM switching with non-existent LLM."""
        # 调用switch_llm工具切换到不存在的LLM
        tool_call = ToolCallMessage(
            function_name="switch_llm", function_arguments={"llm_name": "nonexistent"}
        )

        # 通过ToolManager调用工具
        result = await self.tool_manager.process_tool_call(tool_call)

        # 验证工具调用成功并返回ToolResultMessage
        # 如果返回ToolErrorMessage，检查错误内容
        if isinstance(result, ToolErrorMessage):
            self.fail(f"switch_llm tool failed: {result.content}")
        
        self.assertIsInstance(result, ToolResultMessage)
        self.assertIn("错误：LLM名称 'nonexistent' 不存在", str(result.content))  # type: ignore
        self.assertIn("可用的LLM包括: primary, secondary", str(result.content))  # type: ignore

        # 验证LLM索引未改变
        self.assertEqual(self.agent.config["current_llm_index"], 0)

    async def test_llm_selection(self):
        """Test LLM selection based on current_llm_index."""
        # 初始状态下应该选择第一个LLM
        selected_llm = await self.agent._select_model()
        self.assertEqual(selected_llm, self.mock_llm1)

        # 切换到第二个LLM
        self.agent.config["current_llm_index"] = 1
        selected_llm = await self.agent._select_model()
        self.assertEqual(selected_llm, self.mock_llm2)


if __name__ == "__main__":
    unittest.main()
