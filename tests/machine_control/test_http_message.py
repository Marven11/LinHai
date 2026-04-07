import asyncio
import os
import unittest
from unittest.mock import patch

from linhai.machine_control.http_message import (
    HttpMessage,
    _is_binary,
    build_http_message,
)
from linhai.tool.base import ToolResultFailed


class TestIsBinary(unittest.TestCase):
    def test_image_content_type(self):
        is_bin, encoding = _is_binary("image/png", b"\x89PNG")
        self.assertTrue(is_bin)
        self.assertIsNone(encoding)

    def test_pdf_content_type(self):
        is_bin, encoding = _is_binary("application/pdf", b"%PDF")
        self.assertTrue(is_bin)
        self.assertIsNone(encoding)

    def test_zip_content_type(self):
        is_bin, encoding = _is_binary("application/zip", b"PK")
        self.assertTrue(is_bin)
        self.assertIsNone(encoding)

    def test_audio_content_type(self):
        is_bin, encoding = _is_binary("audio/mpeg", b"\xff\xfb")
        self.assertTrue(is_bin)
        self.assertIsNone(encoding)

    def test_video_content_type(self):
        is_bin, encoding = _is_binary("video/mp4", b"\x00\x00")
        self.assertTrue(is_bin)
        self.assertIsNone(encoding)

    def test_text_with_charset(self):
        is_bin, encoding = _is_binary("text/html; charset=utf-8", b"hello")
        self.assertFalse(is_bin)
        self.assertEqual(encoding, "utf-8")

    def test_text_with_gbk_charset(self):
        is_bin, encoding = _is_binary(
            "text/html; charset=gbk", "\u6d4b\u8bd5".encode("gbk")
        )
        self.assertFalse(is_bin)
        self.assertEqual(encoding, "gbk")

    def test_text_without_charset(self):
        is_bin, encoding = _is_binary("text/plain", b"hello world")
        self.assertFalse(is_bin)
        self.assertIsNotNone(encoding)

    def test_octet_stream(self):
        is_bin, encoding = _is_binary("application/octet-stream", b"\x00\x01")
        self.assertTrue(is_bin)
        self.assertIsNone(encoding)

    def test_binary_in_content_type(self):
        is_bin, encoding = _is_binary("application/x-binary", b"data")
        self.assertTrue(is_bin)
        self.assertIsNone(encoding)


class TestHttpMessage(unittest.TestCase):
    def test_content_with_body(self):
        msg = HttpMessage(
            status_code=200,
            headers={"content-type": "text/plain"},
            is_binary=False,
            size=5,
            body="hello",
        )
        self.assertIn("<<status_code>>200<<status_code>>", msg.content)
        self.assertIn("<<is_binary>>false<<is_binary>>", msg.content)
        self.assertIn("<<size>>5<<size>>", msg.content)
        self.assertIn("<<body>>hello<<body>>", msg.content)
        self.assertNotIn("<<body_file>>", msg.content)

    def test_content_with_body_file(self):
        msg = HttpMessage(
            status_code=200,
            headers={"content-type": "image/png"},
            is_binary=True,
            size=100,
            body_file="/tmp/test.bin",
        )
        self.assertIn("<<status_code>>200<<status_code>>", msg.content)
        self.assertIn("<<is_binary>>true<<is_binary>>", msg.content)
        self.assertIn("<<body_file>>/tmp/test.bin<<body_file>>", msg.content)
        self.assertNotIn("<<body>>", msg.content)

    def test_isinstance_tool_result_success(self):
        from linhai.tool.base import ToolResultSuccess

        msg = HttpMessage(
            status_code=200,
            headers={},
            is_binary=False,
            size=0,
            body="",
        )
        self.assertIsInstance(msg, ToolResultSuccess)

    def test_headers_serialized_as_json(self):
        import json

        headers = {"content-type": "text/html", "x-custom": "value"}
        msg = HttpMessage(
            status_code=200,
            headers=headers,
            is_binary=False,
            size=0,
            body="",
        )
        self.assertIn("<<headers>>", msg.content)
        start = msg.content.index("<<headers>>") + len("<<headers>>")
        end = msg.content.index("<<headers>>", start)
        parsed = json.loads(msg.content[start:end])
        self.assertEqual(parsed, headers)


