import pytest
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from httpx import AsyncClient, ASGITransport

from linhai.webui import create_app
from linhai.webui.agent_manager import AgentManager
from linhai.webui import routes
from linhai.config import get_default_config_path


@pytest.fixture(autouse=True)
def setup_manager():
    config_path = str(get_default_config_path())
    routes._manager = AgentManager(config_path=config_path)
    yield
    routes._manager = None


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_send_message(client):
    create_response = await client.post("/api/agents", json={"init_messages": []})
    assert create_response.status_code == 200
    agent_id = create_response.json()["id"]

    send_response = await client.post(
        f"/api/agents/{agent_id}/messages",
        json={"content": "Hello, introduce yourself briefly"},
    )
    assert send_response.status_code == 200

    await asyncio.sleep(5)

    messages_response = await client.get(f"/api/agents/{agent_id}/messages")
    assert messages_response.status_code == 200
    data = messages_response.json()
    assert "messages" in data

    delete_response = await client.delete(f"/api/agents/{agent_id}")
    assert delete_response.status_code == 200


@pytest.mark.asyncio
async def test_send_message_agent_not_found(client):
    response = await client.post(
        "/api/agents/nonexistent/messages",
        json={"content": "Hello"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_messages_agent_not_found(client):
    response = await client.get("/api/agents/nonexistent/messages")
    assert response.status_code == 404
