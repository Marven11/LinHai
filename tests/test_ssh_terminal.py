"""SSH终端工具测试模块，测试SSH机器上的终端功能"""

import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from linhai.machine_control.ssh_host.ssh_host import SshMachineControl
from linhai.group_chat import GroupChat
from linhai.tool.base import ToolResultMessage, ToolErrorMessage


class TestSshTerminal(unittest.TestCase):
    """SSH终端测试类"""

    def setUp(self):
        """设置测试环境"""
        self.group_chat = Mock(spec=GroupChat)
        self.ssh_control = SshMachineControl(
            host="test-host",
            group_chat=self.group_chat,
            port=22,
            username="testuser",
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
            self.mock_call_tool.return_value = ToolResultMessage("term_123456789")

            result = await self.ssh_control.terminal_create(columns=80, lines=24)
            self.assertIsInstance(result, ToolResultMessage)
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
            self.mock_call_tool.return_value = ToolResultMessage(
                "已发送字符串: echo hello"
            )

            result = await self.ssh_control.terminal_send_string(
                terminal_id="term_123",
                string="echo hello",
                with_enter=True,
                wait_seconds=0.3,
            )
            self.assertIsInstance(result, ToolResultMessage)
            self.assertIn("已发送字符串", result.content)

            # 验证call_tool被正确调用
            self.mock_call_tool.assert_called_once_with(
                "terminal_send_string",
                {"term_id": "term_123", "string": "echo hello", "with_enter": True},
            )

        self.loop.run_until_complete(test())

    def test_terminal_send_keys(self):
        """测试发送按键到远程终端"""

        async def test():
            # 模拟远程调用返回成功消息
            self.mock_call_tool.return_value = ToolResultMessage(
                "已发送按键: ['enter', 'a', 'b']"
            )

            result = await self.ssh_control.terminal_send_keys(
                terminal_id="term_123", keys=["enter", "a", "b"]
            )
            self.assertIsInstance(result, ToolResultMessage)
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
            mock_output = base64.b64encode(raw_output).decode('utf-8')
            self.mock_call_tool.return_value = ToolResultMessage(
                mock_output
            )

            result = await self.ssh_control.terminal_read_screen(
                terminal_id="term_123"
            )
            self.assertIsInstance(result, ToolResultMessage)
            # ssh_host.py中的terminal_read_screen方法会解码base64
            self.assertEqual(result.content, raw_output.decode('utf-8'))

            # 验证call_tool被正确调用
            self.mock_call_tool.assert_called_once_with(
                "terminal_read_screen", {"term_id": "term_123"}
            )

        self.loop.run_until_complete(test())

    def test_terminal_close(self):
        """测试关闭远程终端"""

        async def test():
            # 模拟远程调用返回关闭消息
            self.mock_call_tool.return_value = ToolResultMessage(
                "已关闭终端 term_123"
            )

            result = await self.ssh_control.terminal_close(
                terminal_id="term_123"
            )
            self.assertIsInstance(result, ToolResultMessage)
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
            expected_output = raw_output.decode('utf-8')  # 解码后的字符串
            base64_output = base64.b64encode(raw_output).decode('utf-8')  # base64编码
            
            # 创建终端
            self.mock_call_tool.side_effect = [
                ToolResultMessage("term_123"),  # create
                ToolResultMessage("已发送字符串: echo test"),  # send_string
                ToolResultMessage(base64_output),  # read_screen (base64编码)
                ToolResultMessage("已关闭终端 term_123"),  # close
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
            close_result = await self.ssh_control.terminal_close(
                terminal_id="term_123"
            )
            self.assertIn("已关闭终端", close_result.content)

            # 验证总共调用了4次call_tool
            self.assertEqual(self.mock_call_tool.call_count, 4)

        self.loop.run_until_complete(test())

    def test_error_handling(self):
        """测试错误处理（远程工具返回错误）"""

        async def test():
            # 模拟远程调用返回错误
            self.mock_call_tool.return_value = ToolErrorMessage(
                "工具执行失败: 终端不存在"
            )

            result = await self.ssh_control.terminal_read_screen(
                terminal_id="nonexistent"
            )
            self.assertIsInstance(result, ToolErrorMessage)
            self.assertIn("工具执行失败", result.content)

        self.loop.run_until_complete(test())

    def test_create_terminal_invalid_parameters(self):
        """测试创建终端时参数无效的情况"""

        async def test():
            # 模拟远程调用返回错误信息
            self.mock_call_tool.return_value = ToolErrorMessage(
                "终端尺寸必须大于0: columns=0, lines=24"
            )

            # 注意：实际实现中参数验证在远程端，这里模拟远程返回错误
            result = await self.ssh_control.terminal_create(columns=0, lines=24)
            self.assertIsInstance(result, ToolErrorMessage)
            self.assertIn("终端尺寸必须大于0", result.content)

        self.loop.run_until_complete(test())

    def test_send_keys_to_nonexistent_terminal(self):
        """测试发送按键到不存在的终端"""

        async def test():
            # 模拟远程调用返回错误
            self.mock_call_tool.return_value = ToolErrorMessage(
                "终端不存在: term_nonexistent"
            )

            result = await self.ssh_control.terminal_send_keys(
                terminal_id="term_nonexistent", keys=["enter", "a"]
            )
            self.assertIsInstance(result, ToolErrorMessage)
            self.assertIn("终端不存在", result.content)

        self.loop.run_until_complete(test())

    def test_send_string_to_nonexistent_terminal(self):
        """测试发送字符串到不存在的终端"""

        async def test():
            # 模拟远程调用返回错误
            self.mock_call_tool.return_value = ToolErrorMessage(
                "终端不存在: term_nonexistent"
            )

            result = await self.ssh_control.terminal_send_string(
                terminal_id="term_nonexistent", string="echo test", with_enter=True
            )
            self.assertIsInstance(result, ToolErrorMessage)
            self.assertIn("终端不存在", result.content)

        self.loop.run_until_complete(test())

    def test_read_nonexistent_terminal_screen(self):
        """测试读取不存在的终端屏幕"""

        async def test():
            # 模拟远程调用返回错误
            self.mock_call_tool.return_value = ToolErrorMessage(
                "终端不存在: term_nonexistent"
            )

            result = await self.ssh_control.terminal_read_screen(
                terminal_id="term_nonexistent"
            )
            self.assertIsInstance(result, ToolErrorMessage)
            self.assertIn("终端不存在", result.content)

        self.loop.run_until_complete(test())

    def test_close_nonexistent_terminal(self):
        """测试关闭不存在的终端"""

        async def test():
            # 模拟远程调用返回错误
            self.mock_call_tool.return_value = ToolErrorMessage(
                "终端不存在: term_nonexistent"
            )

            result = await self.ssh_control.terminal_close(
                terminal_id="term_nonexistent"
            )
            self.assertIsInstance(result, ToolErrorMessage)
            self.assertIn("终端不存在", result.content)

        self.loop.run_until_complete(test())

    def test_http_request_not_supported(self):
        """测试SSH机器不支持http_request工具"""

        async def test():
            result = await self.ssh_control.http_request(
                method="GET", url="http://example.com"
            )
            self.assertIsInstance(result, ToolErrorMessage)
            self.assertIn("SSH机器不支持", result.content)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
