import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from linhai.machine_control.http_message import HttpToolResult, HttpTextDiffToolResult
from linhai.machine_control.master_host.http import (
    _add_to_history,
    _history_files,
    _MAX_HISTORY,
    http_request as master_http_request,
)
from linhai.tool.base import FailedToolResult


class TestHistoryCache(unittest.TestCase):
    def setUp(self):
        _history_files.clear()

    def test_add_to_history(self):
        _add_to_history("/tmp/a.txt")
        self.assertEqual(_history_files, ["/tmp/a.txt"])

    def test_max_history_size(self):
        for i in range(10):
            _add_to_history(f"/tmp/{i}.txt")
        self.assertEqual(len(_history_files), _MAX_HISTORY)
        self.assertEqual(_history_files[-1], "/tmp/9.txt")


class TestMasterHttpRequest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _history_files.clear()

    def _make_httpx_response(self, status_code, headers, content):
        mock_resp = AsyncMock()
        mock_resp.status_code = status_code
        mock_resp.headers = headers
        mock_resp.content = content
        return mock_resp

    @patch(
        "linhai.machine_control.master_host.http.count_tokens",
        return_value=500,
    )
    async def test_small_body_no_cache_check(self, mock_tokens):
        resp = self._make_httpx_response(
            200,
            httpx.Headers({"content-type": "text/plain"}),
            b"small body",
        )
        with patch.object(httpx.AsyncClient, "request", return_value=resp):
            result = await master_http_request("GET", "http://example.com")
            self.assertIsInstance(result, HttpToolResult)

    @patch(
        "linhai.machine_control.master_host.http.count_tokens",
        return_value=500,
    )
    @patch("linhai.machine_control.http_message.count_tokens", return_value=6000)
    async def test_large_body_returns_httptoolresult_when_no_history(
        self, mock_ct, mock_diff_ct
    ):
        large = b"A" * 6000
        resp = self._make_httpx_response(
            200,
            httpx.Headers({"content-type": "text/plain"}),
            large,
        )
        with patch.object(httpx.AsyncClient, "request", return_value=resp):
            result = await master_http_request("GET", "http://example.com")
            self.assertIsInstance(result, HttpToolResult)
            self.assertIsNotNone(result.body_file)
            if result.body_file:
                os.unlink(result.body_file)

    @patch("linhai.machine_control.http_message.count_tokens", return_value=6000)
    async def test_large_body_cached_and_diff_small(self, mock_ct):
        tmpfile = tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt", mode="w", encoding="utf-8"
        )
        tmpfile.write("A" * 6000)
        tmpfile.close()
        _add_to_history(tmpfile.name)

        large = b"A" * 6000
        resp = self._make_httpx_response(
            200,
            httpx.Headers({"content-type": "text/plain"}),
            large,
        )
        with patch.object(httpx.AsyncClient, "request", return_value=resp):
            with patch(
                "linhai.machine_control.master_host.http.count_tokens",
                return_value=500,
            ):
                result = await master_http_request("GET", "http://example.com")
                self.assertIsInstance(result, HttpTextDiffToolResult)

        if isinstance(result, HttpToolResult) and result.body_file:
            os.unlink(result.body_file)
        os.unlink(tmpfile.name)

    @patch("linhai.machine_control.http_message.count_tokens", return_value=6000)
    async def test_large_body_cached_but_diff_large(self, mock_ct):
        tmpfile = tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt", mode="w", encoding="utf-8"
        )
        tmpfile.write("B" * 6000)
        tmpfile.close()
        _add_to_history(tmpfile.name)

        large = b"C" * 6000
        resp = self._make_httpx_response(
            200,
            httpx.Headers({"content-type": "text/plain"}),
            large,
        )
        with patch.object(httpx.AsyncClient, "request", return_value=resp):
            with patch(
                "linhai.machine_control.master_host.http.count_tokens",
                return_value=3000,
            ):
                result = await master_http_request("GET", "http://example.com")
                self.assertIsInstance(result, HttpToolResult)

        if isinstance(result, HttpToolResult) and result.body_file:
            os.unlink(result.body_file)
        os.unlink(tmpfile.name)

    @patch(
        "linhai.machine_control.master_host.http.count_tokens",
        return_value=500,
    )
    async def test_failed_request(self, mock_tokens):
        with patch.object(
            httpx.AsyncClient, "request", side_effect=httpx.RequestError("timeout")
        ):
            result = await master_http_request("GET", "http://example.com")
            self.assertIsInstance(result, FailedToolResult)


if __name__ == "__main__":
    unittest.main()
