"""HTTP请求工具测试"""

import unittest
import asyncio
import json
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
import httpx

from linhai.machine_control.master_host.master_host import MasterHostControl
from linhai.registry import Registry
from linhai.sandbox import NoSandbox
from linhai.tool.base import FailedToolResult
from linhai.machine_control.http_message import HttpToolResult


class TestHttpRequest(unittest.IsolatedAsyncioTestCase):
    """测试http_request工具"""

    def setUp(self):
        registry = Registry()
        registry.register_member("process_sandbox", NoSandbox())
        self.host_control = MasterHostControl(registry)

    def extract_content_parts(self, content: str) -> dict:
        """解析<<>>格式的内容为字典"""
        parts = {}
        import re

        # 正则表达式匹配 <<key>>value<<key>> 格式
        pattern = r"<<([^>]+)>>([^<]*)<<\1>>"
        matches = re.findall(pattern, content)
        for key, value in matches:
            parts[key] = value
        return parts

    async def test_http_request_success_small_body(self):
        """测试成功响应，body小于5000字符"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "text/plain; charset=utf-8",
            "x-custom": "value",
        }
        mock_response.text = "Hello, World!" * 100  # 约1300字符
        mock_response.content = b"Hello, World!" * 100

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await self.host_control.http_request("GET", "http://example.com")

            self.assertIsInstance(result, HttpToolResult)
            parts = self.extract_content_parts(result.content)

            self.assertEqual(parts.get("status_code"), "200")
            self.assertIn("headers", parts)
            headers_dict = json.loads(parts["headers"])
            self.assertEqual(
                headers_dict.get("content-type"), "text/plain; charset=utf-8"
            )
            self.assertEqual(headers_dict.get("x-custom"), "value")
            self.assertEqual(parts.get("is_binary"), "false")
            self.assertIn("size", parts)
            self.assertIn("body", parts)
            self.assertNotIn("body_file", parts)

    @patch("linhai.machine_control.http_message.count_tokens", return_value=6000)
    async def test_http_request_success_large_body(self, mock_tokens):
        """测试成功响应，body超过5000 token阈值"""
        large_text = "A" * 6000
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = large_text
        mock_response.content = large_text.encode("utf-8")

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await self.host_control.http_request("GET", "http://example.com")

            self.assertIsInstance(result, HttpToolResult)
            parts = self.extract_content_parts(result.content)

            self.assertEqual(parts.get("status_code"), "200")
            self.assertIn("headers", parts)
            self.assertEqual(parts.get("is_binary"), "false")
            self.assertIn("size", parts)
            self.assertIn("body_file", parts)
            self.assertNotIn("body", parts)

            filepath = parts.get("body_file")
            self.assertIsNotNone(filepath)
            self.assertTrue(os.path.exists(filepath))
            with open(filepath, "r", encoding="utf-8") as f:
                file_content = f.read()
            self.assertEqual(file_content, large_text)

            if os.path.exists(filepath):
                os.unlink(filepath)

    async def test_http_request_binary_response(self):
        """测试二进制响应"""
        binary_data = b"\x89PNG\r\n\x1a\n" + b"x" * 1000
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/png"}
        mock_response.content = binary_data

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await self.host_control.http_request(
                "GET", "http://example.com/image.png"
            )

            self.assertIsInstance(result, HttpToolResult)
            parts = self.extract_content_parts(result.content)

            self.assertEqual(parts.get("status_code"), "200")
            self.assertIn("headers", parts)
            self.assertEqual(parts.get("is_binary"), "true")
            self.assertIn("size", parts)
            self.assertIn("body_file", parts)
            self.assertNotIn("body", parts)

            # 验证临时文件存在且内容正确
            filepath = parts.get("body_file")
            self.assertIsNotNone(filepath)
            self.assertTrue(os.path.exists(filepath))
            with open(filepath, "rb") as f:
                file_content = f.read()
            self.assertEqual(file_content, binary_data)

            # 清理临时文件
            if os.path.exists(filepath):
                os.unlink(filepath)

    async def test_http_request_error_response(self):
        """测试错误响应（如404）"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "Not Found"
        mock_response.content = b"Not Found"

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await self.host_control.http_request(
                "GET", "http://example.com/notfound"
            )

            self.assertIsInstance(result, HttpToolResult)  # HTTP错误也是成功响应
            parts = self.extract_content_parts(result.content)

            self.assertEqual(parts.get("status_code"), "404")
            self.assertIn("headers", parts)
            self.assertEqual(parts.get("is_binary"), "false")
            self.assertIn("body", parts)
            self.assertEqual(parts.get("body"), "Not Found")

    async def test_http_request_network_error(self):
        """测试网络错误"""
        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            # 模拟httpx.RequestError异常
            mock_client.request.side_effect = httpx.RequestError("Connection failed")
            mock_client_class.return_value = mock_client

            result = await self.host_control.http_request("GET", "http://example.com")

            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("请求失败", result.content)

    async def test_http_request_with_params_and_headers(self):
        """测试带参数和请求头的请求"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"status": "ok"}'
        mock_response.content = b'{"status": "ok"}'

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            params = {"q": "test", "page": 1}
            headers = {"Authorization": "Bearer token"}
            data = "request body"

            result = await self.host_control.http_request(
                "POST",
                "http://example.com/api",
                params=params,
                headers=headers,
                data=data,
                follow_redirects=False,
                timeout=30,
            )

            self.assertIsInstance(result, HttpToolResult)
            # 验证mock被正确调用
            mock_client.request.assert_called_once()
            call_args = mock_client.request.call_args
            # 所有参数都是关键字参数，所以call_args[0]为空，call_args[1]为关键字参数字典
            kwargs = call_args[1]
            self.assertEqual(kwargs["method"], "POST")
            self.assertEqual(kwargs["url"], "http://example.com/api")
            self.assertEqual(kwargs["params"], params)
            self.assertEqual(kwargs["headers"].get("Authorization"), "Bearer token")
            self.assertEqual(kwargs["content"], data)
            self.assertEqual(kwargs["follow_redirects"], False)
            self.assertEqual(kwargs["timeout"], 30)

    async def test_http_request_content_type_with_charset(self):
        """测试带charset的content-type"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=gbk"}
        # 模拟gbk编码的内容
        mock_response.content = "测试".encode("gbk")
        # 需要设置response.text属性，但工具中可能会根据编码解码，这里我们模拟解码过程
        # 由于我们模拟了编码，工具会使用我们提供的编码解码，所以可以设置text为解码后的字符串
        mock_response.text = "测试"  # 假设解码后

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await self.host_control.http_request("GET", "http://example.com")

            self.assertIsInstance(result, HttpToolResult)
            parts = self.extract_content_parts(result.content)
            self.assertEqual(parts.get("status_code"), "200")
            self.assertIn("headers", parts)
            headers_dict = json.loads(parts["headers"])
            self.assertEqual(headers_dict.get("content-type"), "text/html; charset=gbk")

    async def test_http_request_with_auth(self):
        """测试带auth参数的请求"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"authenticated": true}'
        mock_response.content = b'{"authenticated": true}'

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            auth = ("user", "pass")
            result = await self.host_control.http_request(
                "GET", "http://example.com/protected", auth=auth
            )

            self.assertIsInstance(result, HttpToolResult)
            mock_client.request.assert_called_once()
            call_args = mock_client.request.call_args
            kwargs = call_args[1]
            self.assertEqual(kwargs["auth"], auth)

    async def test_http_request_with_cookies(self):
        """测试带cookies参数的请求"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"status": "ok"}'
        mock_response.content = b'{"status": "ok"}'

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            cookies = {"session_id": "abc123"}
            result = await self.host_control.http_request(
                "GET", "http://example.com/", cookies=cookies
            )

            self.assertIsInstance(result, HttpToolResult)
            mock_client.request.assert_called_once()
            call_args = mock_client.request.call_args
            kwargs = call_args[1]
            self.assertEqual(kwargs["cookies"], cookies)

    async def test_http_request_with_json_data(self):
        """测试带json_data参数的请求"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"created": true}'
        mock_response.content = b'{"created": true}'

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            json_data = {"name": "test", "value": 123}
            result = await self.host_control.http_request(
                "POST", "http://example.com/api", json_data=json_data
            )

            self.assertIsInstance(result, HttpToolResult)
            mock_client.request.assert_called_once()
            call_args = mock_client.request.call_args
            kwargs = call_args[1]
            self.assertEqual(kwargs["json"], json_data)

    async def test_http_request_with_proxy(self):
        """测试带proxy参数的请求"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"status": "ok"}'
        mock_response.content = b'{"status": "ok"}'

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            proxy = "http://proxy.example.com:8080"
            result = await self.host_control.http_request(
                "GET", "http://example.com/", proxy=proxy
            )

            self.assertIsInstance(result, HttpToolResult)
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args
            kwargs = call_args[1]
            self.assertEqual(kwargs["proxy"], proxy)

    async def test_http_request_with_verify(self):
        """测试带verify参数的请求"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"status": "ok"}'
        mock_response.content = b'{"status": "ok"}'

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            verify = False
            result = await self.host_control.http_request(
                "GET", "http://example.com/", verify=verify
            )

            self.assertIsInstance(result, HttpToolResult)
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args
            kwargs = call_args[1]
            self.assertEqual(kwargs["verify"], verify)

    async def test_http_request_with_auth_list(self):
        """测试带auth参数(列表类型，模拟LLM传入)的请求"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"authenticated": true}'
        mock_response.content = b'{"authenticated": true}'

        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            auth_list = ["user", "pass"]
            result = await self.host_control.http_request(
                "GET", "http://example.com/protected", auth=tuple(auth_list)
            )

            self.assertIsInstance(result, HttpToolResult)
            mock_client.request.assert_called_once()
            call_args = mock_client.request.call_args
            kwargs = call_args[1]
            self.assertEqual(kwargs["auth"], ("user", "pass"))

    async def test_http_request_non_request_error(self):
        """测试非httpx.RequestError异常被捕获"""
        with patch(
            "linhai.machine_control.master_host.http.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.request.side_effect = ValueError("unexpected error")
            mock_client_class.return_value = mock_client

            result = await self.host_control.http_request("GET", "http://example.com")

            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("处理响应失败", result.content)
            self.assertIn("ValueError", result.content)

    async def test_http_request_tool_auth_list_to_tuple(self):
        """测试http_request_tool将list类型的auth转换为tuple"""
        from unittest.mock import MagicMock
        from linhai.machine_control.tools import register_machine_control_tools

        mock_host = MagicMock()
        mock_host.http_request = AsyncMock()
        mock_machine_control = MagicMock()
        mock_machine_control.machines = {"master_host": mock_host}
        mock_machine_control.target_machine = "master_host"

        toolset = register_machine_control_tools(mock_machine_control)
        tool_func = toolset.get_tool("http_request")

        await tool_func(
            method="GET",
            url="http://example.com",
            auth=["admin", "xxx"],
        )

        mock_host.http_request.assert_called_once()
        call_args = mock_host.http_request.call_args
        auth_arg = call_args.args[7]
        self.assertIsInstance(auth_arg, tuple)
        self.assertEqual(auth_arg, ("admin", "xxx"))


if __name__ == "__main__":
    unittest.main()
