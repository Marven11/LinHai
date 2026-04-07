"""Unit tests for http_request tool."""

import asyncio
import os
import re
import tempfile
import unittest
import unittest.mock

import httpx
from linhai.tool.base import ToolArgInfo, ToolSet
from linhai.machine_control.master_host.http import http_request


class TestHttpRequestTool(unittest.TestCase):
    """Test cases for the http_request tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.toolset = ToolSet()
        self.toolset.register_tool(
            name="http_request",
            desc="使用httpx库发送HTTP请求并获取响应内容",
            args={
                "method": ToolArgInfo(desc="HTTP方法，如GET、POST", type="str"),
                "url": ToolArgInfo(desc="请求的URL", type="str"),
                "params": ToolArgInfo(
                    desc="查询参数（字典形式）", type="Optional[dict]"
                ),
                "headers": ToolArgInfo(
                    desc="请求头（字典形式）", type="Optional[dict]"
                ),
                "data": ToolArgInfo(desc="请求体数据", type="Optional[str]"),
                "follow_redirects": ToolArgInfo(
                    desc="是否跟随重定向，默认True", type="bool"
                ),
                "timeout": ToolArgInfo(desc="超时时间（秒），默认60秒", type="int"),
            },
            required_args=["method", "url"],
        )(http_request)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_text_content(self, mock_request):
        """测试文本内容返回"""
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "text/html; charset=utf-8",
            "x-custom": "value",
        }
        text_content = "<html><body>Test Content</body></html>"
        mock_response.content = text_content.encode("utf-8")
        mock_response.text = text_content
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com"}
            )
        )
        # 直接检查返回的字符串中是否包含预期的标记和值
        self.assertIn("<<status_code>>200<<status_code>>", result.content)
        self.assertIn("<<is_binary>>false<<is_binary>>", result.content)
        self.assertIn(f"<<size>>{len(text_content)}<<size>>", result.content)
        # 检查headers
        self.assertIn("<<headers>>", result.content)
        # 检查body
        self.assertIn(f"<<body>>{text_content}<<body>>", result.content)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_binary_content(self, mock_request):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/png", "x-custom": "bin"}
        binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        mock_response.content = binary_content
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com/image.png"}
            )
        )
        self.assertIn("<<status_code>>200<<status_code>>", result.content)
        self.assertIn("<<is_binary>>true<<is_binary>>", result.content)
        self.assertIn(f"<<size>>{len(binary_content)}<<size>>", result.content)
        self.assertIn("<<body_file>>", result.content)
        match = re.search(r"<<body_file>>(.*?)<<body_file>>", result.content)
        self.assertIsNotNone(match)
        assert match is not None
        filepath = match.group(1)
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith(".bin"))
        with open(filepath, "rb") as f:
            content = f.read()
            self.assertEqual(content, binary_content)
        os.unlink(filepath)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_default_user_agent(self, mock_request):
        """测试默认User-Agent设置"""
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.content = b"test"
        mock_response.text = "test"
        mock_request.return_value = mock_response

        asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com"}
            )
        )

        call_args = mock_request.call_args
        self.assertIn("headers", call_args.kwargs)
        self.assertIn("User-Agent", call_args.kwargs["headers"])
        self.assertEqual(
            call_args.kwargs["headers"]["User-Agent"],
            "Mozilla/5.0 (compatible; LinHai/1.0; Chrome-like)",
        )

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_custom_headers(self, mock_request):
        """测试自定义headers保留并添加User-Agent"""
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        json_text = '{"key": "value"}'
        mock_response.content = json_text.encode("utf-8")
        mock_response.text = json_text
        mock_request.return_value = mock_response

        custom_headers = {"Authorization": "Bearer token123"}
        asyncio.run(
            self.toolset.call_tool(
                "http_request",
                {
                    "method": "GET",
                    "url": "http://example.com",
                    "headers": custom_headers,
                },
            )
        )

        call_args = mock_request.call_args
        self.assertIn("headers", call_args.kwargs)
        self.assertEqual(
            call_args.kwargs["headers"]["Authorization"], "Bearer token123"
        )
        self.assertIn("User-Agent", call_args.kwargs["headers"])

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_encoding_detection(self, mock_request):
        """测试编码检测"""
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        gbk_text = "Test Encoding"
        gbk_content = gbk_text.encode("gbk")
        mock_response.content = gbk_content
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com"}
            )
        )
        # 检查返回的内容中是否包含解码后的文本
        self.assertIn(gbk_text, result.content)
        self.assertIn("<<status_code>>200<<status_code>>", result.content)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_request_error(self, mock_request):
        """测试请求错误处理"""
        import httpx

        mock_request.side_effect = httpx.RequestError(
            "Connection timeout", request=unittest.mock.Mock()
        )

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com"}
            )
        )
        self.assertIn("请求失败", result.content)
        self.assertIn("Connection timeout", result.content)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_pdf_content(self, mock_request):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = b"%PDF-1.4\n1 0 obj\n<<"
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com/doc.pdf"}
            )
        )
        self.assertIn("<<status_code>>200<<status_code>>", result.content)
        self.assertIn("<<is_binary>>true<<is_binary>>", result.content)
        self.assertIn("<<body_file>>", result.content)
        match = re.search(r"<<body_file>>(.*?)<<body_file>>", result.content)
        if match:
            filepath = match.group(1)
            if os.path.exists(filepath):
                os.unlink(filepath)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_zip_content(self, mock_request):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/zip"}
        mock_response.content = b"PK\x03\x04\x14\x00\x00\x00\x08\x00"
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request",
                {"method": "GET", "url": "http://example.com/archive.zip"},
            )
        )
        self.assertIn("<<status_code>>200<<status_code>>", result.content)
        self.assertIn("<<is_binary>>true<<is_binary>>", result.content)
        self.assertIn("<<body_file>>", result.content)
        match = re.search(r"<<body_file>>(.*?)<<body_file>>", result.content)
        if match:
            filepath = match.group(1)
            if os.path.exists(filepath):
                os.unlink(filepath)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_timeout_parameter(self, mock_request):
        """测试timeout参数传递"""
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.content = b"test"
        mock_response.text = "test"
        mock_request.return_value = mock_response

        # 使用默认timeout
        asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com"}
            )
        )
        call_args = mock_request.call_args
        self.assertIn("timeout", call_args.kwargs)
        self.assertEqual(call_args.kwargs["timeout"], 60)

        # 使用自定义timeout
        asyncio.run(
            self.toolset.call_tool(
                "http_request",
                {
                    "method": "GET",
                    "url": "http://example.com",
                    "timeout": 30,
                },
            )
        )
        call_args = mock_request.call_args
        self.assertEqual(call_args.kwargs["timeout"], 30)

    @unittest.mock.patch(
        "linhai.machine_control.http_message.count_tokens", return_value=6000
    )
    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_large_text_body_saved_to_file(
        self, mock_request, mock_tokens
    ):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        large_text = "x" * 6000
        mock_response.content = large_text.encode("utf-8")
        mock_response.text = large_text
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com/large"}
            )
        )
        self.assertIn("<<status_code>>200<<status_code>>", result.content)
        self.assertIn("<<is_binary>>false<<is_binary>>", result.content)
        self.assertIn(f"<<size>>{len(large_text)}<<size>>", result.content)
        self.assertIn("<<body_file>>", result.content)
        self.assertNotIn("<<body>>", result.content)
        match = re.search(r"<<body_file>>(.*?)<<body_file>>", result.content)
        self.assertIsNotNone(match)
        assert match is not None
        filepath = match.group(1)
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith(".txt"))
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertEqual(content, large_text)
        os.unlink(filepath)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_small_text_body_returned_directly(self, mock_request):
        """测试小文本响应体（<=5000字符）直接返回"""
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        small_text = "x" * 1000
        mock_response.content = small_text.encode("utf-8")
        mock_response.text = small_text
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com/small"}
            )
        )
        self.assertIn("<<status_code>>200<<status_code>>", result.content)
        self.assertIn("<<is_binary>>false<<is_binary>>", result.content)
        self.assertIn(f"<<size>>{len(small_text)}<<size>>", result.content)
        # 小响应体应该直接返回body，而不是保存到文件
        self.assertIn(f"<<body>>{small_text}<<body>>", result.content)
        self.assertNotIn("<<body_file>>", result.content)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_file_path_is_temporary(self, mock_request):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        binary_content = b"%PDF-1.4\n1 0 obj\n<<"
        mock_response.content = binary_content
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com/doc.pdf"}
            )
        )
        self.assertIn("<<status_code>>200<<status_code>>", result.content)
        self.assertIn("<<is_binary>>true<<is_binary>>", result.content)
        self.assertIn("<<body_file>>", result.content)

        match = re.search(r"<<body_file>>(.*?)<<body_file>>", result.content)
        self.assertIsNotNone(match)
        assert match is not None
        filepath = match.group(1)

        temp_dir = tempfile.gettempdir()
        self.assertTrue(
            filepath.startswith(temp_dir),
            f"文件路径应该在临时目录中，但得到: {filepath}",
        )

        hardcoded_path = "/home/cube/.local/share/linhai/conversation/1a28cf90-1879-47ae-8fba-70f68fad80f0/http_responses"
        self.assertNotIn(
            hardcoded_path,
            filepath,
            f"文件路径不应该包含硬编码路径，但得到: {filepath}",
        )

        if os.path.exists(filepath):
            os.unlink(filepath)


if __name__ == "__main__":
    unittest.main()
