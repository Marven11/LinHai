import pytest

pytestmark = pytest.mark.asyncio


async def test_deepseek_basic(llm_client):
    for _ in range(3):
        response = await llm_client.chat.completions.create(
            model="deepseek/deepseek-v4-flash",
            messages=[{"role": "user", "content": "Say hello"}],
            max_tokens=200,
        )
        if response.choices and response.choices[0].message.content:
            return
    pytest.fail("free model returned empty content after 3 retries")
