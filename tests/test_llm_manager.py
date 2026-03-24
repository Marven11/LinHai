import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from datetime import datetime, timedelta
from linhai.llm_manager import LlmManager, NoAvailableLlmError
from linhai.group_chat import GroupChat
from linhai.llm import Message, Answer


class MockAnswer(Answer):
    def __init__(self):
        self.interrupted = False
        self.message = MagicMock()
        self.message.message = "test answer"

    def interrupt(self):
        self.interrupted = True

    def get_message(self):
        return self.message

    def get_current_content(self):
        return "test content"


class TestLlmManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_group_chat = MagicMock(spec=GroupChat)
        self.mock_group_chat.send_if_exists = AsyncMock()
        self.mock_group_chat.register_member = MagicMock()

        self.mock_llm1 = MagicMock()
        self.mock_llm1.get_name = MagicMock(return_value="llm1")
        self.mock_llm1.get_token_limit = MagicMock(return_value=8000)
        self.mock_llm1.support_image = MagicMock(return_value=True)
        self.mock_llm1.answer_stream = AsyncMock(return_value=MockAnswer())

        self.mock_llm2 = MagicMock()
        self.mock_llm2.get_name = MagicMock(return_value="llm2")
        self.mock_llm2.get_token_limit = MagicMock(return_value=16000)
        self.mock_llm2.support_image = MagicMock(return_value=False)
        self.mock_llm2.answer_stream = AsyncMock(return_value=MockAnswer())

        self.llm_manager = LlmManager(
            group_chat=self.mock_group_chat,
            llms=[self.mock_llm1, self.mock_llm2],
            default_llm_name="llm1",
            llm_fallback_map={"llm1": "llm2"},
        )

    def test_initialization(self):
        self.assertEqual(self.llm_manager.llm_names, ["llm1", "llm2"])
        self.assertEqual(self.llm_manager.default_llm_name, "llm1")
        self.assertEqual(self.llm_manager.llm_fallback_map["llm1"], "llm2")
        self.assertEqual(self.llm_manager.llm_fallback_map["llm2"], None)
        self.assertEqual(len(self.llm_manager.llm_stack), 1)
        self.assertEqual(self.llm_manager.llm_stack[0][0], "llm1")
        self.assertIsNone(self.llm_manager.llm_stack[0][1])

    def test_get_current_llm(self):
        current_llm = self.llm_manager.get_current_llm()
        self.assertEqual(current_llm, self.mock_llm1)

    async def test_switch_to_llm(self):
        await self.llm_manager.switch_to_llm("llm2")
        self.assertEqual(len(self.llm_manager.llm_stack), 1)
        self.assertEqual(self.llm_manager.llm_stack[0][0], "llm2")
        self.assertIsNone(self.llm_manager.llm_stack[0][1])
        self.mock_group_chat.send_if_exists.assert_called()

    async def test_switch_to_llm_invalid(self):
        with self.assertRaises(ValueError) as context:
            await self.llm_manager.switch_to_llm("nonexistent")
        self.assertIn("nonexistent", str(context.exception))

    async def test_answer_stream_success(self):
        history = [MagicMock(spec=Message)]
        answer = await self.llm_manager.answer_stream(history)
        self.assertIsInstance(answer, MockAnswer)
        self.mock_llm1.answer_stream.assert_called_once_with(history)

    async def test_answer_stream_fallback_on_429(self):
        call_count = 0

        async def mock_answer_stream_fail_first(history):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 Too Many Requests")
            return MockAnswer()

        self.mock_llm1.answer_stream = AsyncMock(
            side_effect=mock_answer_stream_fail_first
        )
        self.mock_llm2.answer_stream = AsyncMock(return_value=MockAnswer())

        history = [MagicMock(spec=Message)]
        answer = await self.llm_manager.answer_stream(history)
        self.assertIsInstance(answer, MockAnswer)
        self.assertEqual(self.mock_llm1.answer_stream.call_count, 1)
        self.assertEqual(self.mock_llm2.answer_stream.call_count, 1)
        self.assertEqual(len(self.llm_manager.llm_stack), 2)
        self.assertEqual(self.llm_manager.llm_stack[0][0], "llm1")
        self.assertEqual(self.llm_manager.llm_stack[1][0], "llm2")

    async def test_answer_stream_fallback_on_network_error(self):
        call_count = 0

        async def mock_answer_stream_fail_first(history):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("connection error")
            return MockAnswer()

        self.mock_llm1.answer_stream = AsyncMock(
            side_effect=mock_answer_stream_fail_first
        )
        self.mock_llm2.answer_stream = AsyncMock(return_value=MockAnswer())

        history = [MagicMock(spec=Message)]
        answer = await self.llm_manager.answer_stream(history)
        self.assertIsInstance(answer, MockAnswer)
        self.assertEqual(self.mock_llm1.answer_stream.call_count, 1)
        self.assertEqual(self.mock_llm2.answer_stream.call_count, 1)
        self.assertEqual(len(self.llm_manager.llm_stack), 2)

    async def test_answer_stream_no_fallback_retry_on_429(self):
        call_count = 0

        async def mock_answer_stream_fail_then_succeed(history):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("429 Too Many Requests")
            return MockAnswer()

        self.mock_llm1.answer_stream = AsyncMock(
            side_effect=mock_answer_stream_fail_then_succeed
        )

        llm_manager_no_fallback = LlmManager(
            group_chat=self.mock_group_chat,
            llms=[self.mock_llm1, self.mock_llm2],
            default_llm_name="llm1",
            llm_fallback_map={"llm1": None},
        )

        history = [MagicMock(spec=Message)]
        answer = await llm_manager_no_fallback.answer_stream(history)
        self.assertIsInstance(answer, MockAnswer)
        self.assertEqual(call_count, 3)
        self.assertEqual(len(llm_manager_no_fallback.llm_stack), 1)

    async def test_answer_stream_timeout_retry(self):
        call_count = 0

        async def mock_answer_stream_timeout_once(history):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError("timeout")
            return MockAnswer()

        self.mock_llm1.answer_stream = AsyncMock(
            side_effect=mock_answer_stream_timeout_once
        )

        history = [MagicMock(spec=Message)]
        answer = await self.llm_manager.answer_stream(history)
        self.assertIsInstance(answer, MockAnswer)
        self.assertEqual(call_count, 2)

    async def test_stack_cleanup_expired_llms(self):
        future_time = datetime.now() + timedelta(seconds=1)
        self.llm_manager.llm_stack.append(("llm2", future_time))
        self.assertEqual(len(self.llm_manager.llm_stack), 2)

        self.llm_manager._cleanup_expired_llms()
        self.assertEqual(len(self.llm_manager.llm_stack), 2)

        await asyncio.sleep(1.1)
        self.llm_manager._cleanup_expired_llms()
        self.assertEqual(len(self.llm_manager.llm_stack), 1)
        self.assertEqual(self.llm_manager.llm_stack[0][0], "llm1")

    async def test_get_current_llm_after_cleanup(self):
        future_time = datetime.now() + timedelta(seconds=1)
        self.llm_manager.llm_stack.append(("llm2", future_time))
        self.assertEqual(len(self.llm_manager.llm_stack), 2)

        await asyncio.sleep(1.1)
        current_llm = self.llm_manager.get_current_llm()
        self.assertEqual(current_llm, self.mock_llm1)
        self.assertEqual(len(self.llm_manager.llm_stack), 1)

    async def test_switch_to_llm_clears_stack(self):
        future_time = datetime.now() + timedelta(seconds=1)
        self.llm_manager.llm_stack.append(("llm2", future_time))
        self.assertEqual(len(self.llm_manager.llm_stack), 2)

        await self.llm_manager.switch_to_llm("llm2")
        self.assertEqual(len(self.llm_manager.llm_stack), 1)
        self.assertEqual(self.llm_manager.llm_stack[0][0], "llm2")

    def test_record_error(self):
        initial_count = len(self.llm_manager.llm_errors["llm1"])
        self.llm_manager._record_error("llm1", "test_error")
        self.assertEqual(len(self.llm_manager.llm_errors["llm1"]), initial_count + 1)

    def test_is_llm_expired(self):
        self.assertFalse(self.llm_manager._is_llm_expired(None))
        self.assertFalse(
            self.llm_manager._is_llm_expired(datetime.now() + timedelta(minutes=10))
        )
        self.assertTrue(
            self.llm_manager._is_llm_expired(datetime.now() - timedelta(minutes=1))
        )

    def test_get_fallback_llm(self):
        self.assertEqual(self.llm_manager._get_fallback_llm("llm1"), "llm2")
        self.assertIsNone(self.llm_manager._get_fallback_llm("llm2"))

    def test_list_available_llms(self):
        result = self.llm_manager.list_available_llms()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "llm1")
        self.assertEqual(result[0]["is_current"], True)
        self.assertEqual(result[1]["name"], "llm2")
        self.assertEqual(result[1]["is_current"], False)

    async def test_empty_history_raises_error(self):
        with self.assertRaises(ValueError) as context:
            await self.llm_manager.answer_stream([])
        self.assertIn("empty", str(context.exception).lower())

    async def test_unexpected_error_propagates(self):
        self.mock_llm1.answer_stream = AsyncMock(
            side_effect=ValueError("unexpected error")
        )
        history = [MagicMock(spec=Message)]
        with self.assertRaises(ValueError) as context:
            await self.llm_manager.answer_stream(history)
        self.assertIn("unexpected error", str(context.exception))

    async def test_fallback_chain(self):
        mock_llm3 = MagicMock()
        mock_llm3.get_name = MagicMock(return_value="llm3")
        mock_llm3.get_token_limit = MagicMock(return_value=32000)
        mock_llm3.support_image = MagicMock(return_value=False)
        mock_llm3.answer_stream = AsyncMock(return_value=MockAnswer())

        llm_manager_chain = LlmManager(
            group_chat=self.mock_group_chat,
            llms=[self.mock_llm1, self.mock_llm2, mock_llm3],
            default_llm_name="llm1",
            llm_fallback_map={"llm1": "llm2", "llm2": "llm3"},
        )

        call_count1 = 0
        call_count2 = 0

        async def mock_llm1_fail(history):
            nonlocal call_count1
            call_count1 += 1
            raise Exception("429 Too Many Requests")

        async def mock_llm2_fail(history):
            nonlocal call_count2
            call_count2 += 1
            raise Exception("429 Too Many Requests")

        self.mock_llm1.answer_stream = AsyncMock(side_effect=mock_llm1_fail)
        self.mock_llm2.answer_stream = AsyncMock(side_effect=mock_llm2_fail)

        history = [MagicMock(spec=Message)]
        answer = await llm_manager_chain.answer_stream(history)
        self.assertIsInstance(answer, MockAnswer)
        self.assertEqual(call_count1, 1)
        self.assertEqual(call_count2, 1)
        self.assertEqual(mock_llm3.answer_stream.call_count, 1)
        self.assertEqual(len(llm_manager_chain.llm_stack), 3)


if __name__ == "__main__":
    unittest.main()
