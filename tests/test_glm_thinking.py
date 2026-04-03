import unittest
from unittest.mock import MagicMock, AsyncMock
from linhai.llm import OpenAi, UserMessage


def _make_openai(
    compatibility: str = "glm", completion_options: dict | None = None
) -> OpenAi:
    llm = OpenAi(
        registry=MagicMock(),
        api_key="test_key",
        base_url="https://api.example.com",
        model="test-model",
        openai_config={},
        chat_completion_kwargs=completion_options or {},
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


class TestGlmThinkingDefaults(unittest.IsolatedAsyncioTestCase):
    async def test_default_extra_body(self):
        llm = _make_openai()
        await llm.answer_stream([UserMessage("hello")])
        args = llm.openai.chat.completions.create.call_args
        self.assertEqual(args.kwargs["extra_body"]["thinking"]["type"], "enabled")
        self.assertFalse(args.kwargs["extra_body"]["thinking"]["clear_thinking"])

    async def test_user_values_not_overwritten(self):
        llm = _make_openai(
            completion_options={
                "extra_body": {
                    "thinking": {
                        "type": "disabled",
                        "clear_thinking": True,
                    }
                }
            }
        )
        await llm.answer_stream([UserMessage("hello")])
        args = llm.openai.chat.completions.create.call_args
        self.assertEqual(args.kwargs["extra_body"]["thinking"]["type"], "disabled")
        self.assertTrue(args.kwargs["extra_body"]["thinking"]["clear_thinking"])

    async def test_type_enabled_without_clear_thinking(self):
        llm = _make_openai(
            completion_options={
                "extra_body": {
                    "thinking": {
                        "type": "enabled",
                    }
                }
            }
        )
        await llm.answer_stream([UserMessage("hello")])
        args = llm.openai.chat.completions.create.call_args
        self.assertEqual(args.kwargs["extra_body"]["thinking"]["type"], "enabled")
        self.assertFalse(args.kwargs["extra_body"]["thinking"]["clear_thinking"])

    async def test_non_glm_not_affected(self):
        llm = _make_openai(compatibility="deepseek")
        await llm.answer_stream([UserMessage("hello")])
        args = llm.openai.chat.completions.create.call_args
        self.assertNotIn("extra_body", args.kwargs)


if __name__ == "__main__":
    unittest.main()
