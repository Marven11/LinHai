import os

import pytest
import pytest_asyncio
from openai import AsyncOpenAI


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
