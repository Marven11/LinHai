import os

import pytest
import pytest_asyncio
from openai import AsyncOpenAI

from linhai.llm import SystemMessage


@pytest_asyncio.fixture
async def openrouter_client() -> AsyncOpenAI:
    token = os.environ.get("OPENROUTER_TOKEN")
    if not token:
        pytest.fail("OPENROUTER_TOKEN not set")
    return AsyncOpenAI(
        api_key=token,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://github.com/Marven11/LinHai",
            "X-Title": "LinHai E2E Tests",
        },
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
