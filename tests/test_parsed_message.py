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
        content = "".join(tok.content for tok in self.tokens)
        from linhai.llm import AssistantMessage

        return AssistantMessage(message=content)

    def get_current_content(self):
        return "".join(tok.content for tok in self.tokens[: len(self.tokens)])

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
        lifecycle.trigger_after_segment_finished = AsyncMock()

        agent = MagicMock()

        # Simulate tokens: two normal tokens, one toolcall, then another normal
        from linhai.llm import AnswerToken

        tokens = [
            AnswerToken(reasoning_content=None, content="Hello "),
            AnswerToken(reasoning_content=None, content="world! "),
            AnswerToken(reasoning_content=None, content="```json toolcall\n{}"),
            AnswerToken(reasoning_content=None, content="After tool"),
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
        parsed.token_parser.receive_token = MagicMock(
            side_effect=[
                [{"token_type": "normal", "content": "Hello "}],
                [{"token_type": "normal", "content": "world! "}],
                [{"token_type": "toolcall", "content": "```json toolcall\n{}"}],
                [{"token_type": "normal", "content": "After tool"}],
            ]
        )
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
        # trigger_after_segment_finished should be called 3 times: when first normal segment finishes (due to type change to toolcall), when toolcall segment finishes (due to type change to normal), and when parsing finishes (last normal segment)
        self.assertEqual(lifecycle.trigger_after_segment_finished.call_count, 3)
        lifecycle.trigger_after_parsing.assert_called_once_with(parsed)

    async def test_interrupt(self):
        """Test interrupt functionality."""
        lifecycle = MagicMock(spec=Lifecycle)
        lifecycle.trigger_before_parsing = AsyncMock()
        lifecycle.trigger_after_segment = AsyncMock()
        lifecycle.trigger_after_token_generation = AsyncMock(return_value=False)
        lifecycle.trigger_after_parsing = AsyncMock()
        lifecycle.trigger_after_segment_finished = AsyncMock()

        agent = MagicMock()
        from linhai.llm import AnswerToken

        tokens = [
            AnswerToken(reasoning_content=None, content="First"),
            AnswerToken(reasoning_content=None, content="Second"),
        ]
        answer = MockAnswer(tokens)
        parsed = ParsedAnswer(answer, lifecycle, agent)
        parsed.token_parser = MagicMock()
        parsed.token_parser.receive_token = MagicMock(
            return_value=[{"token_type": "normal", "content": "First"}]
        )
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
        # Since interrupt happens before parsing finishes, trigger_after_segment_finished may not be called
        # We don't assert on its call count

    async def test_segment_finished_callbacks(self):
        """Test that trigger_after_segment_finished is called when segment type changes and when parsing finishes."""
        lifecycle = MagicMock(spec=Lifecycle)
        lifecycle.trigger_before_parsing = AsyncMock()
        lifecycle.trigger_after_segment = AsyncMock()
        lifecycle.trigger_after_token_generation = AsyncMock(return_value=False)
        lifecycle.trigger_after_parsing = AsyncMock()
        lifecycle.trigger_after_segment_finished = AsyncMock()

        agent = MagicMock()
        from linhai.llm import AnswerToken

        # Create tokens that cause segment type changes: normal -> toolcall -> normal
        tokens = [
            AnswerToken(reasoning_content=None, content="Normal1"),
            AnswerToken(reasoning_content=None, content="Toolcall start"),
            AnswerToken(reasoning_content=None, content="Normal2"),
        ]
        answer = MockAnswer(tokens)
        parsed = ParsedAnswer(answer, lifecycle, agent)
        parsed.token_parser = MagicMock()
        parsed.token_parser.receive_token = MagicMock(
            side_effect=[
                [{"token_type": "normal", "content": "Normal1"}],
                [{"token_type": "toolcall", "content": "Toolcall start"}],
                [{"token_type": "normal", "content": "Normal2"}],
            ]
        )
        parsed.token_parser.clear = MagicMock(return_value=[])

        segments = []

        async def mock_put(segment):
            segments.append(segment)

        parsed.segment_queue.put = AsyncMock(side_effect=mock_put)

        await parsed.start_parsing()
        await parsed.wait_parsing()

        # Should have 3 segments
        self.assertEqual(len(segments), 3)
        # Verify callback counts
        self.assertEqual(lifecycle.trigger_after_segment.call_count, 3)
        # trigger_after_segment_finished should be called 3 times: when normal segment finishes (due to type change to toolcall), when toolcall segment finishes (due to type change to normal), and when parsing finishes (last normal segment)
        self.assertEqual(lifecycle.trigger_after_segment_finished.call_count, 3)
        # Additionally, verify that trigger_after_segment_finished was called with the correct arguments
        # We can check that it was called with parsed and segment objects
        # The first call should be for the first normal segment
        self.assertEqual(
            lifecycle.trigger_after_segment_finished.call_args_list[0][0][0], parsed
        )
        self.assertEqual(
            lifecycle.trigger_after_segment_finished.call_args_list[0][0][1][
                "segment_type"
            ],
            "normal",
        )
        # The second call should be for the toolcall segment
        self.assertEqual(
            lifecycle.trigger_after_segment_finished.call_args_list[1][0][0], parsed
        )
        self.assertEqual(
            lifecycle.trigger_after_segment_finished.call_args_list[1][0][1][
                "segment_type"
            ],
            "toolcall",
        )
        # The third call should be for the last normal segment (when parsing finishes)
        self.assertEqual(
            lifecycle.trigger_after_segment_finished.call_args_list[2][0][0], parsed
        )
        self.assertEqual(
            lifecycle.trigger_after_segment_finished.call_args_list[2][0][1][
                "segment_type"
            ],
            "normal",
        )
        # Also verify that trigger_after_parsing was called
        lifecycle.trigger_after_parsing.assert_called_once_with(parsed)

    def test_get_toolcalls_normal(self):
        """Test get_toolcalls with valid tool calls."""
        lifecycle = MagicMock(spec=Lifecycle)
        agent = MagicMock()

        # Create mock answer with tool call content
        from linhai.llm import AnswerToken

        tokens = [
            AnswerToken(reasoning_content=None, content="Here is a tool call:\n\n"),
            AnswerToken(
                reasoning_content=None,
                content='```json toolcall\n{"name": "test_tool", "arguments": {"arg1": "value1"}}\n```',
            ),
        ]
        answer = MockAnswer(tokens)
        parsed = ParsedAnswer(answer, lifecycle, agent)

        tool_calls, errors = parsed.get_toolcalls()

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "test_tool")
        self.assertEqual(tool_calls[0]["arguments"], {"arg1": "value1"})
        self.assertEqual(len(errors), 0)

    def test_get_toolcalls_multiple(self):
        """Test get_toolcalls with multiple tool calls."""
        lifecycle = MagicMock(spec=Lifecycle)
        agent = MagicMock()

        from linhai.llm import AnswerToken

        tokens = [
            AnswerToken(reasoning_content=None, content="First tool:\n"),
            AnswerToken(
                reasoning_content=None,
                content='```json toolcall\n{"name": "tool1", "arguments": {"a": 1}}\n```\n',
            ),
            AnswerToken(reasoning_content=None, content="Second tool:\n"),
            AnswerToken(
                reasoning_content=None,
                content='```json toolcall\n{"name": "tool2", "arguments": {"b": 2}}\n```',
            ),
        ]
        answer = MockAnswer(tokens)
        parsed = ParsedAnswer(answer, lifecycle, agent)

        tool_calls, errors = parsed.get_toolcalls()

        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["name"], "tool1")
        self.assertEqual(tool_calls[1]["name"], "tool2")
        self.assertEqual(len(errors), 0)

    def test_get_toolcalls_with_errors(self):
        """Test get_toolcalls with invalid tool calls."""
        lifecycle = MagicMock(spec=Lifecycle)
        agent = MagicMock()

        from linhai.llm import AnswerToken

        tokens = [
            AnswerToken(reasoning_content=None, content="Valid tool:\n"),
            AnswerToken(
                reasoning_content=None,
                content='```json toolcall\n{"name": "valid_tool", "arguments": {}}\n```\n',
            ),
            AnswerToken(reasoning_content=None, content="Invalid tool:\n"),
            AnswerToken(
                reasoning_content=None,
                content='```json toolcall\n{"invalid": "json"}\n```',
            ),
        ]
        answer = MockAnswer(tokens)
        parsed = ParsedAnswer(answer, lifecycle, agent)

        tool_calls, errors = parsed.get_toolcalls()

        # Should have one valid tool call
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["name"], "valid_tool")
        # Should have one error for the invalid tool call
        self.assertEqual(len(errors), 1)
        self.assertIn("缺少必需的'name'字段", errors[0])

    def test_get_toolcalls_empty(self):
        """Test get_toolcalls with empty content."""
        lifecycle = MagicMock(spec=Lifecycle)
        agent = MagicMock()

        from linhai.llm import AnswerToken

        tokens = [
            AnswerToken(
                reasoning_content=None, content="Just a normal message without tools."
            )
        ]
        answer = MockAnswer(tokens)
        parsed = ParsedAnswer(answer, lifecycle, agent)

        tool_calls, errors = parsed.get_toolcalls()

        self.assertEqual(len(tool_calls), 0)
        self.assertEqual(len(errors), 0)

    def test_get_toolcalls_invalid_json(self):
        """Test get_toolcalls with invalid JSON syntax."""
        lifecycle = MagicMock(spec=Lifecycle)
        agent = MagicMock()

        from linhai.llm import AnswerToken

        tokens = [
            AnswerToken(reasoning_content=None, content="Broken tool:\n"),
            AnswerToken(
                reasoning_content=None,
                content='```json toolcall\n{name: "broken", arguments: {}}\n```',
            ),
        ]
        answer = MockAnswer(tokens)
        parsed = ParsedAnswer(answer, lifecycle, agent)

        tool_calls, errors = parsed.get_toolcalls()

        self.assertEqual(len(tool_calls), 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("JSON格式无效", errors[0])


if __name__ == "__main__":
    unittest.main()
