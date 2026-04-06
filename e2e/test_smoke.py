import pytest

pytestmark = pytest.mark.asyncio


async def test_openrouter_basic(openrouter_client):
    response = await openrouter_client.chat.completions.create(
        model="openrouter/free",
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=50,
    )
    assert response.choices
    assert response.choices[0].message.content
