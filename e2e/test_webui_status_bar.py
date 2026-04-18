import asyncio
import copy
import json
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

from linhai.jsonpubsub import JsonSubscriber
from linhai.webui import create_app
from linhai.webui.agent_manager import AgentManager
from linhai.webui import routes


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


async def _wait_for_agent_turn_and_collect_status_bars(
    ws, sub, status_bar_sub, timeout=120
):
    start_time = time.time()
    reached_waiting = False
    status_bar_updates_received = 0
    while time.time() - start_time < timeout:
        recv_timeout = 2.0 if reached_waiting else 5.0
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=recv_timeout)
        except asyncio.TimeoutError:
            if reached_waiting:
                return status_bar_updates_received
            continue
        data = json.loads(raw)
        if "event" in data:
            sub.update_data(data)
        if isinstance(data, dict) and data.get("type") == "status_bar_update":
            for event in data.get("events", []):
                status_bar_sub.update_data(event)
            status_bar_updates_received += 1
        if isinstance(data, dict) and data.get("type") == "state_change":
            if data.get("new_state") == "waiting_user":
                reached_waiting = True
    return status_bar_updates_received


@pytest.mark.asyncio
async def test_webui_status_bar_e2e():
    import websockets

    config_path = _write_e2e_config()
    routes._manager = AgentManager(config_path=config_path)
    app = create_app()
    port = 18766
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
        resp = await client.post("/api/agents", json={"message": []})
        assert resp.status_code == 200
        agent_id = resp.json()["id"]
        sub = JsonSubscriber()
        status_bar_sub = JsonSubscriber()
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
                        "content": "Say hello in one sentence",
                    }
                )
            )
            updates = await _wait_for_agent_turn_and_collect_status_bars(
                ws, sub, status_bar_sub, timeout=120
            )
            assert updates > 0, "No status_bar_update events received"

            assert (
                status_bar_sub.data is not None
            ), "status_bar_sub.data is None, no events were processed"
            status_bar = status_bar_sub.data.get("status_bar")
            assert (
                status_bar is not None
            ), f"status_bar key not found in data: {status_bar_sub.data}"
            assert isinstance(
                status_bar, list
            ), f"status_bar is not a list: {type(status_bar)}"
            assert len(status_bar) > 0, "status_bar is empty"

            llm_piece = [p for p in status_bar if "✦" in p]
            assert (
                len(llm_piece) > 0
            ), f"No LLM name piece found in status_bar: {status_bar}"

            session = routes._manager.sessions.get(agent_id)
            assert session is not None
            server_status_bar = copy.deepcopy(session._status_bar_data)
            assert (
                status_bar_sub.data == server_status_bar
            ), f"Subscriber data {status_bar_sub.data} != server data {server_status_bar}"

        await client.delete(f"/api/agents/{agent_id}")
