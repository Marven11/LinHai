import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from typing import TypedDict

from linhai.agent import Agent, AgentConfig
from linhai.llm import ChatMessage
from linhai.queue import Queue


# 定义模拟的 AnswerToken 和 Answer
class MockAnswerToken(TypedDict):
    reasoning_content: str | None
    content: str


class MockAnswer:
    def __init__(self, tokens: list[MockAnswerToken]):
        self.tokens = tokens
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.tokens):
            raise StopAsyncIteration
        token = self.tokens[self.index]
        self.index += 1
        return token

    def get_message(self) -> ChatMessage:
        content = "".join(token["content"] for token in self.tokens)
        return ChatMessage(role="assistant", message=content)


class TestAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock(return_value=AsyncMock())

        config = AgentConfig(
            {"system_prompt": "Test system prompt", "model": self.mock_llm}
        )
        self.queues = {
            "user_input_queue": Queue(),
            "user_output_queue": Queue(),
            "tool_input_queue": Queue(),
            "tool_output_queue": Queue(),
        }
        self.agent = Agent(config, **self.queues)

    async def test_initial_state(self):
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_handle_user_message(self):
        # Setup
        test_msg = ChatMessage(role="user", message="Hello", name="test_user")

        # 模拟 answer_stream 返回一个 MockAnswer
        mock_answer = MockAnswer(
            [
                {"reasoning_content": "Thinking...", "content": "Hi"},
                {"reasoning_content": None, "content": " there"},
            ]
        )
        self.mock_llm.answer_stream.return_value = mock_answer

        # Test
        await self.agent.handle_user_message(test_msg)

        # 验证 user_output_queue 收到了正确的 tokens 和最终 Answer
        tokens = []
        final_answer = None

        while not self.agent.user_output_queue.empty():
            item = await self.agent.user_output_queue.get()
            if isinstance(item, dict):  # AnswerToken
                tokens.append(item)
            elif hasattr(item, "get_message"):  # 通过鸭子类型检查 Answer 对象
                final_answer = item

        # 验证 token 内容
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0]["content"], "Hi")
        self.assertEqual(tokens[1]["content"], " there")

        # 验证最终 Answer 对象
        self.assertIsNotNone(final_answer, "Final Answer object not found")
        assert final_answer is not None  # 让Pylance识别类型
        self.assertEqual(final_answer.get_message().message, "Hi there")

        # 验证上下文更新
        self.assertEqual(self.agent.task_context["last_user_message"], "Hello")
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_state_transitions(self):
        # Test state transitions
        self.agent.state = "working"
        self.assertEqual(self.agent.state, "working")

        self.agent.state = "paused"
        self.assertEqual(self.agent.state, "paused")

    async def test_message_processing(self):
        # Setup
        user_msg = ChatMessage(role="user", message="Hi", name="user")
        tool_msg = ChatMessage(role="tool", message="result", name="tool_call_123")

        # 创建MockAnswer对象并设置LLM mock
        mock_answer = MockAnswer([
            {"reasoning_content": None, "content": "Processing..."}
        ])
        self.mock_llm.answer_stream.return_value = mock_answer

        # Put messages in queues
        await self.agent.user_input_queue.put(user_msg)
        await self.agent.tool_output_queue.put(tool_msg)

        # Start agent in working state
        self.agent.state = "working"
        task = asyncio.create_task(self.agent.state_working())

        # Let it process messages
        await asyncio.sleep(0.5)  # 增加等待时间确保消息被处理

        # 检查模型是否被调用
        self.assertTrue(
            self.mock_llm.answer_stream.called, "answer_stream should be called"
        )

        # 检查消息数组是否包含正确的消息（顺序可能变化）
        # 现在消息数组包含：系统消息 + 用户消息 + 工具消息 + 用户消息处理生成的回复 + 工具消息处理生成的回复
        self.assertEqual(
            len(self.agent.messages),
            5,
            "Should have system + user + tool + user_response + tool_response messages",
        )

        # 查找用户消息
        user_messages = [msg for msg in self.agent.messages if msg.role == "user"]
        self.assertEqual(len(user_messages), 1, "Should have one user message")
        self.assertEqual(user_messages[0].message, "Hi")

        # 查找工具消息
        tool_messages = [msg for msg in self.agent.messages if msg.role == "tool"]
        self.assertEqual(len(tool_messages), 1, "Should have one tool message")
        self.assertIn("result", tool_messages[0].message)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_error_handling(self):
        # Setup error
        self.mock_llm.answer_stream.side_effect = Exception("Test error")
        test_msg = ChatMessage(role="user", message="Error test", name="user")

        # Test
        await self.agent.handle_user_message(test_msg)

        # Verify
        self.assertEqual(self.agent.state, "paused")

    async def test_run_loop(self):
        # Setup
        self.agent.state_waiting_user = AsyncMock()
        self.agent.state_working = AsyncMock()
        self.agent.state_paused = AsyncMock()
        
        # 创建任务引用
        task_ref = None
        
        # 设置state_waiting_user模拟方法，使其在调用时取消任务
        async def mock_state_waiting_user():
            # 取消任务以退出循环
            if task_ref:
                task_ref.cancel()
        
        self.agent.state_waiting_user = AsyncMock(side_effect=mock_state_waiting_user)
        self.agent.state = "waiting_user"

        # 创建并运行任务
        task_ref = asyncio.create_task(self.agent.run())
        
        try:
            # 等待任务完成（会被mock_state_waiting_user取消）
            await asyncio.wait_for(task_ref, timeout=0.5)
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            task_ref.cancel()
            self.fail("测试超时，任务未被取消")

        # 验证state_waiting_user被调用
        self.agent.state_waiting_user.assert_called_once()


if __name__ == "__main__":
    unittest.main()
