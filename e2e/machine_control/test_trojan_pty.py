import asyncio
import json
import os
import tempfile

import pytest

from linhai.task_supervisor import PlainTaskSupervisor


@pytest.fixture
def pty_bash_with_trojan():
    trojan_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "linhai",
        "machine_control",
        "trojan",
        "trojan.py",
    )
    trojan_path = os.path.abspath(trojan_path)
    marker_hex = "a1b2"
    return trojan_path, marker_hex


async def _read_until_marker(
    reader: asyncio.StreamReader,
    marker_open: str,
    marker_close: str,
    timeout: float = 10.0,
) -> str:
    buf = b""
    open_bytes = marker_open.encode()
    close_bytes = marker_close.encode()
    while True:
        try:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"读取marker超时，已读取: {buf!r}")
        if not chunk:
            raise ConnectionError("进程已关闭")
        buf += chunk
        start_idx = buf.find(open_bytes)
        if start_idx == -1:
            if len(buf) > len(open_bytes):
                buf = buf[-len(open_bytes) :]
            continue
        close_idx = buf.find(close_bytes, start_idx)
        if close_idx == -1:
            continue
        json_start = start_idx + len(open_bytes)
        return buf[json_start:close_idx].decode("utf-8", errors="replace")


async def _send_request(
    writer: asyncio.StreamWriter, request: dict, marker_open: str, marker_close: str
):
    data = f"{marker_open}{json.dumps(request)}{marker_close}"
    writer.write(data.encode())
    await writer.drain()


@pytest.mark.asyncio
async def test_trojan_ping_over_pty(pty_bash_with_trojan):
    trojan_path, marker_hex = pty_bash_with_trojan
    marker_open = f"<linhai_trojanpy_{marker_hex}>"
    marker_close = f"</linhai_trojanpy_{marker_hex}>"

    process = await asyncio.create_subprocess_exec(
        "python3",
        trojan_path,
        marker_hex,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        await asyncio.sleep(0.5)

        request = {"jsonrpc": "2.0", "id": "1", "method": "ping", "params": {}}
        await _send_request(process.stdin, request, marker_open, marker_close)

        response_str = await _read_until_marker(
            process.stdout, marker_open, marker_close
        )
        response = json.loads(response_str)
        assert response["id"] == "1"
        assert response["result"]["message"] == "pong"
    finally:
        process.terminate()
        await process.wait()


@pytest.mark.asyncio
async def test_trojan_file_operations_over_pty(pty_bash_with_trojan):
    trojan_path, marker_hex = pty_bash_with_trojan
    marker_open = f"<linhai_trojanpy_{marker_hex}>"
    marker_close = f"</linhai_trojanpy_{marker_hex}>"

    process = await asyncio.create_subprocess_exec(
        "python3",
        trojan_path,
        marker_hex,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        await asyncio.sleep(0.5)

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            test_content = "hello from trojan pty test"

            write_req = {
                "jsonrpc": "2.0",
                "id": "2",
                "method": "write_file",
                "params": {
                    "filepath": test_file,
                    "content": test_content,
                    "override": True,
                },
            }
            await _send_request(process.stdin, write_req, marker_open, marker_close)
            resp = json.loads(
                await _read_until_marker(process.stdout, marker_open, marker_close)
            )
            assert resp["id"] == "2"
            assert "error" not in resp

            read_req = {
                "jsonrpc": "2.0",
                "id": "3",
                "method": "read_file",
                "params": {"filepath": test_file},
            }
            await _send_request(process.stdin, read_req, marker_open, marker_close)
            resp = json.loads(
                await _read_until_marker(process.stdout, marker_open, marker_close)
            )
            assert resp["id"] == "3"
            assert test_content in resp["result"]["message"]
    finally:
        process.terminate()
        await process.wait()


@pytest.mark.asyncio
async def test_trojan_process_create_over_pty(pty_bash_with_trojan):
    trojan_path, marker_hex = pty_bash_with_trojan
    marker_open = f"<linhai_trojanpy_{marker_hex}>"
    marker_close = f"</linhai_trojanpy_{marker_hex}>"

    process = await asyncio.create_subprocess_exec(
        "python3",
        trojan_path,
        marker_hex,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        await asyncio.sleep(0.5)

        create_req = {
            "jsonrpc": "2.0",
            "id": "4",
            "method": "process_create",
            "params": {"argv": ["echo", "hello world"], "wait_second": 2.0},
        }
        await _send_request(process.stdin, create_req, marker_open, marker_close)
        resp = json.loads(
            await _read_until_marker(process.stdout, marker_open, marker_close)
        )
        assert resp["id"] == "4"
        result = json.loads(resp["result"]["message"])
        assert "hello world" in result["stdout"]
    finally:
        process.terminate()
        await process.wait()