class TestBuildHttpMessage(unittest.IsolatedAsyncioTestCase):
    async def test_small_text_body_inline(self):
        content = b"Hello, World!"
        result = await build_http_message(
            status_code=200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content=content,
            content_type="text/plain; charset=utf-8",
        )
        self.assertIsInstance(result, HttpMessage)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.is_binary)
        self.assertEqual(result.body, "Hello, World!")
        self.assertIsNone(result.body_file)

    @patch("linhai.machine_control.http_message.count_tokens", return_value=6000)
    async def test_large_text_body_saved_to_file(self, mock_tokens):
        large_text = "A" * 6000
        content = large_text.encode("utf-8")
        result = await build_http_message(
            status_code=200,
            headers={"content-type": "text/plain"},
            content=content,
            content_type="text/plain",
        )
        self.assertIsInstance(result, HttpMessage)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.is_binary)
        self.assertIsNone(result.body)
        self.assertIsNotNone(result.body_file)
        self.assertTrue(os.path.exists(result.body_file))
        with open(result.body_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), large_text)
        os.unlink(result.body_file)

    async def test_binary_content_saved_to_file(self):
        binary_data = b"\x89PNG\r\n\x1a\n" + b"x" * 100
        result = await build_http_message(
            status_code=200,
            headers={"content-type": "image/png"},
            content=binary_data,
            content_type="image/png",
        )
        self.assertIsInstance(result, HttpMessage)
        self.assertTrue(result.is_binary)
        self.assertIsNone(result.body)
        self.assertIsNotNone(result.body_file)
        self.assertTrue(os.path.exists(result.body_file))
        with open(result.body_file, "rb") as f:
            self.assertEqual(f.read(), binary_data)
        os.unlink(result.body_file)

    async def test_gbk_encoding(self):
        text = "\u6d4b\u8bd5\u5185\u5bb9"
        content = text.encode("gbk")
        result = await build_http_message(
            status_code=200,
            headers={"content-type": "text/html; charset=gbk"},
            content=content,
            content_type="text/html; charset=gbk",
        )
        self.assertIsInstance(result, HttpMessage)
        self.assertEqual(result.body, text)

    async def test_empty_content(self):
        result = await build_http_message(
            status_code=204,
            headers={},
            content=b"",
            content_type="text/plain",
        )
        self.assertIsInstance(result, HttpMessage)
        self.assertEqual(result.status_code, 204)
        self.assertEqual(result.body, "")

    async def test_decode_failure(self):
        content = b"\xff\xfe\xfd"
        result = await build_http_message(
            status_code=200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content=content,
            content_type="text/plain; charset=utf-8",
        )
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("\u65e0\u6cd5\u4f7f\u7528\u7f16\u7801", result.content)

    async def test_error_status_code_still_returns_http_message(self):
        result = await build_http_message(
            status_code=404,
            headers={"content-type": "text/html"},
            content=b"Not Found",
            content_type="text/html",
        )
        self.assertIsInstance(result, HttpMessage)
        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.body, "Not Found")

    @patch("linhai.machine_control.http_message.count_tokens", return_value=6000)
    async def test_large_body_file_is_txt(self, mock_tokens):
        content = b"x" * 6000
        result = await build_http_message(
            status_code=200,
            headers={"content-type": "text/plain"},
            content=content,
            content_type="text/plain",
        )
        self.assertIsInstance(result, HttpMessage)
        self.assertIsNotNone(result.body_file)
        self.assertTrue(result.body_file.endswith(".txt"))
        os.unlink(result.body_file)

    async def test_binary_body_file_is_bin(self):
        result = await build_http_message(
            status_code=200,
            headers={"content-type": "application/pdf"},
            content=b"%PDF-1.4",
            content_type="application/pdf",
        )
        self.assertIsInstance(result, HttpMessage)
        self.assertIsNotNone(result.body_file)
        self.assertTrue(result.body_file.endswith(".bin"))
        os.unlink(result.body_file)


if __name__ == "__main__":
    unittest.main()
