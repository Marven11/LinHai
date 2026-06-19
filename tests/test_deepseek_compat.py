import unittest
from unittest.mock import MagicMock, AsyncMock
from linhai.base import UserMessage, AssistantMessage
from linhai.llm import OpenAi


def _make_openai(compatibility: str = "deepseek") -> OpenAi:
    llm = OpenAi(
        registry=MagicMock(),
        api_key="test_key",
        base_url="https://api.example.com",
        model="test-model",
        openai_config={},
        chat_completion_kwargs={},
        name="test-llm",
        support_image=False,
        explicit_cache_info=None,
        compatibility=compatibility,
    )
    mock_stream = MagicMock()
    mock_stream.__aiter__ = MagicMock(return_value=iter([]))
    mock_stream.__anext__ = AsyncMock(side_effect=StopAsyncIteration)
    llm.openai = MagicMock()
    llm.openai.chat.completions.create = AsyncMock(return_value=mock_stream)
    return llm


class TestDeepseekEmptyAssistantFix(unittest.IsolatedAsyncioTestCase):
    async def test_empty_assistant_gets_content(self):
        llm = _make_openai(compatibility="deepseek")
        history = [
            UserMessage("hello"),
            AssistantMessage(message=None, reasoning_message="some reasoning"),
            UserMessage("again"),
        ]
        await llm.answer_stream(history)
        args = llm.openai.chat.completions.create.call_args
        messages = args.kwargs["messages"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        self.assertEqual(len(assistant_msgs), 1)
        self.assertEqual(assistant_msgs[0]["content"], "I")

    async def test_assistant_with_content_not_affected(self):
        llm = _make_openai(compatibility="deepseek")
        history = [
            UserMessage("hello"),
            AssistantMessage(message="hello back"),
            UserMessage("again"),
        ]
        await llm.answer_stream(history)
        args = llm.openai.chat.completions.create.call_args
        messages = args.kwargs["messages"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        self.assertEqual(assistant_msgs[0]["content"], "hello back")

    async def test_assistant_with_tool_calls_not_affected(self):
        llm = _make_openai(compatibility="deepseek")
        msg = AssistantMessage(message=None, reasoning_message="reasoning")
        msg.tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "test_tool", "arguments": "{}"},
            }
        ]
        history = [UserMessage("hello"), msg, UserMessage("again")]
        await llm.answer_stream(history)
        args = llm.openai.chat.completions.create.call_args
        messages = args.kwargs["messages"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        self.assertNotIn("content", assistant_msgs[0])
        self.assertIn("tool_calls", assistant_msgs[0])

    async def test_non_deepseek_also_filled(self):
        llm = _make_openai(compatibility="kimi")
        history = [
            UserMessage("hello"),
            AssistantMessage(message=None, reasoning_message="some reasoning"),
            UserMessage("again"),
        ]
        await llm.answer_stream(history)
        args = llm.openai.chat.completions.create.call_args
        messages = args.kwargs["messages"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        self.assertEqual(assistant_msgs[0]["content"], "I")


if __name__ == "__main__":
    unittest.main()
