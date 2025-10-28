"""测试Agent的@系统功能。"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock
from linhai.agent import Agent, AgentConfig
from linhai.group_chat import GroupChat
from linhai.llm import ChatMessage
from linhai.agent_base import RuntimeMessage


class TestAgentAtSystem(unittest.IsolatedAsyncioTestCase):
    """测试Agent的@系统功能。"""

    def setUp(self):
        """设置测试环境。"""
        # 创建模拟的GroupChat
        self.group_chat = Mock(spec=GroupChat)
        self.group_chat.get_members = Mock(return_value=Mock())

        # 创建模拟的LLM配置
        self.mock_llm1 = AsyncMock()
        self.mock_llm2 = AsyncMock()

        # 设置answer_stream返回一个空的异步迭代器
        async def empty_answer_stream(messages):
            class EmptyAnswer:
                def __aiter__(self):
                    return self

                async def __anext__(self):
                    raise StopAsyncIteration

                def get_message(self):
                    return ChatMessage(role="assistant", message="")

                def get_current_content(self):
                    return ""

                def get_reasoning_message(self):
                    return None

            return EmptyAnswer()

        self.mock_llm1.answer_stream = empty_answer_stream
        self.mock_llm2.answer_stream = empty_answer_stream

        self.config: AgentConfig = {
            "system_prompt": "测试系统提示",
            "llms": [self.mock_llm1, self.mock_llm2],
            "llm_names": ["llm1", "llm2"],
            "current_llm_index": 0,
            "compress_threshold_hard": 1000,
            "compress_threshold_soft": 500,
            "tool_confirmation": {"skip_confirmation": True},
        }

        # 创建Agent实例
        self.agent = Agent(
            config=self.config, group_chat=self.group_chat, init_messages=[]
        )

    async def test_select_model_with_at_system_valid(self):
        """测试有效的@系统调用。"""
        # 添加一个@llm2的用户消息
        user_message = ChatMessage(role="user", message="@llm2 你好")

        # 调用handle_message，这会更新current_llm_index
        await self.agent.handle_message(user_message)

        # 调用_select_model
        selected_model = await self.agent._select_model()

        # 验证选择了正确的LLM
        self.assertEqual(selected_model, self.mock_llm2)

    async def test_select_model_with_at_system_invalid(self):
        """测试无效的@系统调用。"""
        # 添加一个@invalid_llm的用户消息
        user_message = ChatMessage(role="user", message="@invalid_llm 你好")

        # 调用handle_message，这会添加错误消息
        await self.agent.handle_message(user_message)

        # 调用_select_model
        selected_model = await self.agent._select_model()

        # 验证使用了默认LLM
        self.assertEqual(selected_model, self.mock_llm1)

        # 验证添加了错误消息
        self.assertTrue(
            any(
                isinstance(msg, RuntimeMessage)
                and "错误：LLM名称 'invalid_llm' 不存在" in str(msg)
                for msg in self.agent.messages
            )
        )

    async def test_select_model_without_at_system(self):
        """测试没有@系统的默认行为。"""
        # 添加一个普通用户消息
        user_message = ChatMessage(role="user", message="你好")
        self.agent.messages.append(user_message)

        # 调用_select_model
        selected_model = await self.agent._select_model()

        # 验证使用了默认LLM
        self.assertEqual(selected_model, self.mock_llm1)

    async def test_select_model_with_at_in_middle(self):
        """测试消息中间包含@的情况。"""
        # 添加一个消息中间包含@的用户消息
        user_message = ChatMessage(role="user", message="请@llm2回答这个问题")
        self.agent.messages.append(user_message)

        # 调用_select_model
        selected_model = await self.agent._select_model()

        # 验证使用了默认LLM（因为@不在开头）
        self.assertEqual(selected_model, self.mock_llm1)

    async def test_select_model_with_empty_at(self):
        """测试只有@的情况。"""
        # 添加一个只有@的用户消息
        user_message = ChatMessage(role="user", message="@")
        self.agent.messages.append(user_message)

        # 调用_select_model
        selected_model = await self.agent._select_model()

        # 验证使用了默认LLM
        self.assertEqual(selected_model, self.mock_llm1)


if __name__ == "__main__":
    unittest.main()
