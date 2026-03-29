"""测试Answer的truncate功能。"""

import unittest
from unittest.mock import MagicMock, AsyncMock
from linhai.llm import OpenAiAnswer
from linhai.registry import Registry


class TestAnswerTruncate(unittest.IsolatedAsyncioTestCase):
    """测试Answer的truncate功能。"""

    async def test_truncate_sets_truncated_flag_not_interrupted(self):
        """测试truncate会设置truncated标志但不设置interrupted标志。"""
        mock_stream = MagicMock()
        mock_registry = MagicMock(spec=Registry)
        answer = OpenAiAnswer(
            stream=mock_stream,
            registry=mock_registry,
            compatibility=None,
            estimated_cached_input_tokens=0,
        )

        answer.truncate()

        self.assertTrue(answer.truncated)

        self.assertFalse(answer.interrupted)

    async def test_interrupt_sets_interrupted_flag(self):
        """测试interrupt会设置interrupted标志。"""
        mock_stream = MagicMock()
        mock_registry = MagicMock(spec=Registry)
        answer = OpenAiAnswer(
            stream=mock_stream,
            registry=mock_registry,
            compatibility=None,
            estimated_cached_input_tokens=0,
        )

        answer.interrupt()

        self.assertTrue(answer.interrupted)

    async def test_truncate_preserves_content(self):
        """测试truncate会保留已经生成的内容。"""
        mock_stream = MagicMock()
        mock_stream.__anext__ = AsyncMock(
            side_effect=[
                MagicMock(
                    choices=[
                        MagicMock(delta=MagicMock(content="test", reasoning_content=""))
                    ],
                    usage=None,
                ),
                MagicMock(
                    choices=[
                        MagicMock(
                            delta=MagicMock(content=" content", reasoning_content="")
                        )
                    ],
                    usage=None,
                ),
                StopAsyncIteration(),
            ]
        )
        mock_registry = MagicMock(spec=Registry)
        answer = OpenAiAnswer(
            stream=mock_stream,
            registry=mock_registry,
            compatibility=None,
            estimated_cached_input_tokens=0,
        )

        tokens = []
        async for token in answer:
            tokens.append(token)
            if len(tokens) >= 2:
                break

        self.assertEqual(answer.get_current_content(), "test content")

        answer.truncate()

        self.assertEqual(answer.get_current_content(), "test content")

        self.assertTrue(answer.truncated)

    async def test_truncate_stops_further_generation(self):
        """测试truncate会阻止后续生成，但保留已生成的内容。"""
        mock_stream = MagicMock()
        mock_stream.__anext__ = AsyncMock(
            side_effect=[
                MagicMock(
                    choices=[
                        MagicMock(
                            delta=MagicMock(
                                content="```json toolcall", reasoning_content=""
                            )
                        )
                    ],
                    usage=None,
                ),
                MagicMock(
                    choices=[
                        MagicMock(
                            delta=MagicMock(
                                content='\n{"name": "test_tool", "arguments": {}}\n```',
                                reasoning_content="",
                            )
                        )
                    ],
                    usage=None,
                ),
                MagicMock(
                    choices=[
                        MagicMock(
                            delta=MagicMock(
                                content="不应该出现的后续内容", reasoning_content=""
                            )
                        )
                    ],
                    usage=None,
                ),
                StopAsyncIteration(),
            ]
        )
        mock_registry = MagicMock(spec=Registry)
        answer = OpenAiAnswer(
            stream=mock_stream,
            registry=mock_registry,
            compatibility=None,
            estimated_cached_input_tokens=0,
        )

        tokens = []
        async for token in answer:
            tokens.append(token)
            if len(tokens) >= 2:
                break

        self.assertIn("```json toolcall", answer.get_current_content())
        self.assertIn("test_tool", answer.get_current_content())

        answer.truncate()

        self.assertIn("```json toolcall", answer.get_current_content())
        self.assertIn("test_tool", answer.get_current_content())
        self.assertNotIn("不应该出现的后续内容", answer.get_current_content())

        self.assertTrue(answer.truncated)

        with self.assertRaises(StopAsyncIteration):
            await answer.__anext__()

        self.assertFalse(answer.interrupted)


if __name__ == "__main__":
    unittest.main()
