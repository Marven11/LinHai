import unittest
import asyncio
from datetime import datetime, timedelta
from typing import Sequence, AsyncIterator
from linhai.llm_manager import LlmManager
from linhai.registry import Registry
from linhai.base import (
    Message,
    Answer,
    AnswerToken,
    AnswerTokenUsage,
    AssistantMessage,
    ExplicitCacheInfo,
    OpenAiToolCallToken,
)


class FakeAnswer:
    def __init__(
        self,
        message: str = "test answer",
        reasoning_message: str | None = None,
        token_usage: AnswerTokenUsage | None = None,
    ):
        self._message = message
        self._reasoning_message = reasoning_message
        self._token_usage = token_usage
        self.interrupted = False
        self._content = message
        self._toyield: list[AnswerToken] = [
            AnswerToken(content=token, reasoning_content=None) for token in message
        ]

    def __aiter__(self) -> AsyncIterator[AnswerToken | OpenAiToolCallToken]:
        return self

    async def __anext__(self) -> AnswerToken | OpenAiToolCallToken:
        if not self._toyield:
            raise StopAsyncIteration
        return self._toyield.pop(0)

    def get_message(self) -> Message:
        return AssistantMessage(
            message=self._message,
            reasoning_message=self._reasoning_message,
        )

    def get_reasoning_message(self) -> str | None:
        return self._reasoning_message

    def interrupt(self) -> None:
        self.interrupted = True

    def truncate(self) -> None:
        self.interrupted = True

    def get_current_content(self) -> str | None:
        return self._content

    def get_token_usage(self) -> AnswerTokenUsage | None:
        return self._token_usage

    async def get_openai_toolcalls(self) -> list | None:
        return None


class FakeLLM:
    def __init__(
        self,
        name: str = "fake-llm",
        token_limit: int | None = 8000,
        support_image: bool = False,
        compatibility: str | None = None,
        custom_toolcall_format: bool = True,
        explicit_cache_info: ExplicitCacheInfo | None = None,
        compress_threshold: int | float | None = None,
        success_content: str = "test answer",
        success_token_usage: AnswerTokenUsage | None = None,
        error_sequence: list[Exception] | None = None,
    ):
        self.name = name
        self._token_limit = token_limit
        self._support_image = support_image
        self._compatibility = compatibility
        self._custom_toolcall_format = custom_toolcall_format
        self._explicit_cache_info = explicit_cache_info
        self._compress_threshold = compress_threshold
        self._success_content = success_content
        self._success_token_usage = success_token_usage
        self._error_sequence = error_sequence or []
        self.call_count = 0

    def get_name(self) -> str:
        return self.name

    def get_token_limit(self) -> int | None:
        return self._token_limit

    def support_image(self) -> bool:
        return self._support_image

    def get_compatibility(self) -> str | None:
        return self._compatibility

    def get_custom_toolcall_format(self) -> bool:
        return self._custom_toolcall_format

    def get_explicit_cache_info(self) -> ExplicitCacheInfo | None:
        return self._explicit_cache_info

    def get_compress_threshold(self) -> int | float | None:
        return self._compress_threshold

    def get_description(self) -> str:
        tl = f"{self._token_limit}" if self._token_limit is not None else "未设置"
        return f"名称: {self.name}, 模型: {self.name}, token限制: {tl}"

    async def reconnect(self) -> None:
        pass

    async def answer_stream(self, _history: Sequence[Message]) -> Answer:
        self.call_count += 1
        if self.call_count <= len(self._error_sequence):
            raise self._error_sequence[self.call_count - 1]
        return FakeAnswer(
            message=self._success_content,
            token_usage=self._success_token_usage,
        )


def _make_registry():
    r = Registry()
    r.register_queue("ui_log")
    return r


def _make_llm_manager(registry, llms, **kwargs):
    names = [llm.get_name() for llm in llms]
    fb_map = {n: None for n in names}
    fb_dur = {n: 120 for n in names}
    fb_map.update(kwargs.pop("llm_fallback_map", {}))
    fb_dur.update(kwargs.pop("llm_fallback_duration_map", {}))
    return LlmManager(
        registry=registry,
        llms=llms,
        default_llm_name=kwargs.pop("default_llm_name", None),
        llm_fallback_map=fb_map,
        llm_fallback_duration_map=fb_dur,
        **kwargs,
    )


class TestLlmManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = _make_registry()

        self.llm1 = FakeLLM(
            name="llm1",
            token_limit=8000,
            support_image=True,
        )
        self.llm2 = FakeLLM(
            name="llm2",
            token_limit=16000,
            support_image=False,
        )

        self.llm_manager = _make_llm_manager(
            self.registry,
            [self.llm1, self.llm2],
            llm_fallback_map={"llm1": "llm2"},
        )

    def test_initialization(self):
        self.assertEqual(self.llm_manager.llm_names, ["llm1", "llm2"])
        self.assertEqual(self.llm_manager.default_llm_name, "llm1")
        self.assertEqual(self.llm_manager.llm_fallback_map["llm1"], "llm2")
        self.assertIsNone(self.llm_manager.llm_fallback_map["llm2"])
        self.assertEqual(len(self.llm_manager.llm_stack), 1)
        self.assertEqual(self.llm_manager.llm_stack[0]["llm_name"], "llm1")
        self.assertIsNone(self.llm_manager.llm_stack[0]["disabled_until"])

    def test_get_current_llm(self):
        current = self.llm_manager.get_current_llm()
        self.assertIs(current, self.llm1)

    def test_get_current_llm_without_cleanup(self):
        future_time = datetime.now() + timedelta(seconds=10)
        self.llm_manager.llm_stack.append(
            {"llm_name": "llm2", "disabled_until": future_time, "retry_count": 0}
        )
        current = self.llm_manager.get_current_llm(rotate_invalid_llm=False)
        self.assertIs(current, self.llm2)
        self.assertEqual(len(self.llm_manager.llm_stack), 2)

    async def test_switch_to_llm(self):
        await self.llm_manager.switch_to_llm("llm2")
        self.assertEqual(len(self.llm_manager.llm_stack), 1)
        self.assertEqual(self.llm_manager.llm_stack[0]["llm_name"], "llm2")
        self.assertIsNone(self.llm_manager.llm_stack[0]["disabled_until"])

    async def test_switch_to_llm_invalid(self):
        with self.assertRaises(ValueError) as context:
            await self.llm_manager.switch_to_llm("nonexistent")
        self.assertIn("nonexistent", str(context.exception))

    async def test_answer_stream_success(self):
        from linhai.base import UserMessage

        history = [UserMessage("hello")]
        answer = await self.llm_manager.answer_stream(history)
        self.assertIsInstance(answer, FakeAnswer)
        self.assertEqual(answer.get_message().get_content(), "test answer")
        self.assertEqual(self.llm1.call_count, 1)

    async def test_answer_stream_fallback_on_429(self):
        from linhai.base import UserMessage

        self.llm1._error_sequence = [Exception("429 Too Many Requests")]
        self.llm2._success_content = "fallback answer"

        history = [UserMessage("hello")]
        answer = await self.llm_manager.answer_stream(history)
        msg = answer.get_message()
        assert msg is not None
        self.assertEqual(msg.get_content(), "fallback answer")
        self.assertEqual(self.llm1.call_count, 1)
        self.assertEqual(self.llm2.call_count, 1)
        self.assertEqual(len(self.llm_manager.llm_stack), 2)
        self.assertEqual(self.llm_manager.llm_stack[0]["llm_name"], "llm1")
        self.assertEqual(self.llm_manager.llm_stack[1]["llm_name"], "llm2")

    async def test_answer_stream_fallback_on_network_error(self):
        from linhai.base import UserMessage

        self.llm1._error_sequence = [Exception("connection error")]
        self.llm2._success_content = "fallback answer"

        history = [UserMessage("hello")]
        answer = await self.llm_manager.answer_stream(history)
        self.assertEqual(answer.get_message().get_content(), "fallback answer")
        self.assertEqual(self.llm1.call_count, 1)
        self.assertEqual(self.llm2.call_count, 1)
        self.assertEqual(len(self.llm_manager.llm_stack), 2)

    async def test_answer_stream_no_fallback_retry_on_429(self):
        from linhai.base import UserMessage

        self.llm1._error_sequence = [
            Exception("429 Too Many Requests"),
            Exception("429 Too Many Requests"),
        ]
        self.llm1._success_content = "retry success"

        r2 = _make_registry()
        lm = _make_llm_manager(r2, [self.llm1])

        history = [UserMessage("hello")]
        answer = await lm.answer_stream(history)
        self.assertEqual(answer.get_message().get_content(), "retry success")
        self.assertEqual(self.llm1.call_count, 3)
        self.assertEqual(len(lm.llm_stack), 1)

    async def test_answer_stream_timeout_retry(self):
        from linhai.base import UserMessage

        self.llm1._error_sequence = [asyncio.TimeoutError("timeout")]
        self.llm1._success_content = "retry after timeout"

        history = [UserMessage("hello")]
        answer = await self.llm_manager.answer_stream(history)
        self.assertEqual(answer.get_message().get_content(), "retry after timeout")
        self.assertEqual(self.llm1.call_count, 2)

    async def test_stack_cleanup_expired_llms(self):
        future_time = datetime.now() + timedelta(seconds=0.01)
        self.llm_manager.llm_stack.append(
            {"llm_name": "llm2", "disabled_until": future_time, "retry_count": 0}
        )
        self.assertEqual(len(self.llm_manager.llm_stack), 2)
        self.llm_manager._cleanup_expired_llms()
        self.assertEqual(len(self.llm_manager.llm_stack), 2)
        await asyncio.sleep(0.02)
        self.llm_manager._cleanup_expired_llms()
        self.assertEqual(len(self.llm_manager.llm_stack), 1)
        self.assertEqual(self.llm_manager.llm_stack[0]["llm_name"], "llm1")

    async def test_get_current_llm_after_cleanup(self):
        future_time = datetime.now() + timedelta(seconds=0.01)
        self.llm_manager.llm_stack.append(
            {"llm_name": "llm2", "disabled_until": future_time, "retry_count": 0}
        )
        await asyncio.sleep(0.02)
        current = self.llm_manager.get_current_llm()
        self.assertIs(current, self.llm1)
        self.assertEqual(len(self.llm_manager.llm_stack), 1)

    async def test_switch_to_llm_clears_stack(self):
        future_time = datetime.now() + timedelta(seconds=1)
        self.llm_manager.llm_stack.append(
            {"llm_name": "llm2", "disabled_until": future_time, "retry_count": 0}
        )
        self.assertEqual(len(self.llm_manager.llm_stack), 2)
        await self.llm_manager.switch_to_llm("llm2")
        self.assertEqual(len(self.llm_manager.llm_stack), 1)
        self.assertEqual(self.llm_manager.llm_stack[0]["llm_name"], "llm2")

    def test_record_error(self):
        initial = len(self.llm_manager.llm_errors["llm1"])
        self.llm_manager._record_error("llm1", "test_error")
        self.assertEqual(len(self.llm_manager.llm_errors["llm1"]), initial + 1)
        self.assertEqual(self.llm_manager.llm_errors["llm1"][-1][1], "test_error")

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
        self.assertTrue(result[0]["is_current"])
        self.assertTrue(result[0]["support_image"])
        self.assertEqual(result[0]["token_limit"], 8000)
        self.assertEqual(result[1]["name"], "llm2")
        self.assertFalse(result[1]["is_current"])
        self.assertFalse(result[1]["support_image"])
        self.assertEqual(result[1]["token_limit"], 16000)

    async def test_empty_history_raises_error(self):
        with self.assertRaises(ValueError) as context:
            await self.llm_manager.answer_stream([])
        self.assertIn("empty", str(context.exception).lower())

    async def test_unexpected_error_propagates(self):
        from linhai.base import UserMessage

        self.llm1._error_sequence = [ValueError("unexpected error")]

        history = [UserMessage("hello")]
        with self.assertRaises(ValueError) as context:
            await self.llm_manager.answer_stream(history)
        self.assertIn("unexpected error", str(context.exception))

    async def test_fallback_chain(self):
        from linhai.base import UserMessage

        llm3 = FakeLLM(name="llm3", token_limit=32000)

        self.llm1._error_sequence = [Exception("429 Too Many Requests")]
        self.llm2._error_sequence = [Exception("429 Too Many Requests")]
        llm3._success_content = "chain answer"

        r2 = _make_registry()
        lm = _make_llm_manager(
            r2,
            [self.llm1, self.llm2, llm3],
            llm_fallback_map={"llm1": "llm2", "llm2": "llm3"},
        )

        history = [UserMessage("hello")]
        answer = await lm.answer_stream(history)
        self.assertEqual(answer.get_message().get_content(), "chain answer")
        self.assertEqual(self.llm1.call_count, 1)
        self.assertEqual(self.llm2.call_count, 1)
        self.assertEqual(llm3.call_count, 1)
        self.assertEqual(len(lm.llm_stack), 3)

    async def test_answer_stream_openai_error(self):
        from linhai.base import UserMessage
        from linhai.llm import OpenAIError

        self.llm1._error_sequence = [OpenAIError("API error")]
        self.llm2._success_content = "fallback after openai error"

        history = [UserMessage("hello")]
        answer = await self.llm_manager.answer_stream(history)
        self.assertEqual(
            answer.get_message().get_content(), "fallback after openai error"
        )
        self.assertEqual(self.llm1.call_count, 1)
        self.assertEqual(self.llm2.call_count, 1)
        self.assertEqual(len(self.llm_manager.llm_stack), 2)

    async def test_answer_stream_retry_on_openai_error_no_fallback(self):
        from linhai.base import UserMessage
        from linhai.llm import OpenAIError

        self.llm1._error_sequence = [OpenAIError("API error"), OpenAIError("API error")]
        self.llm1._success_content = "retry openai success"

        r2 = _make_registry()
        lm = _make_llm_manager(r2, [self.llm1])

        history = [UserMessage("hello")]
        answer = await lm.answer_stream(history)
        self.assertEqual(answer.get_message().get_content(), "retry openai success")
        self.assertEqual(self.llm1.call_count, 3)

    async def test_answer_stream_resets_retry_count_on_success(self):
        from linhai.base import UserMessage

        self.llm1._error_sequence = [
            Exception("connection error"),
            Exception("connection error"),
            Exception("connection error"),
        ]
        self.llm1._success_content = "success after retries"

        r2 = _make_registry()
        lm = _make_llm_manager(r2, [self.llm1])

        history = [UserMessage("hello")]
        answer = await lm.answer_stream(history)
        self.assertEqual(answer.get_message().get_content(), "success after retries")
        self.assertEqual(lm.llm_stack[-1]["retry_count"], 0)

    def test_serialize_and_restore(self):
        self.llm_manager._record_error("llm1", "test_error")
        data = self.llm_manager.serialize()
        self.assertIn("llm_stack", data)

        r2 = _make_registry()
        new_lm = _make_llm_manager(
            r2, [self.llm1, self.llm2], llm_fallback_map={"llm1": "llm2"}
        )
        new_lm.restore_from(data)
        self.assertEqual(len(new_lm.llm_stack), 1)
        self.assertEqual(new_lm.llm_stack[0]["llm_name"], "llm1")

    def test_default_llm_name_auto_select(self):
        r2 = _make_registry()
        lm = _make_llm_manager(
            r2, [self.llm1, self.llm2], llm_fallback_map={"llm1": "llm2"}
        )
        self.assertEqual(lm.default_llm_name, "llm1")

    def test_invalid_default_llm_name_raises(self):
        with self.assertRaises(ValueError):
            r2 = _make_registry()
            _make_llm_manager(r2, [self.llm1], default_llm_name="nonexistent")

    def test_invalid_fallback_map_raises(self):
        with self.assertRaises(ValueError):
            r2 = _make_registry()
            _make_llm_manager(r2, [self.llm1], llm_fallback_map={"llm1": "nonexistent"})

    def test_fallback_duration_default(self):
        r2 = _make_registry()
        lm = _make_llm_manager(r2, [self.llm1], llm_fallback_duration_map={})
        self.assertEqual(lm.llm_fallback_duration_map["llm1"], 120)

    def test_invalid_fallback_duration_raises(self):
        with self.assertRaises(ValueError):
            r2 = _make_registry()
            _make_llm_manager(r2, [self.llm1], llm_fallback_duration_map={"llm1": -1})

    async def test_answer_stream_with_token_usage(self):
        from linhai.base import UserMessage

        self.llm1._success_token_usage = AnswerTokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cached_input_tokens=20,
        )

        history = [UserMessage("hello")]
        answer = await self.llm_manager.answer_stream(history)
        usage = answer.get_token_usage()
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 50)
        self.assertEqual(usage.total_tokens, 150)
        self.assertEqual(usage.cached_input_tokens, 20)

    async def test_non_openai_non_recoverable_error_propagates(self):
        from linhai.base import UserMessage

        self.llm1._error_sequence = [TypeError("type error")]

        history = [UserMessage("hello")]
        with self.assertRaises(TypeError):
            await self.llm_manager.answer_stream(history)

    def test_empty_llm_list_raises(self):
        r = _make_registry()
        with self.assertRaises(IndexError):
            _make_llm_manager(r, [])

    async def test_fallback_chain_exhausted_no_success(self):
        from linhai.base import UserMessage

        self.llm1._error_sequence = [Exception("429 Too Many Requests")]
        self.llm2._error_sequence = [ValueError("non-recoverable at final LLM")]

        history = [UserMessage("hello")]
        with self.assertRaises(ValueError) as ctx:
            await self.llm_manager.answer_stream(history)
        self.assertIn("non-recoverable", str(ctx.exception))
        self.assertEqual(self.llm1.call_count, 1)
        self.assertEqual(self.llm2.call_count, 1)

    async def test_answer_stream_with_partial_token_usage(self):
        from linhai.base import UserMessage

        self.llm1._success_token_usage = AnswerTokenUsage(
            input_tokens=50,
            output_tokens=0,
            total_tokens=50,
            cached_input_tokens=None,
        )

        history = [UserMessage("hello")]
        answer = await self.llm_manager.answer_stream(history)
        usage = answer.get_token_usage()
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.input_tokens, 50)
        self.assertEqual(usage.output_tokens, 0)
        self.assertIsNone(usage.cached_input_tokens)

    def test_fallback_duration_respected(self):
        r2 = _make_registry()
        lm = _make_llm_manager(
            r2,
            [self.llm1, self.llm2],
            llm_fallback_map={"llm1": "llm2"},
            llm_fallback_duration_map={"llm1": 60, "llm2": 180},
        )
        self.assertEqual(lm.llm_fallback_duration_map["llm1"], 60)
        self.assertEqual(lm.llm_fallback_duration_map["llm2"], 180)

    def test_explicit_cache_info_in_list_available(self):
        from linhai.base import ExplicitCacheInfo

        llm_with_cache = FakeLLM(
            name="cached-llm",
            explicit_cache_info=ExplicitCacheInfo(
                cache_write_price_ratio=1.25, cache_hit_price_ratio=0.1
            ),
        )
        r2 = _make_registry()
        lm = _make_llm_manager(
            r2,
            [llm_with_cache, self.llm2],
            llm_fallback_map={"cached-llm": "llm2"},
        )
        result = lm.list_available_llms()
        self.assertEqual(len(result), 2)
        cache_info = llm_with_cache.get_explicit_cache_info()
        self.assertIsNotNone(cache_info)
        assert cache_info is not None
        self.assertAlmostEqual(cache_info.cache_write_price_ratio, 1.25)
        self.assertAlmostEqual(cache_info.cache_hit_price_ratio, 0.1)

    def test_duplicate_llm_names(self):
        r = _make_registry()
        llm_a = FakeLLM(name="same-name", token_limit=1000)
        llm_b = FakeLLM(name="same-name", token_limit=2000)
        lm = _make_llm_manager(r, [llm_a, llm_b], llm_fallback_map={"same-name": None})
        self.assertEqual(lm.llm_names, ["same-name", "same-name"])


if __name__ == "__main__":
    unittest.main()
