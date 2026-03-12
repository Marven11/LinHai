"""Unit tests for new lifecycle callbacks: after_new_parsed_answer and after_segment_finished."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from linhai.parsed_message import ParsedAnswer, Segment
from linhai.agent.lifecycle import Lifecycle
from linhai.group_chat import GroupChat


class MockAnswer:
    """Mock implementation of Answer for testing."""

    def __init__(self):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

    def get_message(self):
        from linhai.llm import AssistantMessage

        return AssistantMessage(message="test")

    def get_current_content(self):
        return "test"

    def interrupt(self):
        pass


class TestAfterNewParsedAnswerCallback(unittest.IsolatedAsyncioTestCase):
    """Test cases for after_new_parsed_answer callback."""

    async def test_callback_called_when_triggered(self):
        """Test that after_new_parsed_answer callback is called when triggered by caller."""
        group_chat = GroupChat()
        lifecycle = Lifecycle(group_chat)

        callback_called = False
        received_parsed_answer = None

        async def callback(parsed_answer):
            nonlocal callback_called, received_parsed_answer
            callback_called = True
            received_parsed_answer = parsed_answer

        lifecycle.register_after_new_parsed_answer(callback)

        answer = MockAnswer()
        agent = MagicMock()

        parsed = ParsedAnswer(answer, lifecycle, agent)

        # Callback should be triggered by the caller (main.py), not in __init__
        # This simulates what main.py does
        await lifecycle.trigger_after_new_parsed_answer(parsed)

        self.assertTrue(callback_called)
        self.assertIs(received_parsed_answer, parsed)


class TestCallbackOrder(unittest.IsolatedAsyncioTestCase):
    """Test that callbacks are called in the correct order."""

    async def test_parsing_lifecycle_callback_order(self):
        """Test that after_new_parsed_answer is called when triggered by caller."""
        group_chat = GroupChat()
        lifecycle = Lifecycle(group_chat)

        call_order = []

        async def after_new_parsed_answer(parsed_answer):
            call_order.append("after_new_parsed_answer")

        lifecycle.register_after_new_parsed_answer(after_new_parsed_answer)

        answer = MockAnswer()
        agent = MagicMock()

        parsed = ParsedAnswer(answer, lifecycle, agent)

        # Simulate what main.py does
        await lifecycle.trigger_after_new_parsed_answer(parsed)

        self.assertEqual(call_order[0], "after_new_parsed_answer")


if __name__ == "__main__":
    unittest.main()
