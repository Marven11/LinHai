"""Unit tests for parsed_message module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from linhai.parsed_message import ParsedAnswer, Segment
from linhai.llm import Answer
from linhai.agent.lifecycle import Lifecycle


class MockAnswer(Answer):
    """Mock implementation of Answer for testing."""

    def __init__(self, tokens):
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

    def get_message(self):
        content = "".join(tok.get("content", "") for tok in self.tokens)
        from linhai.llm import AssistantMessage
        return AssistantMessage(message=content)

    def get_current_content(self):
        return "".join(tok.get("content", "") for tok in self.tokens[: self.index])

    def interrupt(self):
        pass


class TestParsedAnswer(unittest.IsolatedAsyncioTestCase):
    """Test cases for ParsedAnswer."""

    async def test_adjacent_token_merging(self):
        """Test that adjacent tokens of same type are merged."""
        lifecycle = MagicMock(spec=Lifecycle)
        lifecycle.trigger_before_parsing = AsyncMock()
        lifecycle.trigger_after_segment = AsyncMock()
        lifecycle.trigger_after_token_generation = AsyncMock(return_value=False)
        lifecycle.trigger_after_parsing = AsyncMock()

        agent = MagicMock()

        # Simulate tokens: two normal tokens, one toolcall, then another normal
        tokens = [
            {"reasoning_content": None, "content": "Hello "},
            {"reasoning_content": None, "content": "world! "},
            {"reasoning_content": None, "content": "```json toolcall\n{}"},
            {"reasoning_content": None, "content": "After tool"},
        ]
        answer = MockAnswer(tokens)

        # Mock token parser to return parsed tokens
        from linhai.cli.token_parser import TokenParser
        parser = TokenParser()
        # We'll mock the receive_token to return appropriate parsed tokens
        # For simplicity, we'll directly use the parser and assume it works
        # In real test, we might need to mock it differently
        
        parsed = ParsedAnswer(answer, lifecycle, agent)
        # Replace token_parser with a mock that returns controlled parsed tokens
        parsed.token_parser = MagicMock()
        # Simulate parsed tokens: first two are "normal", third is "toolcall", fourth is "normal"
        parsed.token_parser.receive_token = MagicMock(side_effect=[
            [{"token_type": "normal", "content": "Hello "}],
            [{"token_type": "normal", "content": "world! "}],
            [{"token_type": "toolcall", "content": "```json toolcall\n{}"}],
            [{"token_type": "normal", "content": "After tool"}],
        ])
        parsed.token_parser.clear = MagicMock(return_value=[])

        segments = []
        async def mock_put(segment):
            segments.append(segment)
        parsed.segment_queue.put = AsyncMock(side_effect=mock_put)

        await parsed.start_parsing()
        await parsed.wait_parsing()

        # Should have 3 segments: combined normal, toolcall, normal
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0]["segment_type"], "normal")
        self.assertEqual(segments[0]["content"], "Hello world! ")
        self.assertEqual(segments[1]["segment_type"], "toolcall")
        self.assertEqual(segments[2]["segment_type"], "normal")
        self.assertEqual(segments[2]["content"], "After tool")

        # Verify lifecycle callbacks were called
        lifecycle.trigger_before_parsing.assert_called_once_with(parsed)
        self.assertEqual(lifecycle.trigger_after_segment.call_count, 3)
        lifecycle.trigger_after_parsing.assert_called_once_with(parsed)

    async def test_interrupt(self):
        """Test interrupt functionality."""
        lifecycle = MagicMock(spec=Lifecycle)
        lifecycle.trigger_before_parsing = AsyncMock()
        lifecycle.trigger_after_segment = AsyncMock()
        lifecycle.trigger_after_token_generation = AsyncMock(return_value=False)
        lifecycle.trigger_after_parsing = AsyncMock()

        agent = MagicMock()
        tokens = [
            {"reasoning_content": None, "content": "First"},
            {"reasoning_content": None, "content": "Second"},
        ]
        answer = MockAnswer(tokens)
        parsed = ParsedAnswer(answer, lifecycle, agent)
        parsed.token_parser = MagicMock()
        parsed.token_parser.receive_token = MagicMock(return_value=[{"token_type": "normal", "content": "First"}])
        parsed.token_parser.clear = MagicMock(return_value=[])

        segments = []
        async def mock_put(segment):
            segments.append(segment)
        parsed.segment_queue.put = AsyncMock(side_effect=mock_put)

        task = asyncio.create_task(parsed.start_parsing())
        # Give it a moment to start
        await asyncio.sleep(0.01)
        parsed.interrupt()
        await task

        # Should have received at least one segment (maybe)
        # Interrupt should stop parsing
        self.assertTrue(parsed.interrupted)


if __name__ == "__main__":
    unittest.main()