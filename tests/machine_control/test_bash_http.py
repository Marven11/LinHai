import asyncio
import base64
import json
import unittest
from unittest.mock import AsyncMock, Mock

from linhai.machine_control.bash_host.bash_host import BashHostControl
from linhai.machine_control.bash_host.http import (
    _WRITEOUT_PREFIX,
    http_request,
)
from linhai.machine_control.http_message import HttpMessage
from linhai.registry import Registry
from linhai.tool.base import FailedToolResult


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _b64_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _make_host() -> BashHostControl:
    registry = Mock(spec=Registry)
    registry.send_if_exists = AsyncMock()
    host = BashHostControl(registry=registry)
    host._tmp_dir = "/tmp/linhai_test"
    host._has_curl = True
    host.execute_raw = AsyncMock()
    return host


class TestHttpRequestNoCurl(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_no_curl(self):
        async def test():
            host = _make_host()
            host._has_curl = False
            result = await host.http_request("GET", "http://example.com")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("curl", result.content)

        self.loop.run_until_complete(test())


class TestHttpRequestBasic(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_curl_not_found(self):
        async def test():
            host = _make_host()
            host.execute_raw.side_effect = [
                (1, "curl: not found", ""),
                (0, "", ""),
                (0, "0", ""),
                (0, "0", ""),
                (0, "", ""),
            ]
            result = await http_request(host, "GET", "http://example.com")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("curl", result.content)

        self.loop.run_until_complete(test())

    def test_simple_get(self):
        async def test():
            body = "hello world"
            header_text = "content-type: text/plain\r\n"
            host = _make_host()
            wo_line = f"{_WRITEOUT_PREFIX}200\ttext/plain"
            host.execute_raw.side_effect = [
                (0, wo_line, ""),
                (0, _b64(header_text), ""),
                (0, str(len(body.encode())), ""),
                (0, _b64(body), ""),
                (0, "", ""),
            ]
            result = await http_request(host, "GET", "http://example.com")
            self.assertIsInstance(result, HttpMessage)
            self.assertEqual(result.status_code, 200)
            self.assertIn("text/plain", result.headers.get("content-type", ""))

        self.loop.run_until_complete(test())

    def test_curl_failure(self):
        async def test():
            host = _make_host()
            host.execute_raw.side_effect = [
                (28, "", "curl: timeout"),
            ]
            result = await http_request(host, "GET", "http://example.com", timeout=5)
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("HTTP请求失败", result.content)

        self.loop.run_until_complete(test())

    def test_post_with_data(self):
        async def test():
            body = "ok"
            header_text = "content-type: text/plain\r\n"
            host = _make_host()
            wo_line = f"{_WRITEOUT_PREFIX}201\ttext/plain"
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, wo_line, ""),
                (0, _b64(header_text), ""),
                (0, str(len(body.encode())), ""),
                (0, _b64(body), ""),
                (0, "", ""),
            ]
            result = await http_request(
                host, "POST", "http://example.com", data="hello"
            )
            self.assertIsInstance(result, HttpMessage)
            self.assertEqual(result.status_code, 201)

        self.loop.run_until_complete(test())

    def test_post_with_json(self):
        async def test():
            body = "ok"
            header_text = "content-type: application/json\r\n"
            host = _make_host()
            wo_line = f"{_WRITEOUT_PREFIX}200\tapplication/json"
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, wo_line, ""),
                (0, _b64(header_text), ""),
                (0, str(len(body.encode())), ""),
                (0, _b64(body), ""),
                (0, "", ""),
            ]
            result = await http_request(
                host, "POST", "http://example.com", json_data={"key": "val"}
            )
            self.assertIsInstance(result, HttpMessage)
            self.assertEqual(result.status_code, 200)

        self.loop.run_until_complete(test())

    def test_empty_body(self):
        async def test():
            header_text = "content-type: text/plain\r\n"
            host = _make_host()
            wo_line = f"{_WRITEOUT_PREFIX}204\ttext/plain"
            host.execute_raw.side_effect = [
                (0, wo_line, ""),
                (0, _b64(header_text), ""),
                (0, "0", ""),
                (0, "", ""),
            ]
            result = await http_request(host, "DELETE", "http://example.com/resource")
            self.assertIsInstance(result, HttpMessage)
            self.assertEqual(result.status_code, 204)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
