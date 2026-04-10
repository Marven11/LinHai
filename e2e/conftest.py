import asyncio
import os
import random

import pytest
import pytest_asyncio
from openai import AsyncOpenAI

from linhai.llm import SystemMessage


@pytest_asyncio.fixture
async def llm_client() -> AsyncOpenAI:
    token = os.environ.get("DEEPSEEK_TOKEN")
    if not token:
        pytest.fail("DEEPSEEK_TOKEN not set")
    return AsyncOpenAI(
        api_key=token,
        base_url="https://api.deepseek.com/v1",
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
