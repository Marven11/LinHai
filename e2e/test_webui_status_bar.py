import asyncio
import copy
import json
import sys
import tempfile
import time
from pathlib import Path

import pytest
import tomli_w
import uvicorn
from httpx import AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from linhai.utils.jsonpubsub import JsonSubscriber
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


async def _wait_for_agent_turn(ws, sub, timeout=120):
    raise NotImplementedError("Use AsyncEventFeeder instead")


@pytest.mark.asyncio
async def test_webui_status_bar_e2e():
    import websockets

    from e2e.conftest import AsyncEventFeeder

    config_path = _write_e2e_config()
    routes._manager = AgentManager(config_path=config_path)
    app = create_app()
    port = 18766
    import threading

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
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/api/agents/{agent_id}/ws"
        ) as ws:
            data = json.loads(await ws.recv())
            assert "event" in data
            sub.update_data(data)

            feeder = AsyncEventFeeder(ws, sub)
            await feeder.start()

            await ws.send(
                json.dumps(
                    {
                        "type": "user_message",
                        "content": "Say hello in one sentence",
                    }
                )
            )
            finished = await feeder.wait_for_completion(
                min_duration=30, quiet_period=5, timeout=120
            )
            assert finished, "Agent did not complete turn within 120s"

            await feeder.stop()

            status_bar = sub.data.get("status_bar")
            assert (
                status_bar is not None
            ), f"status_bar key not found in subscriber data: {sub.data.keys()}"
            assert isinstance(
                status_bar, list
            ), f"status_bar is not a list: {type(status_bar)}"
            assert len(status_bar) > 0, "status_bar is empty"

            llm_piece = [p for p in status_bar if "\u2726" in p]
            assert (
                len(llm_piece) > 0
            ), f"No LLM name piece found in status_bar: {status_bar}"

            session = routes._manager.sessions.get(agent_id)
            assert session is not None
            server_data = copy.deepcopy(session._data)
            assert (
                sub.data == server_data
            ), f"Subscriber data {sub.data} != server data {server_data}"

        await client.delete(f"/api/agents/{agent_id}")
