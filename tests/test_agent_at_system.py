"""测试Agent的@系统功能。"""

import unittest
from unittest.mock import Mock, AsyncMock, MagicMock

from linhai.agent import Agent
from linhai.group_chat import GroupChat
from linhai.llm import UserMessage, AssistantMessage
from linhai.agent.base import RuntimeMessage


class TestAgentAtSystem(unittest.IsolatedAsyncioTestCase):
    """测试Agent的@系统功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = Mock(spec=GroupChat)
        self.group_chat.get_members = Mock(return_value=Mock())

        self.mock_llm1 = AsyncMock()
        self.mock_llm1.get_name = MagicMock(return_value="deepseek-reasoning")
        self.mock_llm2 = AsyncMock()
        self.mock_llm2.get_name = MagicMock(return_value="qwen")

        async def empty_answer_stream(_):
            """返回一个空的答案流。"""

            class EmptyAnswer:
                """空的答案流类。"""

                def __aiter__(self):
                    """返回迭代器自身。"""
                    return self

                async def __anext__(self):
                    """引发StopAsyncIteration。"""
                    raise StopAsyncIteration

                def get_message(self):
                    """返回空消息。"""
                    return AssistantMessage(message="")

                def get_current_content(self):
                    """返回空内容。"""
                    return ""

                def get_reasoning_message(self):
                    """返回None。"""
                    return None

            return EmptyAnswer()

        self.mock_llm1.answer_stream = empty_answer_stream
        self.mock_llm2.answer_stream = empty_answer_stream

        self.config = {
            "llms": [self.mock_llm1, self.mock_llm2],
            "llm_names": ["deepseek-reasoning", "qwen"],
            "current_llm_index": 0,
            "compress_threshold": 1000,
        }

        self.agent = Agent(
            llms=self.config["llms"],
            compress_threshold=self.config["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=[],
            llm_name=self.config["llm_names"][self.config["current_llm_index"]],
        )

    async def testget_current_model_with_at_system_valid(self):
        """测试有效的@系统调用。"""
        user_message = UserMessage(message="@qwen 你好")

        await self.agent.handle_user_message(user_message)

        selected_model = await self.agent.get_current_model()

        self.assertEqual(selected_model, self.mock_llm2)

    async def testget_current_model_with_at_system_invalid(self):
        """测试无效的@系统调用。"""
        user_message = UserMessage(message="@invalid_llm 你好")

        await self.agent.handle_user_message(user_message)

        selected_model = await self.agent.get_current_model()

        self.assertEqual(selected_model, self.mock_llm1)

        messages = self.agent.message_processor.get_messages()
        self.assertTrue(
            any(
                isinstance(msg, RuntimeMessage)
                and "错误：用户指定的LLM名称'invalid_llm'不存在，请向用户报告这一点"
                in str(msg)
                for msg in messages
            )
        )

    async def testget_current_model_without_at_system(self):
        """测试没有@系统的默认行为。"""
        user_message = UserMessage(message="你好")
        self.agent.message_processor.add_new_message(user_message)

        selected_model = await self.agent.get_current_model()

        self.assertEqual(selected_model, self.mock_llm1)

    async def testget_current_model_with_at_in_middle(self):
        """测试消息中间包含@的情况。"""
        user_message = UserMessage(message="请@llm2回答这个问题")
        self.agent.message_processor.add_new_message(user_message)

        selected_model = await self.agent.get_current_model()

        self.assertEqual(selected_model, self.mock_llm1)

    async def testget_current_model_with_empty_at(self):
        """测试只有@的情况。"""
        user_message = UserMessage(message="@")
        self.agent.message_processor.add_new_message(user_message)

        selected_model = await self.agent.get_current_model()

        self.assertEqual(selected_model, self.mock_llm1)


if __name__ == "__main__":
    unittest.main()
