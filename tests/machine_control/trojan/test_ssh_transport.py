"""SSH Trojan Transport测试模块，测试基于单bash shell的SSH连接功能"""

import unittest
import asyncio
import sys
import os
import shutil
import subprocess
import tempfile
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from io import StringIO

from linhai.machine_control.trojan.ssh_transport import SshTrojanTransport
from linhai.registry import Registry


class TestSshTrojanTransport(unittest.TestCase):
    """SSH Trojan Transport测试类"""

    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.send_if_exists_mock = AsyncMock()
        self.registry.send_if_exists = self.send_if_exists_mock

        self.mock_task_supervisor = AsyncMock()
        self.mock_process = AsyncMock()
        self.mock_process.stdin = AsyncMock()
        self.mock_process.stdin.write = Mock()
        self.mock_process.stdin.drain = AsyncMock()
        self.mock_process.stdout = AsyncMock()
        self.mock_process.stderr = AsyncMock()
        self.mock_process.returncode = None

        self.run_with_timeout_responses = []
        self.run_with_timeout_index = 0

        async def run_with_timeout_side_effect(coro, timeout):
            if self.run_with_timeout_index < len(self.run_with_timeout_responses):
                response = self.run_with_timeout_responses[self.run_with_timeout_index]
                self.run_with_timeout_index += 1
                return (True, response)
            return (True, b"")

        self.mock_task_supervisor.run_with_timeout = AsyncMock(
            side_effect=run_with_timeout_side_effect
        )
        self.registry.has_member = Mock(return_value=True)
        self.registry.get_member_typechecked = Mock(
            return_value=self.mock_task_supervisor
        )

        self.transport = SshTrojanTransport(
            host="test-host",
            registry=self.registry,
            port=22,
            username="testuser",
        )

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @unittest.skipIf(shutil.which("bash") is None, "系统没有bash，跳过测试")
    def test_connect_success_with_real_bash(self):
        async def test():
            mock_process = AsyncMock()
            mock_process.stdin = AsyncMock()
            mock_process.stdin.write = Mock()
            mock_process.stdin.drain = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.readline = AsyncMock()
            mock_process.stderr = AsyncMock()
            mock_process.returncode = None
            mock_process.terminate = Mock()

            self.run_with_timeout_responses = [
                mock_process,
                b"Python 3.14.2\n",
                b"CMD_RESULT_0:0\n",
                b"/tmp/trojan.py\n",
                b"CMD_RESULT_0:0\n",
                b"CMD_RESULT_0:0\n",
            ]
            self.run_with_timeout_index = 0

            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("tempfile.mktemp", return_value="/tmp/trojan_local.py"):
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch(
                            "pathlib.Path.read_text", return_value="# trojan content"
                        ):
                            with patch("pathlib.Path.write_text"):
                                with patch("pathlib.Path.unlink"):
                                    with patch("asyncio.get_event_loop") as mock_loop:
                                        mock_loop_instance = Mock()
                                        mock_loop_instance.time = Mock(return_value=0)
                                        mock_loop.return_value = mock_loop_instance
                                        result = await self.transport.connect()
                                        self.assertTrue(result)
                                        self.assertTrue(self.transport.is_connected())
                                        self.assertTrue(self.send_if_exists_mock.called)
                                        await self.transport.disconnect()

        self.loop.run_until_complete(test())

    @unittest.skipIf(shutil.which("bash") is None, "系统没有bash，跳过测试")
    def test_python_version_check_failure_with_real_bash(self):
        async def test():
            mock_process = AsyncMock()
            mock_process.stdin = AsyncMock()
            mock_process.stdin.write = Mock()
            mock_process.stdin.drain = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.readline = AsyncMock()
            mock_process.stderr = AsyncMock()
            mock_process.returncode = 0
            mock_process.terminate = Mock()

            self.run_with_timeout_responses = [
                mock_process,
                b"Python 2.7.18\n",
                b"CMD_RESULT_0:0\n",
            ]
            self.run_with_timeout_index = 0

            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("tempfile.mktemp", return_value="/tmp/trojan_local.py"):
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch(
                            "pathlib.Path.read_text", return_value="# trojan content"
                        ):
                            with patch("pathlib.Path.write_text"):
                                with patch("pathlib.Path.unlink"):
                                    with patch("asyncio.get_event_loop") as mock_loop:
                                        mock_loop_instance = Mock()
                                        mock_loop_instance.time = Mock(return_value=0)
                                        mock_loop.return_value = mock_loop_instance
                                        result = await self.transport.connect()
                                        self.assertFalse(result)
                                        self.assertFalse(self.transport.is_connected())

        self.loop.run_until_complete(test())

    @unittest.skipIf(shutil.which("bash") is None, "系统没有bash，跳过测试")
    def test_command_timeout_with_real_bash(self):

        async def test():
            mock_process = AsyncMock()
            mock_process.stdin = AsyncMock()
            mock_process.stdin.write = Mock()
            mock_process.stdin.drain = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.readline = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.returncode = None

            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("tempfile.mktemp", return_value="/tmp/trojan_local.py"):
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch(
                            "pathlib.Path.read_text",
                            return_value="# trojan content",
                        ):
                            with patch("pathlib.Path.write_text"):
                                with patch("pathlib.Path.unlink"):
                                    self.transport._bash_process = mock_process

                                    exit_code, output, error = (
                                        await self.transport._execute_in_bash(
                                            "test command", timeout=0.5
                                        )
                                    )

                                    self.assertEqual(exit_code, 1)
                                    self.assertEqual(error, "命令执行超时")

        self.loop.run_until_complete(test())

    def test_disconnect(self):
        async def test():
            # 设置一个模拟的trojan_transport
            mock_trojan_transport = AsyncMock()
            mock_trojan_transport.disconnect = AsyncMock()
            mock_trojan_transport.is_connected = Mock(return_value=True)

            # 创建一个模拟的bash进程，确保wait()返回一个可await的值
            mock_bash_process = AsyncMock()
            mock_bash_process.terminate = Mock()
            # 创建一个future，使wait()可await且返回returncode
            future = asyncio.Future()
            future.set_result(0)  # 模拟进程退出码为0
            mock_bash_process.wait = Mock(return_value=future)
            mock_bash_process.returncode = 0

            self.transport._trojan_transport = mock_trojan_transport
            self.transport._bash_process = mock_bash_process

            # 执行断开连接
            await self.transport.disconnect()

            # 验证trojan_transport.disconnect被调用
            mock_trojan_transport.disconnect.assert_called_once()

            # 验证清理操作
            self.assertIsNone(self.transport._trojan_transport)
            self.assertIsNone(self.transport._bash_process)

        self.loop.run_until_complete(test())

    def test_send_request_not_connected(self):
        async def test():
            self.transport._trojan_transport = None

            with self.assertRaises(ConnectionError) as context:
                await self.transport.send_request("test_method", {"param": "value"})

            self.assertIn("未建立连接", str(context.exception))

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
