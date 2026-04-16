import asyncio
import copy
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest
import tomli_w
import uvicorn
from httpx import AsyncClient

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


def _write_e2e_config() -> Path:
    from linhai.config import LLMConfig

    llm_config = LLMConfig(
        name="deepseek",
        base_url="http://192.168.114.149:8124/v1/deepseek",
        api_key="x",
        model="deepseek-chat",
    )
    config_data = {
        "llm": [llm_config.model_dump(exclude_none=True)],
        "agent": [{"name": "default", "default_llm": "deepseek"}],
    }
    config_path = Path(tempfile.mkdtemp()) / "config.toml"
    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)
    return config_path


async def _wait_for_agent_turn(ws, sub, timeout=120):
    start_time = time.time()
    reached_waiting = False
    while time.time() - start_time < timeout:
        recv_timeout = 2.0 if reached_waiting else 5.0
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=recv_timeout)
        except asyncio.TimeoutError:
            if reached_waiting:
                return True
            continue
        data = json.loads(raw)
        if "event" in data:
            sub.update_data(data)
        if isinstance(data, dict) and data.get("type") == "state_change":
            if data.get("new_state") == "waiting_user":
                reached_waiting = True
    return False


@pytest.mark.asyncio
async def test_webui_streaming_e2e():
    import websockets

    config_path = _write_e2e_config()
    routes._manager = AgentManager(config_path=config_path)
    app = create_app()
    port = 18765
    server_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": app, "host": "127.0.0.1", "port": port, "log_level": "error"},
        daemon=True,
    )
    server_thread.start()
    async with AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
        for _ in range(50):
            try:
                resp = await client.get("/api/agents")
                if resp.status_code == 200:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.2)
        resp = await client.post("/api/agents", json={"init_messages": []})
        assert resp.status_code == 200
        agent_id = resp.json()["id"]
        sub = JsonSubscriber()
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/api/agents/{agent_id}/ws"
        ) as ws:
            data = json.loads(await ws.recv())
            assert "event" in data
            sub.update_data(data)

            await ws.send(
                json.dumps(
                    {
                        "type": "user_message",
                        "content": "Write a 200-word essay about artificial intelligence and its impact on society",
                    }
                )
            )
            finished1 = await _wait_for_agent_turn(ws, sub, timeout=120)
            assert finished1, "Agent did not complete first turn within 120s"

            await ws.send(
                json.dumps(
                    {
                        "type": "user_message",
                        "content": "Now summarize your essay in exactly 100 words",
                    }
                )
            )
            finished2 = await _wait_for_agent_turn(ws, sub, timeout=120)
            assert finished2, "Agent did not complete second turn within 120s"

        messages = sub.data.get("messages", [])
        user_msgs = [m for m in messages if m.get("type") == "user"]
        assert len(user_msgs) == 2, f"Expected 2 user messages, got {len(user_msgs)}"
        assert (
            user_msgs[0]["content"]
            == "Write a 200-word essay about artificial intelligence and its impact on society"
        )
        assert (
            user_msgs[1]["content"] == "Now summarize your essay in exactly 100 words"
        )
        agent_msgs = [m for m in messages if m.get("type") == "agent"]
        assert (
            len(agent_msgs) >= 2
        ), f"Expected 2+ agent messages, got {len(agent_msgs)}"
        assert all(
            len(m.get("content", "")) > 50 for m in agent_msgs
        ), f"Agent messages too short: {[m.get('content', '')[:50] for m in agent_msgs]}"
        session = routes._manager.sessions.get(agent_id)
        assert session is not None
        server_data = copy.deepcopy(session._messages_data)
        assert sub.data == server_data
        await client.delete(f"/api/agents/{agent_id}")
