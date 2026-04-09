"""测试Agent的@系统功能。"""

import unittest
from unittest.mock import Mock, AsyncMock, MagicMock

from linhai.agent import Agent
from linhai.agent.command_callback import CommandCallback
from linhai.registry import Registry
from linhai.llm import UserMessage, AssistantMessage
from linhai.agent.messages import RuntimeMessage


class TestAgentAtSystem(unittest.IsolatedAsyncioTestCase):
    """测试Agent的@系统功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = Mock(spec=Registry)
        self.mock_cli_app = Mock()
        self.mock_container = Mock()
        self.mock_cli_app.query_one = Mock(return_value=self.mock_container)
        self.mock_cli_app.should_auto_scroll = Mock(return_value=True)

        # 创建lifecycle的mock，用于add_new_message中的回调
        self.lifecycle_mock = Mock()

        async def trigger_before_add_new_message_coroutine(msg):
            return None

        self.lifecycle_mock.before_add_new_message.trigger = (
            trigger_before_add_new_message_coroutine
        )
        self.command_callback = CommandCallback(self.registry)

        async def trigger_after_parsed_user_message_side_effect(parsed):
            return await self.command_callback(parsed)

        self.lifecycle_mock.after_parsed_user_message.trigger = AsyncMock(
            side_effect=trigger_after_parsed_user_message_side_effect
        )

        def get_member_typechecked_side_effect(name, cls):
            if name == "tui_app":
                return self.mock_cli_app
            elif name == "agent":
                return self.agent
            elif name == "conversation_folder":
                from pathlib import Path
                from tempfile import TemporaryDirectory

                self.temp_dir = TemporaryDirectory()
                self.addCleanup(self.temp_dir.cleanup)
                return Path(self.temp_dir.name)
            elif name == "lifecycle":
                return self.lifecycle_mock
            elif name == "llm_manager":
                return self.llm_manager
            else:
                return Mock()

        self.registry.get_member_typechecked = Mock(
            side_effect=get_member_typechecked_side_effect
        )
        # 确保registry有register_member方法，避免Agent初始化时出错
        self.registry.register_member = Mock()
        self.registry.has_member = Mock(return_value=True)

        self.mock_llm1 = MagicMock()
        self.mock_llm1.get_name = MagicMock(return_value="deepseek-reasoning")
        self.mock_llm2 = MagicMock()
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

        from linhai.llm_manager import LlmManager

        self.llm_manager = LlmManager(
            registry=self.registry,
            llms=self.config["llms"],
            default_llm_name=self.config["llm_names"][self.config["current_llm_index"]],
            llm_fallback_map={"deepseek-reasoning": None, "qwen": None},
            llm_fallback_duration_map={"deepseek-reasoning": 120, "qwen": 120},
        )

        self.agent = Agent(
            llm_manager=self.llm_manager,
            compress_threshold=self.config["compress_threshold"],
            registry=self.registry,
            pinned_messages=[],
        )

    async def testget_current_model_with_at_system_valid(self):
        """测试有效的@系统调用。"""
        user_message = UserMessage(message="@qwen 你好")
        self.registry.receive = AsyncMock(return_value=user_message)
        await self.agent.user_message_handler.receive_and_dispatch()

        selected_model = self.agent.get_current_model()

        self.assertEqual(selected_model, self.mock_llm2)

    async def testget_current_model_with_at_system_invalid(self):
        """测试无效的@系统调用。"""
        user_message = UserMessage(message="@invalid_llm 你好")
        self.registry.receive = AsyncMock(return_value=user_message)
        await self.agent.user_message_handler.receive_and_dispatch()

        selected_model = self.agent.get_current_model()

        self.assertEqual(selected_model, self.mock_llm1)

    async def testget_current_model_without_at_system(self):
        """测试没有@系统的默认行为。"""
        user_message = UserMessage(message="你好")
        await self.agent.message_processor.add_new_message(user_message)

        selected_model = self.agent.get_current_model()

        self.assertEqual(selected_model, self.mock_llm1)

    async def testget_current_model_with_at_in_middle(self):
        """测试消息中间包含@的情况。"""
        user_message = UserMessage(message="请@llm2回答这个问题")
        await self.agent.message_processor.add_new_message(user_message)

        selected_model = self.agent.get_current_model()

        self.assertEqual(selected_model, self.mock_llm1)

    async def testget_current_model_with_empty_at(self):
        """测试只有@的情况。"""
        user_message = UserMessage(message="@")
        await self.agent.message_processor.add_new_message(user_message)

        selected_model = self.agent.get_current_model()

        self.assertEqual(selected_model, self.mock_llm1)


if __name__ == "__main__":
    unittest.main()
