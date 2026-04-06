import pytest

pytestmark = pytest.mark.asyncio


async def test_openrouter_basic(openrouter_client):
    for _ in range(3):
        response = await openrouter_client.chat.completions.create(
            model="openrouter/free",
            messages=[{"role": "user", "content": "Say hello"}],
            max_tokens=200,
        )
        if response.choices and response.choices[0].message.content:
            return
    pytest.fail("free model returned empty content after 3 retries")
