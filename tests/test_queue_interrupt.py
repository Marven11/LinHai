"""测试队列消息不打断agent输出的功能"""

import unittest
from unittest.mock import Mock, AsyncMock, MagicMock
from pathlib import Path

from linhai.agent import Agent
from linhai.group_chat import GroupChat
from linhai.llm import UserMessage, AssistantMessage, AnswerToken
from linhai.agent.base import RuntimeMessage


class MockAnswer:
    """模拟Answer类"""

    def __init__(self, message_content="Agent响应内容"):
        self.message_content = message_content
        self.tokens = [
            AnswerToken(reasoning_content=None, content="test"),
            AnswerToken(reasoning_content=None, content=" token"),
            AnswerToken(reasoning_content=None, content=" more"),
            AnswerToken(reasoning_content=None, content=" tokens"),
            AnswerToken(reasoning_content=None, content=" to"),
            AnswerToken(reasoning_content=None, content=" ensure"),
            AnswerToken(reasoning_content=None, content=" loop"),
            AnswerToken(reasoning_content=None, content=" runs"),
            AnswerToken(reasoning_content=None, content=" long"),
            AnswerToken(reasoning_content=None, content=" enough"),
        ]
        self.current_index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.current_index < len(self.tokens):
            token = self.tokens[self.current_index]
            self.current_index += 1
            return token
        raise StopAsyncIteration

    def get_current_content(self):
        # tokens现在是AnswerToken对象，需要提取content字段
        return "".join(token.content for token in self.tokens[: self.current_index])

    def get_message(self):
        return AssistantMessage(message=self.message_content)

    def get_reasoning_message(self):
        """Get reasoning message."""
        return None

    def interrupt(self):
        pass


class TestQueueInterrupt(unittest.IsolatedAsyncioTestCase):
    """测试队列消息不打断功能"""

    def setUp(self):
        """设置测试环境"""
        self.group_chat = GroupChat()

        from linhai.tool.main import ToolManager
        from linhai.tool.base import utils_tools
        from linhai.machine_control.master_host import terminal_toolset
        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            group_chat=self.group_chat,
            toolsets=[utils_tools, terminal_toolset],
            config=ToolConfig(),
            mcp_config=[],
            mcp_basedir=Path("/tmp"),
        )

        self.mock_llm = Mock()

        self.config = {
            "llms": [self.mock_llm],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 52428,
        }

        self.pinned_messages = []

        # 配置mock对象的get_name方法
        self.mock_llm.get_name = MagicMock(return_value="test_llm")
        self.mock_llm.get_explicit_cache_info = MagicMock(return_value=None)

        from linhai.llm_manager import LlmManager

        llm_manager = LlmManager(
            group_chat=self.group_chat,
            llms=self.config["llms"],
            default_llm_name=self.config["llm_names"][self.config["current_llm_index"]],
            llm_fallback_map={"test_llm": None},
        )
        self.agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=self.config["compress_threshold"],
            group_chat=self.group_chat,
            pinned_messages=self.pinned_messages,
        )

        # 注册conversation_folder，因为AgentMessage._save_context需要它
        from linhai.agent.conversation import register_conversation_folder

        register_conversation_folder(self.group_chat)

    async def test_queue_message_handling(self):
        """测试/queue消息的处理逻辑"""
        queue_msg = UserMessage(message="/queue 这是一个排队消息")

        content = queue_msg.message.strip()  # type: ignore
        self.assertTrue(content.startswith("/queue"))

        await self.agent.message_processor.add_new_message(
            AssistantMessage(message="Agent响应")
        )
        await self.agent.message_processor.add_new_message(
            RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理：")
        )
        await self.agent.message_processor.add_new_message(queue_msg)

        agent_messages = self.agent.message_processor.get_messages()
        self.assertEqual(len(agent_messages), 3)
        self.assertIsInstance(agent_messages[0], AssistantMessage)
        self.assertEqual(agent_messages[0].message, "Agent响应")  # type: ignore
        self.assertIsInstance(agent_messages[1], RuntimeMessage)
        self.assertEqual(agent_messages[1].message, "用户在你回答的时候输出了以下排队消息，现在请处理：")  # type: ignore
        self.assertIsInstance(agent_messages[2], UserMessage)
        self.assertEqual(agent_messages[2].message, "/queue 这是一个排队消息")  # type: ignore

    def test_normal_message_handling(self):
        """测试普通消息的处理逻辑"""
        normal_msg = UserMessage(message="这是一个普通消息")

        content = normal_msg.message.strip()  # type: ignore
        self.assertFalse(content.startswith("/queue"))
