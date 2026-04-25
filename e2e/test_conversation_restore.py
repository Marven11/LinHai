import asyncio
import json
import random
import sys
import tempfile
import threading
from pathlib import Path

import pytest
import tomli_w
from httpx import AsyncClient
import uvicorn

sys.path.insert(0, str(Path(__file__).parent.parent))

from linhai.utils.jsonpubsub import JsonSubscriber
from linhai.webui import create_app
from linhai.webui.agent_manager import AgentManager
from linhai.webui import routes
from e2e.conftest import AsyncEventFeeder

pytestmark = pytest.mark.asyncio


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


async def _wait_for_agent_completion(ws, feeder, sub, timeout=300):
    finished = await feeder.wait_for_completion(
        min_duration=30, quiet_period=5, timeout=timeout
    )
    assert finished, "Agent did not complete within timeout"


def _extract_save_path_from_notifications(sub) -> str | None:
    messages = sub.data.get("messages", [])
    for msg in reversed(messages):
        if msg.get("type") == "notification":
            content = msg.get("content", "")
            if "Conversation saved to" in content:
                prefix = "Conversation saved to "
                idx = content.index(prefix)
                return content[idx + len(prefix) :].strip()
    return None


async def test_conversation_save_and_restore():
    import websockets

    config_path = _write_e2e_config()
    routes._manager = AgentManager(config_path=config_path)
    app = create_app()
    token = app.state.api_token
    port = 18767
    server_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": app, "host": "127.0.0.1", "port": port, "log_level": "error"},
        daemon=True,
    )
    server_thread.start()

    secret_number = str(random.randint(1000000, 9999999))

    async with AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
        client.cookies.set("api_token", token)
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
            f"ws://127.0.0.1:{port}/api/agents/{agent_id}/ws",
            additional_headers={"Cookie": f"api_token={token}"},
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
                        "content": f"帮我记住一个数字: {secret_number}，看到之后回复'好的，我会记住的'。",
                    }
                )
            )
            feeder.reset_timing()
            await _wait_for_agent_completion(ws, feeder, sub)

            agent_msgs = [
                m for m in sub.data.get("messages", []) if m.get("type") == "agent"
            ]
            assert (
                len(agent_msgs) >= 1
            ), f"Expected at least 1 agent message, got {len(agent_msgs)}"

            await ws.send(
                json.dumps(
                    {
                        "type": "user_message",
                        "content": "/save",
                    }
                )
            )

            save_path = None
            for _ in range(60):
                await asyncio.sleep(1)
                save_path = _extract_save_path_from_notifications(sub)
                if save_path is not None:
                    break

            await feeder.drain()
            await feeder.stop()

        assert (
            save_path is not None
        ), f"Save path not found in notifications: {sub.data.get('messages', [])}"
        save_file = Path(save_path)
        assert save_file.exists(), f"Save file not found: {save_path}"
        save_data = json.loads(save_file.read_text(encoding="utf-8"))
        assert "version" in save_data
        assert "members" in save_data

        await client.delete(f"/api/agents/{agent_id}")

        resp = await client.post(
            "/api/agents",
            json={"message": [], "restore_path": str(save_file)},
        )
        assert resp.status_code == 200
        agent_id_2 = resp.json()["id"]

        sub2 = JsonSubscriber()
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/api/agents/{agent_id_2}/ws",
            additional_headers={"Cookie": f"api_token={token}"},
        ) as ws2:
            data = json.loads(await ws2.recv())
            assert "event" in data
            sub2.update_data(data)

            feeder2 = AsyncEventFeeder(ws2, sub2)
            await feeder2.start()

            await ws2.send(
                json.dumps(
                    {
                        "type": "user_message",
                        "content": "我刚刚说的数字是多少？",
                    }
                )
            )
            feeder2.reset_timing()
            await _wait_for_agent_completion(ws2, feeder2, sub2)

            await feeder2.drain()
            await feeder2.stop()

        all_messages = sub2.data.get("messages", [])
        user_contents = [
            m.get("content", "") for m in all_messages if m.get("type") == "user"
        ]
        agent_contents = [
            m.get("content", "") for m in all_messages if m.get("type") == "agent"
        ]

        has_user_number = any(secret_number in c for c in user_contents)
        has_agent_number = any(secret_number in c for c in agent_contents)

        assert (
            has_user_number
        ), f"Secret number {secret_number} not found in restored user messages: {user_contents}"
        assert (
            has_agent_number
        ), f"Secret number {secret_number} not found in restored agent messages: {[c[:200] for c in agent_contents]}"

        await client.delete(f"/api/agents/{agent_id_2}")

    routes._manager = None
