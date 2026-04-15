import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from starlette.testclient import TestClient

from linhai.jsonpubsub import JsonSubscriber
from linhai.webui import create_app
from linhai.webui.agent_manager import AgentManager
from linhai.webui import routes
from linhai.config import get_default_config_path


def setup_manager():
    config_path = get_default_config_path()
    routes._manager = AgentManager(config_path=config_path)


def teardown_manager():
    routes._manager = None


def _feed_events_until(ws, sub, predicate, max_iterations=30):
    for _ in range(max_iterations):
        data = ws.receive_json(mode="text")
        if "event" in data:
            sub.update_data(data)
        if predicate(sub):
            return True
    return False


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


def test_websocket_initial_state():
    setup_manager()
    try:
        app = create_app()
        client = TestClient(app)

        response = client.post("/api/agents", json={"init_messages": ["Say hello"]})
        assert response.status_code == 200
        agent_id = response.json()["id"]

        sub = JsonSubscriber()
        with client.websocket_connect(f"/api/agents/{agent_id}/ws") as ws:
            data = ws.receive_json(mode="text")
            assert "event" in data
            sub.update_data(data)
            messages = sub.data.get("messages", [])
            assert any(
                m.get("type") == "user" and m.get("content") == "Say hello"
                for m in messages
            )

        client.delete(f"/api/agents/{agent_id}")
    finally:
        teardown_manager()


def test_websocket_user_message():
    setup_manager()
    try:
        app = create_app()
        client = TestClient(app)

        response = client.post("/api/agents", json={"init_messages": []})
        assert response.status_code == 200
        agent_id = response.json()["id"]

        sub = JsonSubscriber()
        with client.websocket_connect(f"/api/agents/{agent_id}/ws") as ws:
            data = ws.receive_json(mode="text")
            assert "event" in data
            sub.update_data(data)

            ws.send_text(
                json.dumps({"type": "user_message", "content": "Hello from test"})
            )

            found = _feed_events_until(
                ws,
                sub,
                lambda s: any(
                    m.get("type") == "user" and m.get("content") == "Hello from test"
                    for m in s.data.get("messages", [])
                ),
            )
            assert found, f"User message not found in subscriber data: {sub.data}"

        client.delete(f"/api/agents/{agent_id}")
    finally:
        teardown_manager()


def test_websocket_reset_recovery():
    setup_manager()
    try:
        app = create_app()
        client = TestClient(app)

        response = client.post("/api/agents", json={"init_messages": []})
        assert response.status_code == 200
        agent_id = response.json()["id"]

        sub = JsonSubscriber()
        with client.websocket_connect(f"/api/agents/{agent_id}/ws") as ws:
            data = ws.receive_json(mode="text")
            assert "event" in data
            sub.update_data(data)

            ws.send_text(
                json.dumps({"type": "user_message", "content": "Before reset"})
            )
            _feed_events_until(
                ws,
                sub,
                lambda s: any(
                    m.get("type") == "user" for m in s.data.get("messages", [])
                ),
            )

            original_data = copy.deepcopy(sub.data)

            desynced_sub = JsonSubscriber()
            assert desynced_sub.data is None

            ws.send_text(json.dumps({"type": "reset"}))
            _feed_events_until(
                ws, desynced_sub, lambda s: s.data is not None, max_iterations=10
            )

            assert desynced_sub.data is not None
            assert (
                desynced_sub.data == original_data
            ), f"Reset recovery mismatch: {desynced_sub.data} != {original_data}"

        client.delete(f"/api/agents/{agent_id}")
    finally:
        teardown_manager()


def test_websocket_multi_turn():
    setup_manager()
    try:
        app = create_app()
        client = TestClient(app)

        response = client.post("/api/agents", json={"init_messages": []})
        assert response.status_code == 200
        agent_id = response.json()["id"]

        sub = JsonSubscriber()
        with client.websocket_connect(f"/api/agents/{agent_id}/ws") as ws:
            data = ws.receive_json(mode="text")
            assert "event" in data
            sub.update_data(data)

            ws.send_text(
                json.dumps({"type": "user_message", "content": "First message"})
            )

            found1 = _feed_events_until(
                ws,
                sub,
                lambda s: any(
                    m.get("type") == "user" and m.get("content") == "First message"
                    for m in s.data.get("messages", [])
                ),
            )
            assert found1, f"First user message not found: {sub.data}"

            first_count = len(sub.data.get("messages", []))

            ws.send_text(
                json.dumps({"type": "user_message", "content": "Second message"})
            )

            found2 = _feed_events_until(
                ws,
                sub,
                lambda s: len(s.data.get("messages", [])) > first_count
                and any(
                    m.get("type") == "user" and m.get("content") == "Second message"
                    for m in s.data.get("messages", [])
                ),
            )
            assert found2, f"Second user message not found: {sub.data}"

            messages = sub.data.get("messages", [])
            contents = [m.get("content") for m in messages if m.get("type") == "user"]
            assert contents == ["First message", "Second message"]

        client.delete(f"/api/agents/{agent_id}")
    finally:
        teardown_manager()
