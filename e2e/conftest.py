import asyncio
import json
import random
import time

import pytest
import pytest_asyncio
from openai import AsyncOpenAI

from linhai.base import SystemMessage
from linhai.utils.jsonpubsub import JsonSubscriber


class AsyncEventFeeder:
    def __init__(self, ws, sub: JsonSubscriber):
        self.ws = ws
        self.sub = sub
        self._task = None
        self._last_event_time = 0.0
        self._started_at = 0.0

    @property
    def running(self):
        return self._task is not None and not self._task.done()

    async def start(self):
        self._started_at = time.time()
        self._last_event_time = time.time()
        self._task = asyncio.create_task(self._feed_loop())

    async def _feed_loop(self):
        while True:
            try:
                raw = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
                data = json.loads(raw)
                if "event" in data:
                    try:
                        self.sub.update_data(data)
                    except RuntimeError:
                        pass
                    self._last_event_time = time.time()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            except Exception:
                return

    def elapsed_since_start(self):
        return time.time() - self._started_at

    def quiet_period(self):
        return time.time() - self._last_event_time

    async def wait_for_completion(
        self, min_duration: float = 30, quiet_period: float = 5, timeout: float = 300
    ):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if (
                self.elapsed_since_start() >= min_duration
                and self.quiet_period() >= quiet_period
            ):
                return True
            await asyncio.sleep(0.5)
        return False

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def reset_timing(self):
        self._started_at = time.time()
        self._last_event_time = time.time()


@pytest_asyncio.fixture
async def llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key="x",
        base_url="http://192.168.114.149:8124/v1/deepseek",
    )


def slim_system_message(msg: SystemMessage) -> None:
    for title in [
        "SOUL",
        "WAITING USER AND AUTO RUN",
        "GLOBAL PROMPT",
        "CONTEXT MANAGEMENT",
        "SECRET SYSTEM",
        "MACHINE CONTROL BASIC",
    ]:
        msg.remove_introduction(title)
    for title in ["CODING STYLE", "USER INTERACTION"]:
        msg.remove_rule(title)
    msg.remove_example("SECRET")


E2E_MAX_RETRIES = 20


async def retry_llm_call(fn, max_retries: int = E2E_MAX_RETRIES):
    for i in range(max_retries):
        result = await fn()
        if result:
            return result
        if i < max_retries - 1:
            delay = min(2.0 * (1.5**i) + random.uniform(0, 2), 60.0)
            await asyncio.sleep(delay)
    pytest.fail(
        f"Free model returned empty/unexpected response after {max_retries} retries"
    )
