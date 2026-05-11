import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from linhai.webui.app import create_app


@pytest.fixture
def mock_manager():
    with patch("linhai.webui.routes.get_manager") as mock_get:
        with patch("linhai.webui.agent_manager.load_config"):
            from linhai.webui.agent_manager import AgentManager, AgentSession

            manager = AgentManager(config_path=Path("/fake/path"))
            mock_agent = MagicMock()
            mock_agent.state_machine.state = "waiting_user"
            mock_llm = MagicMock()
            mock_llm.get_name = MagicMock(return_value="gpt")
            mock_agent.get_current_llm_info = MagicMock(return_value=(None, mock_llm))
            mock_registry = MagicMock()
            mock_registry.has_member.return_value = False
            mock_agent.registry = mock_registry
            session = AgentSession(
                agent_id="test-agent-id",
                agent=mock_agent,
                task_name="task-1",
                manager=manager,
            )
            manager.sessions["test-agent-id"] = session
            mock_get.return_value = manager
            yield manager, session


@pytest.fixture
async def client():
    app = create_app(api_token="e2e-test-token")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {app.state.api_token}"
        yield ac


@pytest.mark.asyncio
async def test_list_llms(mock_manager, client):
    manager, session = mock_manager
    manager._registries["test-agent-id"] = session.registry
    resp = await client.get("/api/agents/test-agent-id/llms")
    assert resp.status_code == 200
    data = resp.json()
    assert "llms" in data


@pytest.mark.asyncio
async def test_switch_llm(mock_manager, client):
    manager, session = mock_manager
    manager._registries["test-agent-id"] = session.registry
    session.registry.has_member = MagicMock(return_value=True)
    mock_llm_manager = MagicMock()
    mock_llm_manager.list_available_llms = MagicMock(
        return_value=[
            {
                "name": "gpt",
                "model": "gpt-4",
                "token_limit": 128000,
                "support_image": True,
                "is_current": True,
                "is_default": True,
                "error_count": 0,
            },
            {
                "name": "claude",
                "model": "claude-3",
                "token_limit": 200000,
                "support_image": True,
                "is_current": False,
                "is_default": False,
                "error_count": 0,
            },
        ]
    )
    mock_llm_manager.switch_to_llm = AsyncMock()
    session.registry.get_member_typechecked = MagicMock(return_value=mock_llm_manager)
    resp = await client.post(
        "/api/agents/test-agent-id/switch_llm",
        json={"llm_name": "claude"},
    )
    assert resp.status_code == 200
    mock_llm_manager.switch_to_llm.assert_called_once_with("claude")


@pytest.mark.asyncio
async def test_switch_llm_invalid(mock_manager, client):
    manager, session = mock_manager
    manager._registries["test-agent-id"] = session.registry
    session.registry.has_member = MagicMock(return_value=True)
    mock_llm_manager = MagicMock()
    mock_llm_manager.list_available_llms = MagicMock(
        return_value=[
            {
                "name": "gpt",
                "model": "gpt-4",
                "token_limit": 128000,
                "support_image": True,
                "is_current": True,
                "is_default": True,
                "error_count": 0,
            },
        ]
    )
    mock_llm_manager.switch_to_llm = AsyncMock()
    session.registry.get_member_typechecked = MagicMock(return_value=mock_llm_manager)
    resp = await client.post(
        "/api/agents/test-agent-id/switch_llm",
        json={"llm_name": "nonexistent"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_agent_state(mock_manager, client):
    manager, session = mock_manager
    manager._registries["test-agent-id"] = session.registry
    resp = await client.get("/api/agents/test-agent-id")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "waiting_user"


@pytest.mark.asyncio
async def test_kill_process(mock_manager, client):
    manager, session = mock_manager
    manager._registries["test-agent-id"] = session.registry
    session.registry.has_member = MagicMock(return_value=True)
    mock_mc = MagicMock()
    mock_host = MagicMock()
    mock_proc = MagicMock()
    mock_proc.kill = AsyncMock(return_value=MagicMock(success=True))
    mock_host.get_process.return_value = mock_proc
    mock_mc.machines = {"master_host": mock_host}
    session.registry.get_member_typechecked = MagicMock(return_value=mock_mc)
    resp = await client.post(
        "/api/agents/test-agent-id/processes/123/kill",
        json={"machine_id": "master_host"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_kill_process_not_found(mock_manager, client):
    manager, session = mock_manager
    manager._registries["test-agent-id"] = session.registry
    session.registry.has_member = MagicMock(return_value=True)
    mock_mc = MagicMock()
    mock_mc.machines = {}
    session.registry.get_member_typechecked = MagicMock(return_value=mock_mc)
    resp = await client.post(
        "/api/agents/test-agent-id/processes/999/kill",
        json={"machine_id": "master_host"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agent_not_found_llms(client):
    resp = await client.get("/api/agents/nonexistent/llms")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agent_not_found_switch_llm(client):
    resp = await client.post(
        "/api/agents/nonexistent/switch_llm",
        json={"llm_name": "gpt"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agent_not_found_kill_process(client):
    resp = await client.post(
        "/api/agents/nonexistent/processes/123/kill",
        json={"machine_id": "master_host"},
    )
    assert resp.status_code == 404
