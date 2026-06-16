import asyncio
import json
import math
import base64
import enum
import os
import tempfile

import pytest
from linhai.task_supervisor import PlainTaskSupervisor

METADATA_MAX_LENGTH = 22


class _DecodeState(enum.Enum):
    WAITING_DATA = 0
    COMPOSING = 1
    COMPOSED = 2


_SAFE_BYTES = frozenset(
    b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 {}[]":,._-\\'
)


def _encode(
    data: bytes, marker: bytes, max_length: int, text_only: bool
) -> list[bytes]:
    if text_only and data and _SAFE_BYTES.issuperset(data):
        text_only = False
    assert max_length > METADATA_MAX_LENGTH
    step = (
        max_length - METADATA_MAX_LENGTH
        if not text_only
        else math.floor((max_length - 3) / 4 * 3) - METADATA_MAX_LENGTH
    )
    slices = [data[i : i + step] for i in range(0, len(data), step)]
    if text_only:
        b64s = (base64.b64encode(b) for b in slices)
        fractions = [
            marker + b"B" + str(len(b64)).encode() + b" " + b64 for b64 in b64s
        ]
    else:
        fractions = [marker + b"R" + str(len(b)).encode() + b" " + b for b in slices]
    return fractions + [marker + b"X1 ;"]


def _decode(fraction: bytes) -> tuple[_DecodeState, bytes, bytes]:
    if len(fraction) <= METADATA_MAX_LENGTH and b" " not in fraction:
        return _DecodeState.WAITING_DATA, b"", fraction

    metadata, data = fraction.split(b" ", maxsplit=1)
    action, length_str = metadata[0:1], metadata[1:].decode("ascii")
    if not length_str:
        return _DecodeState.WAITING_DATA, b"", fraction
    length = int(length_str)
    if len(data) < length:
        return _DecodeState.WAITING_DATA, b"", fraction
    if action == b"R":
        return _DecodeState.COMPOSING, data[:length], data[length:]
    if action == b"B":
        return _DecodeState.COMPOSING, base64.b64decode(data[:length]), data[length:]
    if action == b"X":
        return _DecodeState.COMPOSED, b"", data[length:]
    else:
        raise RuntimeError(f"Malformed data: {metadata=} {data=} ")


class _PulseDecoder:
    def __init__(self, marker: bytes):
        self.is_waiting_marker = True
        self.marker = marker
        self.composed: list[bytes] = []
        self.composing = b""
        self.stream_remains = b""

    def comsume(self, stream: bytes):
        stream = self.stream_remains + stream
        while stream:
            if self.is_waiting_marker:
                if len(stream) <= len(self.marker):
                    break
                pos = stream.find(self.marker)
                if pos != -1:
                    stream = stream[pos + len(self.marker) :]
                    self.is_waiting_marker = False
                else:
                    stream = stream[-len(self.marker) :]
                    break
            else:
                state, decoded, remains = _decode(stream)
                stream = remains
                self.composing += decoded
                if state == _DecodeState.COMPOSED:
                    self.composed.append(self.composing)
                    self.composing = b""

                if state == _DecodeState.WAITING_DATA:
                    break
                else:
                    self.is_waiting_marker = True

        self.stream_remains = stream

    def emit_composed(self):
        result = self.composed
        self.composed = []
        return result


class _PulseEncoder:
    def __init__(self, marker: bytes, max_length: int, text_only: bool):
        self.marker = marker
        self.max_length = max_length
        self.text_only = text_only

    def encode(self, data: bytes):
        return _encode(data, self.marker, self.max_length, self.text_only)


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
    marker_str: str,
    timeout: float = 10.0,
) -> str:
    decoder = _PulseDecoder(marker_str.encode())
    while True:
        for composed in decoder.emit_composed():
            return composed.decode("utf-8", errors="replace")
        try:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError("读取marker超时")
        if not chunk:
            raise ConnectionError("进程已关闭")
        decoder.comsume(chunk)


async def _send_request(writer: asyncio.StreamWriter, request: dict, marker_str: str):
    encoder = _PulseEncoder(marker_str.encode(), 4096, True)
    fractions = encoder.encode(json.dumps(request).encode())
    for fraction in fractions:
        writer.write(fraction)
    await writer.drain()


@pytest.mark.asyncio
async def test_trojan_ping_over_pty(pty_bash_with_trojan):
    trojan_path, marker_hex = pty_bash_with_trojan
    marker_str = f"<linhai_pulse_{marker_hex}>"

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

        assert process.stdin is not None and process.stdout is not None

        request = {"jsonrpc": "2.0", "id": "1", "method": "ping", "params": {}}
        await _send_request(process.stdin, request, marker_str)

        response_str = await _read_until_marker(process.stdout, marker_str)
        response = json.loads(response_str)
        assert response["id"] == "1"
        assert response["result"]["message"] == "pong"
    finally:
        process.terminate()
        await process.wait()


@pytest.mark.asyncio
async def test_trojan_file_operations_over_pty(pty_bash_with_trojan):
    trojan_path, marker_hex = pty_bash_with_trojan
    marker_str = f"<linhai_pulse_{marker_hex}>"

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
                },
            }
            assert process.stdin is not None and process.stdout is not None

            await _send_request(process.stdin, write_req, marker_str)
            resp = json.loads(await _read_until_marker(process.stdout, marker_str))
            assert resp["id"] == "2"
            assert "error" not in resp

            read_req = {
                "jsonrpc": "2.0",
                "id": "3",
                "method": "read_file",
                "params": {"filepath": test_file},
            }
            await _send_request(process.stdin, read_req, marker_str)
            resp = json.loads(await _read_until_marker(process.stdout, marker_str))
            assert resp["id"] == "3"
            assert test_content in resp["result"]["message"]
    finally:
        process.terminate()
        await process.wait()


@pytest.mark.asyncio
async def test_trojan_process_create_over_pty(pty_bash_with_trojan):
    trojan_path, marker_hex = pty_bash_with_trojan
    marker_str = f"<linhai_pulse_{marker_hex}>"

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
        assert process.stdin is not None and process.stdout is not None

        await _send_request(process.stdin, create_req, marker_str)
        resp = json.loads(await _read_until_marker(process.stdout, marker_str))
        assert resp["id"] == "4"
        result = json.loads(resp["result"]["message"])
        assert "hello world" in result["stdout"]
    finally:
        process.terminate()
        await process.wait()
