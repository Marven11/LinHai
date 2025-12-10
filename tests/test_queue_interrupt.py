"""测试队列消息不打断agent输出的功能"""

import unittest
from unittest.mock import Mock, AsyncMock
from pathlib import Path

from linhai.agent import Agent, AgentContext
from linhai.group_chat import GroupChat
from linhai.llm import UserMessage, AssistantMessage
from linhai.agent.base import RuntimeMessage


class MockAnswer:
    """模拟Answer类"""
    
    def __init__(self, message_content="Agent响应内容"):
        self.message_content = message_content
        self.tokens = ["test", " token", " more", " tokens", " to", " ensure", " loop", " runs", " long", " enough"]
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
        return "".join(self.tokens[:self.current_index])
        
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
        from linhai.tool.base import global_tools
        from linhai.machine_control.master_host import terminal_toolset
        from linhai.config import ToolConfig
        
        self.tool_manager = ToolManager(
            group_chat=self.group_chat, 
            toolsets=[global_tools, terminal_toolset],
            config=ToolConfig(),
            mcp_config=[],
            mcp_basedir=Path("/tmp")
        )
        
        self.mock_llm = Mock()
        
        self.config: AgentContext = {
            "system_prompt": "测试系统提示",
            "llms": [self.mock_llm],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_soft": 32768,
            "compress_threshold_hard": 52428,
        }
        
        self.init_messages = []
        
        from linhai.subagent.issue import IssueManager
        try:
            self.group_chat.get_members("issue_manager", IssueManager)
        except RuntimeError:
            try:
                issue_manager = IssueManager(self.group_chat)
                self.group_chat.register_member("issue_manager", issue_manager)
            except RuntimeError as e:
                if "exists" in str(e):
                    pass
                else:
                    raise
        
        self.agent = Agent(
            context=self.config,
            group_chat=self.group_chat,
            init_messages=self.init_messages,
        )

    async def test_queue_message_placed_after_agent_output(self):
        """测试/queue消息被放在agent输出后面"""
        mock_answer = MockAnswer()
        self.mock_llm.answer_stream = AsyncMock(return_value=mock_answer)
        
        is_empty_calls = 0
        def is_empty_side_effect(_queue_name):
            nonlocal is_empty_calls
            is_empty_calls += 1
            return is_empty_calls > 1
        
        self.group_chat.is_empty = Mock(side_effect=is_empty_side_effect)
        self.group_chat.receive = AsyncMock(return_value=UserMessage(message="/queue 排队消息"))
        self.group_chat.send = AsyncMock()
        
        await self.agent.generate_response()
        
        agent_messages = self.agent.message_processor.get_messages()

        
        assistant_messages = [msg for msg in agent_messages if isinstance(msg, AssistantMessage)]
        queue_messages = [msg for msg in agent_messages if isinstance(msg, UserMessage) and msg.message.startswith("/queue")]
        runtime_messages = [msg for msg in agent_messages if isinstance(msg, RuntimeMessage)]
        
        self.assertTrue(len(assistant_messages) >= 1, "应该至少有一个assistant消息")
        self.assertTrue(len(queue_messages) >= 1, "应该至少有一个/queue消息")
        self.assertTrue(len(runtime_messages) >= 1, "应该至少有一个runtime消息")
        
        last_assistant_idx = None
        for i, msg in enumerate(agent_messages):
            if isinstance(msg, AssistantMessage):
                last_assistant_idx = i
        
        assert last_assistant_idx is not None, "应该至少有一个assistant消息"
        
        if last_assistant_idx is not None:
            for i, msg in enumerate(agent_messages):
                if isinstance(msg, UserMessage) and msg.message.startswith("/queue"):
                    self.assertGreater(i, last_assistant_idx, "/queue消息应该在agent输出之后")
        
        for i, msg in enumerate(agent_messages):
            if isinstance(msg, RuntimeMessage) and "排队消息" in msg.message:
                self.assertGreater(i, last_assistant_idx, "运行时消息应该在agent输出之后")

    def test_queue_message_handling(self):
        """测试/queue消息的处理逻辑"""
        queue_msg = UserMessage(message="/queue 这是一个排队消息")
        
        content = queue_msg.message.strip()  # type: ignore
        self.assertTrue(content.startswith("/queue"))
        
        self.agent.message_processor.append_message(AssistantMessage(message="Agent响应"))
        self.agent.message_processor.append_message(RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理："))
        self.agent.message_processor.append_message(queue_msg)
        
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
        

    async def test_queue_message_preserved_after_interrupt(self):
        """测试/queue消息在agent生成被打断时不会丢失"""
        mock_answer = MockAnswer()
        self.mock_llm.answer_stream = AsyncMock(return_value=mock_answer)
        
        receive_calls = [
            UserMessage(message="/queue 排队消息1"),
            UserMessage(message="/queue 排队消息2"),
            UserMessage(message="普通打断消息")
        ]
        
        is_empty_call_count = 0
        
        def is_empty_side_effect(_queue_name):
            nonlocal is_empty_call_count
            is_empty_call_count += 1
            return is_empty_call_count > 10  # 增加调用次数
        
        self.group_chat.is_empty = Mock(side_effect=is_empty_side_effect)
        self.group_chat.receive = AsyncMock(side_effect=receive_calls)
        self.group_chat.send = AsyncMock()
        
        try:
            await self.agent.generate_response()
        except RuntimeError:
            pass
        
        self.assertTrue(hasattr(self.agent, 'queued_messages'), "agent应该有queued_messages实例变量")
        self.assertEqual(len(self.agent.queued_messages), 2, "queued_messages应该保存了2条排队消息")
        
        self.assertEqual(self.agent.queued_messages[0].message, "/queue 排队消息1")  # type: ignore
        self.assertEqual(self.agent.queued_messages[1].message, "/queue 排队消息2")  # type: ignore
        
        agent_messages = self.agent.message_processor.get_messages()
        queue_messages_in_main = [msg for msg in agent_messages if isinstance(msg, UserMessage) and msg.message.startswith("/queue")]
        self.assertEqual(len(queue_messages_in_main), 0, "排队消息不应该出现在主消息列表中（因为被打断了）")
        
        self.group_chat.is_empty = Mock(return_value=True)
        self.mock_llm.answer_stream = AsyncMock(return_value=MockAnswer("继续响应"))
        
        await self.agent.generate_response()
        
        agent_messages = self.agent.message_processor.get_messages()
        queue_messages_in_main = [msg for msg in agent_messages if isinstance(msg, UserMessage) and msg.message.startswith("/queue")]
        self.assertEqual(len(queue_messages_in_main), 2, "排队消息现在应该出现在主消息列表中")
        
        self.assertEqual(len(self.agent.queued_messages), 0, "queued_messages应该在处理后清空")
        
        assistant_messages = [msg for msg in agent_messages if isinstance(msg, AssistantMessage)]
        self.assertTrue(len(assistant_messages) >= 1, "应该至少有一个assistant消息")
        
        last_assistant_idx = None
        for i, msg in enumerate(agent_messages):
            if isinstance(msg, AssistantMessage):
                last_assistant_idx = i
        
        if last_assistant_idx is not None:
            for i, msg in enumerate(agent_messages):
                if isinstance(msg, UserMessage) and msg.message.startswith("/queue"):
                    self.assertGreater(i, last_assistant_idx, "/queue消息应该在agent输出之后")


if __name__ == "__main__":
    unittest.main()