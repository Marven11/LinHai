"""Unit tests for LLM switching functionality."""

import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.agent import Agent, AgentConfig
from linhai.llm import ChatMessage


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
        from linhai.group_chat import GroupChat

        self.group_chat = GroupChat()

        # 注册必要的队列
        self.group_chat.register_queue("cli_user_output")

        # 创建ToolManager实例
        from linhai.tool.main import ToolManager
        from linhai.tool.base import global_tools

        self.tool_manager = ToolManager(
            group_chat=self.group_chat, toolsets=[global_tools]
        )

        # 创建初始消息列表
        from linhai.llm import SystemMessage

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

    async def test_current_llm_tool(self):
        """Test current_llm tool functionality."""
        # 调用current_llm工具
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(function_name="current_llm", function_arguments={})

        # 调用工具
        result = await self.agent.call_tool(tool_call)

        # 验证工具调用成功
        self.assertFalse(result)  # 不需要早期返回

        # 验证消息中包含当前LLM信息
        self.assertTrue(
            any("当前使用的LLM: primary" in str(msg) for msg in self.agent.messages)
        )

    async def test_switch_llm_tool_success(self):
        """Test successful LLM switching."""
        # 调用switch_llm工具切换到secondary
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(
            function_name="switch_llm", function_arguments={"llm_name": "secondary"}
        )

        # 调用工具
        result = await self.agent.call_tool(tool_call)

        # 验证工具调用成功
        self.assertFalse(result)  # 不需要早期返回

        # 验证LLM索引已更新
        self.assertEqual(self.agent.config["current_llm_index"], 1)

        # 验证消息中包含切换成功信息
        self.assertTrue(
            any("已切换到LLM: secondary" in str(msg) for msg in self.agent.messages)
        )

    async def test_switch_llm_tool_failure(self):
        """Test LLM switching with non-existent LLM."""
        # 调用switch_llm工具切换到不存在的LLM
        from linhai.llm import ToolCallMessage

        tool_call = ToolCallMessage(
            function_name="switch_llm", function_arguments={"llm_name": "nonexistent"}
        )

        # 调用工具
        result = await self.agent.call_tool(tool_call)

        # 验证工具调用成功（返回False表示不需要早期返回，但有错误消息）
        self.assertFalse(result)

        # 验证LLM索引未改变
        self.assertEqual(self.agent.config["current_llm_index"], 0)

        # 验证消息中包含错误信息
        self.assertTrue(
            any(
                "错误：LLM名称 'nonexistent' 不存在" in str(msg)
                for msg in self.agent.messages
            )
        )
        self.assertTrue(
            any(
                "可用的LLM包括: primary, secondary" in str(msg)
                for msg in self.agent.messages
            )
        )

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
