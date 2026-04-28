import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from linhai.webui import create_app
from linhai.webui.agent_manager import AgentManager
from linhai.webui import routes
from linhai.config import get_default_config_path

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def setup_manager():
    config_path = str(get_default_config_path())
    routes._manager = AgentManager(config_path=config_path)
    yield
    routes._manager = None


@pytest.fixture
async def client():
    app = create_app(api_token="e2e-test-token")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {app.state.api_token}"
        yield ac


async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_agent(client):
    response = await client.post("/api/agents", json={"message": ["Hello"]})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["state"] in ["working", "waiting_user"]


async def test_list_agents(client):
    response = await client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)


async def test_get_agent_state(client):
    create_response = await client.post("/api/agents", json={"message": ["Say hello"]})
    agent_id = create_response.json()["id"]

    await asyncio.sleep(1)

    get_response = await client.get(f"/api/agents/{agent_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["id"] == agent_id
    assert data["state"] in ["working", "waiting_user"]

    delete_response = await client.delete(f"/api/agents/{agent_id}")
    assert delete_response.status_code == 200


async def test_delete_agent(client):
    create_response = await client.post("/api/agents", json={"message": ["Test"]})
    agent_id = create_response.json()["id"]

    delete_response = await client.delete(f"/api/agents/{agent_id}")
    assert delete_response.status_code == 200

    get_response = await client.get(f"/api/agents/{agent_id}")
    assert get_response.status_code == 404
