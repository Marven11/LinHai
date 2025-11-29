"""测试Answer的truncate功能。"""

import unittest
from unittest.mock import MagicMock, AsyncMock
from linhai.llm import OpenAiAnswer


class TestAnswerTruncate(unittest.IsolatedAsyncioTestCase):
    """测试Answer的truncate功能。"""

    async def test_truncate_sets_truncated_flag_not_interrupted(self):
        """测试truncate会设置truncated标志但不设置interrupted标志。"""
        mock_stream = MagicMock()
        answer = OpenAiAnswer(mock_stream)
        
        # 调用truncate
        answer.truncate()
        
        # 验证truncated被设置
        self.assertTrue(answer.truncated)
        
        # 验证interrupted没有被设置
        self.assertFalse(answer.interrupted)

    async def test_interrupt_sets_interrupted_flag(self):
        """测试interrupt会设置interrupted标志。"""
        mock_stream = MagicMock()
        answer = OpenAiAnswer(mock_stream)
        
        # 调用interrupt
        answer.interrupt()
        
        # 验证interrupted被设置
        self.assertTrue(answer.interrupted)

    async def test_truncate_preserves_content(self):
        """测试truncate会保留已经生成的内容。"""
        mock_stream = MagicMock()
        mock_stream.__anext__ = AsyncMock(side_effect=[
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content="test", reasoning_content=None))],
                usage=None
            ),
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content=" content", reasoning_content=None))],
                usage=None
            ),
            StopAsyncIteration()
        ])
        
        answer = OpenAiAnswer(mock_stream)
        
        # 获取一些token
        tokens = []
        async for token in answer:
            tokens.append(token)
            if len(tokens) >= 2:
                break
        
        # 验证已经获取了内容
        self.assertEqual(answer.get_current_content(), "test content")
        
        # 调用truncate
        answer.truncate()
        
        # 验证内容仍然被保留
        self.assertEqual(answer.get_current_content(), "test content")
        
        # 验证truncated被设置
        self.assertTrue(answer.truncated)

    async def test_truncate_stops_further_generation(self):
        """测试truncate会阻止后续生成，但保留已生成的内容。"""
        mock_stream = MagicMock()
        mock_stream.__anext__ = AsyncMock(side_effect=[
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content='```json toolcall', reasoning_content=None))],
                usage=None
            ),
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content='\n{"name": "test_tool", "arguments": {}}\n```', reasoning_content=None))],
                usage=None
            ),
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content='不应该出现的后续内容', reasoning_content=None))],
                usage=None
            ),
            StopAsyncIteration()
        ])
        
        answer = OpenAiAnswer(mock_stream)
        
        # 获取前两个token（工具调用）
        tokens = []
        async for token in answer:
            tokens.append(token)
            if len(tokens) >= 2:
                break
        
        # 验证已经获取了工具调用内容
        self.assertIn('```json toolcall', answer.get_current_content())
        self.assertIn('test_tool', answer.get_current_content())
        
        # 调用truncate
        answer.truncate()
        
        # 验证内容被保留
        self.assertIn('```json toolcall', answer.get_current_content())
        self.assertIn('test_tool', answer.get_current_content())
        self.assertNotIn('不应该出现的后续内容', answer.get_current_content())
        
        # 验证truncated被设置
        self.assertTrue(answer.truncated)
        
        # 验证后续迭代会立即触发StopAsyncIteration
        with self.assertRaises(StopAsyncIteration):
            await answer.__anext__()
        
        # 验证interrupted没有被设置
        self.assertFalse(answer.interrupted)


if __name__ == "__main__":
    unittest.main()
