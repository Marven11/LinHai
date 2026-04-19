"""SSH终端工具测试模块，测试SSH机器上的终端功能"""

import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from linhai.machine_control.posix_shell.posix_shell_control import PosixShellControl
from linhai.registry import Registry
from linhai.tool.base import ToolResultSuccess, ToolResultFailed


class TestSshTerminal(unittest.TestCase):
    """SSH终端测试类"""

    def setUp(self):
        """设置测试环境"""
        self.registry = Mock(spec=Registry)
        self.ssh_control = PosixShellControl(
            registry=self.registry,
        )
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # 模拟call_tool方法
        self.mock_call_tool = AsyncMock()
        self.ssh_control.call_tool = self.mock_call_tool

    def tearDown(self):
        """清理测试环境"""
        self.loop.close()

    def test_terminal_create(self):
        """测试创建远程终端"""

        async def test():
            # 模拟远程调用返回终端ID
            self.mock_call_tool.return_value = ToolResultSuccess(
                content="term_123456789"
            )

            result = await self.ssh_control.terminal_create(columns=80, lines=24)
            self.assertIsInstance(result, ToolResultSuccess)
            self.assertEqual(result.content, "term_123456789")

            # 验证call_tool被正确调用
            self.mock_call_tool.assert_called_once_with(
                "terminal_create", {"columns": 80, "lines": 24}
            )

        self.loop.run_until_complete(test())

    def test_terminal_send_string(self):
        """测试发送字符串到远程终端"""

        async def test():
            # 模拟远程调用返回成功消息
            self.mock_call_tool.return_value = ToolResultSuccess(
                content="已发送字符串: echo hello"
            )

            result = await self.ssh_control.terminal_send_string(
                terminal_id="term_123",
                string="echo hello",
                with_enter=True,
                wait_seconds=0.3,
            )
            self.assertIsInstance(result, ToolResultSuccess)
            self.assertIn("已发送字符串", result.content)

            # 验证call_tool被正确调用
            self.mock_call_tool.assert_called_once_with(
                "terminal_send_string",
                {
                    "term_id": "term_123",
                    "string": "echo hello",
                    "with_enter": True,
                    "wait_seconds": 0.3,
                },
            )

        self.loop.run_until_complete(test())

    def test_terminal_send_keys(self):
        """测试发送按键到远程终端"""

        async def test():
            # 模拟远程调用返回成功消息
            self.mock_call_tool.return_value = ToolResultSuccess(
                content="已发送按键: ['enter', 'a', 'b']"
            )

            result = await self.ssh_control.terminal_send_keys(
                terminal_id="term_123", keys=["enter", "a", "b"]
            )
            self.assertIsInstance(result, ToolResultSuccess)
            self.assertIn("已发送按键", result.content)

            # 验证call_tool被正确调用
            self.mock_call_tool.assert_called_once_with(
                "terminal_send_keys",
                {"term_id": "term_123", "keys": ["enter", "a", "b"]},
            )

        self.loop.run_until_complete(test())

    def test_terminal_read_screen(self):
        """测试读取远程终端屏幕内容"""

        async def test():
            # 模拟远程调用返回base64编码的屏幕内容（trojan.py实际返回格式）
            import base64

            # 注意：trojan.py中terminal_read_screen返回的是base64编码的字节流
            # 我们这里模拟base64编码的字符串，然后解码后比较
            raw_output = b"hello world\n$"
            mock_output = base64.b64encode(raw_output).decode("utf-8")
            self.mock_call_tool.return_value = ToolResultSuccess(content=mock_output)

            result = await self.ssh_control.terminal_read_screen(terminal_id="term_123")
            self.assertIsInstance(result, ToolResultSuccess)
            # posix_shell.py中的terminal_read_screen方法会解码base64
            self.assertEqual(result.content, raw_output.decode("utf-8"))

            # 验证call_tool被正确调用
            self.mock_call_tool.assert_called_once_with(
                "terminal_read_screen", {"term_id": "term_123"}
            )

        self.loop.run_until_complete(test())

    def test_terminal_close(self):
        """测试关闭远程终端"""

        async def test():
            # 模拟远程调用返回关闭消息
            self.mock_call_tool.return_value = ToolResultSuccess(
                content="已关闭终端 term_123"
            )

            result = await self.ssh_control.terminal_close(terminal_id="term_123")
            self.assertIsInstance(result, ToolResultSuccess)
            self.assertIn("已关闭终端", result.content)

            # 验证call_tool被正确调用
            self.mock_call_tool.assert_called_once_with(
                "terminal_close", {"term_id": "term_123"}
            )

        self.loop.run_until_complete(test())

    def test_terminal_lifecycle(self):
        """测试完整的终端生命周期"""
        import base64

        async def test():
            # 模拟返回数据
            raw_output = b"test output\n$"
            expected_output = raw_output.decode("utf-8")  # 解码后的字符串
            base64_output = base64.b64encode(raw_output).decode("utf-8")  # base64编码

            # 创建终端
            self.mock_call_tool.side_effect = [
                ToolResultSuccess(content="term_123"),  # create
                ToolResultSuccess(content="已发送字符串: echo test"),  # send_string
                ToolResultSuccess(content=base64_output),  # read_screen (base64编码)
                ToolResultSuccess(content="已关闭终端 term_123"),  # close
            ]

            # 1. 创建终端
            create_result = await self.ssh_control.terminal_create()
            self.assertEqual(create_result.content, "term_123")

            # 2. 发送字符串
            send_result = await self.ssh_control.terminal_send_string(
                terminal_id="term_123", string="echo test", with_enter=True
            )
            self.assertIn("已发送字符串", send_result.content)

            # 3. 读取屏幕
            read_result = await self.ssh_control.terminal_read_screen(
                terminal_id="term_123"
            )
            self.assertEqual(read_result.content, expected_output)

            # 4. 关闭终端
            close_result = await self.ssh_control.terminal_close(terminal_id="term_123")
            self.assertIn("已关闭终端", close_result.content)

            # 验证总共调用了4次call_tool
            self.assertEqual(self.mock_call_tool.call_count, 4)

        self.loop.run_until_complete(test())

    def test_error_handling(self):
        """测试错误处理（远程工具返回错误）"""

        async def test():
            # 模拟远程调用返回错误
            self.mock_call_tool.return_value = ToolResultFailed(
                content="工具执行失败: 终端不存在"
            )

            result = await self.ssh_control.terminal_read_screen(
                terminal_id="nonexistent"
            )
            self.assertIsInstance(result, ToolResultFailed)
            self.assertIn("工具执行失败", result.content)

        self.loop.run_until_complete(test())

    def test_create_terminal_invalid_parameters(self):
        """测试创建终端时参数无效的情况"""

        async def test():
            # 模拟远程调用返回错误信息
            self.mock_call_tool.return_value = ToolResultFailed(
                content="终端尺寸必须大于0: columns=0, lines=24"
            )

            # 注意：实际实现中参数验证在远程端，这里模拟远程返回错误
            result = await self.ssh_control.terminal_create(columns=0, lines=24)
            self.assertIsInstance(result, ToolResultFailed)
            self.assertIn("终端尺寸必须大于0", result.content)

        self.loop.run_until_complete(test())

    def test_send_keys_to_nonexistent_terminal(self):
        """测试发送按键到不存在的终端"""

        async def test():
            # 模拟远程调用返回错误
            self.mock_call_tool.return_value = ToolResultFailed(
                content="终端不存在: term_nonexistent"
            )

            result = await self.ssh_control.terminal_send_keys(
                terminal_id="term_nonexistent", keys=["enter", "a"]
            )
            self.assertIsInstance(result, ToolResultFailed)
            self.assertIn("终端不存在", result.content)

        self.loop.run_until_complete(test())

    def test_send_string_to_nonexistent_terminal(self):
        """测试发送字符串到不存在的终端"""

        async def test():
            # 模拟远程调用返回错误
            self.mock_call_tool.return_value = ToolResultFailed(
                content="终端不存在: term_nonexistent"
            )

            result = await self.ssh_control.terminal_send_string(
                terminal_id="term_nonexistent", string="echo test", with_enter=True
            )
            self.assertIsInstance(result, ToolResultFailed)
            self.assertIn("终端不存在", result.content)

        self.loop.run_until_complete(test())

    def test_read_nonexistent_terminal_screen(self):
        """测试读取不存在的终端屏幕"""

        async def test():
            # 模拟远程调用返回错误
            self.mock_call_tool.return_value = ToolResultFailed(
                content="终端不存在: term_nonexistent"
            )

            result = await self.ssh_control.terminal_read_screen(
                terminal_id="term_nonexistent"
            )
            self.assertIsInstance(result, ToolResultFailed)
            self.assertIn("终端不存在", result.content)

        self.loop.run_until_complete(test())

    def test_close_nonexistent_terminal(self):
        """测试关闭不存在的终端"""

        async def test():
            # 模拟远程调用返回错误
            self.mock_call_tool.return_value = ToolResultFailed(
                content="终端不存在: term_nonexistent"
            )

            result = await self.ssh_control.terminal_close(
                terminal_id="term_nonexistent"
            )
            self.assertIsInstance(result, ToolResultFailed)
            self.assertIn("终端不存在", result.content)

        self.loop.run_until_complete(test())

    def test_http_request_delegates_to_call_tool(self):
        """测试SSH机器通过call_tool调用远程http_request"""
        import base64
        import json

        async def test():
            self.mock_call_tool.return_value = ToolResultSuccess(
                content=json.dumps(
                    {
                        "status_code": 200,
                        "headers": {"content-type": "text/html"},
                        "content_base64": base64.b64encode(b"hello").decode(),
                        "content_type": "text/html",
                    }
                )
            )

            result = await self.ssh_control.http_request(
                method="GET", url="http://example.com"
            )
            self.assertIsInstance(result, ToolResultSuccess)
            self.mock_call_tool.assert_called_once_with(
                "http_request",
                {
                    "method": "GET",
                    "url": "http://example.com",
                    "follow_redirects": False,
                    "timeout": 60,
                },
            )

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
