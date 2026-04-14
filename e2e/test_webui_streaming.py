import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from starlette.testclient import TestClient

from linhai.webui import create_app
from linhai.webui.agent_manager import AgentManager
from linhai.webui import routes
from linhai.config import get_default_config_path


def setup_manager():
    config_path = get_default_config_path()
    routes._manager = AgentManager(config_path=config_path)


def teardown_manager():
    routes._manager = None


def test_websocket_agent_not_found():
    setup_manager()
    try:
        app = create_app()
        client = TestClient(app)
        try:
            with client.websocket_connect("/api/agents/nonexistent/ws"):
                pass
            assert False, "Expected websocket close"
        except Exception:
            pass
    finally:
        teardown_manager()


def test_websocket_connect_existing_agent():
    setup_manager()
    try:
        app = create_app()
        client = TestClient(app)

        response = client.post("/api/agents", json={"init_messages": ["Say hello"]})
        assert response.status_code == 200
        agent_id = response.json()["id"]

        with client.websocket_connect(f"/api/agents/{agent_id}/ws") as ws:
            ws.send_text(json.dumps({"type": "reset"}))
            data = ws.receive_json(mode="text")
            assert isinstance(data, dict)
            assert "idx" in data

        client.delete(f"/api/agents/{agent_id}")
    finally:
        teardown_manager()


def test_websocket_send_user_message():
    setup_manager()
    try:
        app = create_app()
        client = TestClient(app)

        response = client.post("/api/agents", json={"init_messages": ["Say hi"]})
        assert response.status_code == 200
        agent_id = response.json()["id"]

        with client.websocket_connect(f"/api/agents/{agent_id}/ws") as ws:
            ws.send_text(json.dumps({"type": "user_message", "content": "Hello"}))
            data = ws.receive_json(mode="text")
            assert isinstance(data, dict)

        client.delete(f"/api/agents/{agent_id}")
    finally:
        teardown_manager()


def test_websocket_reset():
    setup_manager()
    try:
        app = create_app()
        client = TestClient(app)

        response = client.post("/api/agents", json={"init_messages": ["Say hello"]})
        assert response.status_code == 200
        agent_id = response.json()["id"]

        with client.websocket_connect(f"/api/agents/{agent_id}/ws") as ws:
            ws.send_text(json.dumps({"type": "reset"}))
            data = ws.receive_json(mode="text")
            assert isinstance(data, dict)
            assert isinstance(data.get("idx"), int)

        client.delete(f"/api/agents/{agent_id}")
    finally:
        teardown_manager()
