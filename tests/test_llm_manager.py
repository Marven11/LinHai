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
            max_retries_per_llm=2,
        )

    def test_initialization(self):
        self.assertEqual(
            self.llm_manager.llm_names[self.llm_manager.current_llm_index], "llm1"
        )
        self.assertEqual(self.llm_manager.get_current_llm(), self.mock_llm1)
        self.assertEqual(self.llm_manager.llm_names, ["llm1", "llm2"])

    async def test_switch_to_llm(self):
        await self.llm_manager.switch_to_llm("llm2")
        self.assertEqual(
            self.llm_manager.llm_names[self.llm_manager.current_llm_index], "llm2"
        )
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

    async def test_answer_stream_timeout_retry(self):
        self.mock_llm1.answer_stream.side_effect = [
            asyncio.TimeoutError("timeout"),
            MockAnswer(),
        ]
        history = [MagicMock(spec=Message)]
        answer = await self.llm_manager.answer_stream(history)
        self.assertIsInstance(answer, MockAnswer)
        self.assertEqual(self.mock_llm1.answer_stream.call_count, 2)

    async def test_answer_stream_rate_limit_switch(self):
        self.mock_llm1.answer_stream.side_effect = Exception("rate limit exceeded")
        history = [MagicMock(spec=Message)]
        answer = await self.llm_manager.answer_stream(history)
        self.assertIsInstance(answer, MockAnswer)
        self.mock_llm1.answer_stream.assert_called_once()
        self.mock_llm2.answer_stream.assert_called_once()

    async def test_answer_stream_all_disabled(self):
        with patch.object(self.llm_manager, "_is_llm_disabled", return_value=True):
            self.mock_llm1.answer_stream.side_effect = Exception("test error")
            history = [MagicMock(spec=Message)]
            with self.assertRaises(RuntimeError) as context:
                await self.llm_manager.answer_stream(history)
            self.assertIn("重试2次后仍无法完成", str(context.exception))

    def test_record_error(self):
        initial_count = len(self.llm_manager.llm_errors["llm1"])
        self.llm_manager._record_error("llm1", "test_error")
        self.assertEqual(len(self.llm_manager.llm_errors["llm1"]), initial_count + 1)

    def test_is_llm_disabled(self):
        self.assertFalse(self.llm_manager._is_llm_disabled("llm1"))

        future_time = datetime.now() + timedelta(minutes=10)
        self.llm_manager.llm_disabled_until["llm1"] = future_time
        self.assertTrue(self.llm_manager._is_llm_disabled("llm1"))

        past_time = datetime.now() - timedelta(minutes=1)
        self.llm_manager.llm_disabled_until["llm1"] = past_time
        self.assertFalse(self.llm_manager._is_llm_disabled("llm1"))

    def test_get_next_available_llm(self):
        llm = self.llm_manager._get_next_available_llm()
        self.assertEqual(llm, self.mock_llm2)
        self.assertEqual(self.llm_manager.current_llm_index, 1)

    def test_list_available_llms(self):
        result = self.llm_manager.list_available_llms()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "llm1")
        self.assertEqual(result[0]["is_current"], True)
        self.assertEqual(result[1]["name"], "llm2")
        self.assertEqual(result[1]["is_current"], False)

    def test_get_token_limit(self):
        limit = self.llm_manager.get_current_llm().get_token_limit()
        self.assertEqual(limit, 8000)

    def test_support_image(self):
        support = self.llm_manager.get_current_llm().support_image()
        self.assertTrue(support)

        self.llm_manager.current_llm_index = 1
        support = self.llm_manager.get_current_llm().support_image()
        self.assertFalse(support)


if __name__ == "__main__":
    unittest.main()
