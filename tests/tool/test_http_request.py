"""Unit tests for http_request tool."""

import unittest
import unittest.mock
import tempfile
import os
import asyncio

from linhai.tool.base import ToolSet, ToolArgInfo
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
            },
            required_args=["method", "url"],
        )(http_request)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_text_content(self, mock_request):
        """测试文本内容返回"""
        mock_response = unittest.mock.Mock()
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        text_content = "<html><body>Test Content</body></html>"
        mock_response.content = text_content.encode("utf-8")
        mock_response.text = text_content
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com"}
            )
        )
        # result是ToolResultMessage对象，需要检查其content
        self.assertIn("Test Content", result.content)
        self.assertIsInstance(result.content, str)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_binary_content(self, mock_request):
        """测试二进制内容保存到临时文件"""
        mock_response = unittest.mock.Mock()
        mock_response.headers = {"content-type": "image/png"}
        mock_response.content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com/image.png"}
            )
        )
        
        # 从ToolResultMessage中提取文件路径
        self.assertIn("二进制内容已保存到临时文件: ", result.content)
        # 提取路径：查找"二进制内容已保存到临时文件: "之后的内容
        path_start = result.content.find("二进制内容已保存到临时文件: ") + len("二进制内容已保存到临时文件: ")
        # 路径可能在<<data>>标记中，我们需要提取到下一个标记前
        temp_path = result.content[path_start:].split('<<')[0].strip()
        
        self.assertTrue(os.path.exists(temp_path))
        self.assertTrue(temp_path.endswith(".bin"))

        with open(temp_path, "rb") as f:
            content = f.read()
            self.assertEqual(content, mock_response.content)

        os.unlink(temp_path)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_default_user_agent(self, mock_request):
        """测试默认User-Agent设置"""
        mock_response = unittest.mock.Mock()
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
        # result是ToolResultMessage对象，需要检查其content
        self.assertIn("Test Encoding", result.content)

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
        # result是ToolErrorMessage对象，需要检查其content
        self.assertIn("请求失败", result.content)
        self.assertIn("Connection timeout", result.content)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_pdf_content(self, mock_request):
        """测试PDF二进制内容"""
        mock_response = unittest.mock.Mock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = b"%PDF-1.4\n1 0 obj\n<<"
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request", {"method": "GET", "url": "http://example.com/doc.pdf"}
            )
        )
        
        # 从ToolResultMessage中提取文件路径
        self.assertIn("二进制内容已保存到临时文件: ", result.content)
        path_start = result.content.find("二进制内容已保存到临时文件: ") + len("二进制内容已保存到临时文件: ")
        temp_path = result.content[path_start:].split('<<')[0].strip()
        
        self.assertTrue(os.path.exists(temp_path))
        self.assertTrue(temp_path.endswith(".bin"))
        os.unlink(temp_path)

    @unittest.mock.patch("httpx.AsyncClient.request")
    def test_http_request_zip_content(self, mock_request):
        """测试ZIP二进制内容"""
        mock_response = unittest.mock.Mock()
        mock_response.headers = {"content-type": "application/zip"}
        mock_response.content = b"PK\x03\x04\x14\x00\x00\x00\x08\x00"
        mock_request.return_value = mock_response

        result = asyncio.run(
            self.toolset.call_tool(
                "http_request",
                {"method": "GET", "url": "http://example.com/archive.zip"},
            )
        )
        
        # 从ToolResultMessage中提取文件路径
        self.assertIn("二进制内容已保存到临时文件: ", result.content)
        path_start = result.content.find("二进制内容已保存到临时文件: ") + len("二进制内容已保存到临时文件: ")
        temp_path = result.content[path_start:].split('<<')[0].strip()
        
        self.assertTrue(os.path.exists(temp_path))
        self.assertTrue(temp_path.endswith(".bin"))
        os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()
