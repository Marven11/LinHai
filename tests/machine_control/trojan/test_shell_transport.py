"""SSH Trojan Transport测试模块，测试基于单bash shell的SSH连接功能"""

import unittest
import asyncio
import shutil
from unittest.mock import AsyncMock, Mock, patch

from linhai.machine_control.trojan.shell_transport import ShellTrojanTransport
from linhai.machine_control.process import (
    ProcessKillResult,
    ProcessReadResult,
    ProcessWriteResult,
)
from linhai.registry import Registry


class TestShellTrojanTransport(unittest.TestCase):
    """SSH Trojan Transport测试类"""

    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.send_if_exists_mock = AsyncMock()
        self.registry.send_if_exists = self.send_if_exists_mock

        self.mock_task_supervisor = AsyncMock()
        self.mock_task_supervisor.create_supervised_task = Mock()
        self.mock_task_supervisor.cancel = Mock()
        self.mock_task_supervisor.wait = AsyncMock(return_value=None)
        self.registry.has_member = Mock(return_value=True)
        self.registry.get_member_typechecked = Mock(
            return_value=self.mock_task_supervisor
        )

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def _make_mock_process(self, read_responses):
        mock_process = AsyncMock()
        mock_process.pid = "1"
        mock_process.stdio_write = AsyncMock(
            return_value=ProcessWriteResult(pid="1", success=True, message="写入成功")
        )
        responses = iter(read_responses)
        default = ProcessReadResult(pid="1", success=True, stdout=b"", stderr=b"")

        async def read_side_effect(wait_seconds):
            return next(responses, default)

        mock_process.stdio_read = AsyncMock(side_effect=read_side_effect)
        mock_process.kill = AsyncMock(
            return_value=ProcessKillResult(pid="1", success=True, message="进程已终止")
        )
        return mock_process

    @unittest.skipIf(shutil.which("bash") is None, "系统没有bash，跳过测试")
    def test_connect_success_with_real_bash(self):
        async def test():
            read_responses = [
                ProcessReadResult(
                    pid="1",
                    success=True,
                    stdout=b"Python 3.14.2\nCMD_RESULT_0:0\n",
                    stderr=b"",
                ),
                ProcessReadResult(
                    pid="1",
                    success=True,
                    stdout=b"/tmp/trojan.py\nCMD_RESULT_0:0\n",
                    stderr=b"",
                ),
                ProcessReadResult(
                    pid="1",
                    success=True,
                    stdout=b"CMD_RESULT_0:0\n",
                    stderr=b"",
                ),
            ]
            mock_process = self._make_mock_process(read_responses)
            transport = ShellTrojanTransport(
                registry=self.registry,
                process=mock_process,
            )

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
                                    result = await transport.connect()
                                    self.assertTrue(result)
                                    self.assertTrue(transport.is_connected())
                                    self.assertTrue(self.send_if_exists_mock.called)
                                    await transport.disconnect()

        self.loop.run_until_complete(test())

    @unittest.skipIf(shutil.which("bash") is None, "系统没有bash，跳过测试")
    def test_python_version_check_failure_with_real_bash(self):
        async def test():
            read_responses = [
                ProcessReadResult(
                    pid="1",
                    success=True,
                    stdout=b"Python 2.7.18\nCMD_RESULT_0:0\n",
                    stderr=b"",
                ),
            ]
            mock_process = self._make_mock_process(read_responses)
            transport = ShellTrojanTransport(
                registry=self.registry,
                process=mock_process,
            )

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
                                    result = await transport.connect()
                                    self.assertFalse(result)
                                    self.assertFalse(transport.is_connected())

        self.loop.run_until_complete(test())

    @unittest.skipIf(shutil.which("bash") is None, "系统没有bash，跳过测试")
    def test_command_timeout_with_real_bash(self):
        async def test():
            empty_read = ProcessReadResult(
                pid="1", success=True, stdout=b"", stderr=b""
            )
            mock_process = self._make_mock_process([empty_read, empty_read])
            transport = ShellTrojanTransport(
                registry=self.registry,
                process=mock_process,
            )

            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop_instance = Mock()
                time_values = iter([0, 0, 0.3, 0.6])
                mock_loop_instance.time = Mock(side_effect=lambda: next(time_values))
                mock_loop.return_value = mock_loop_instance

                exit_code, output, error = await transport._execute_in_shell(
                    "test command", timeout=0.5
                )

                self.assertEqual(exit_code, 1)
                self.assertEqual(error, "命令执行超时")

        self.loop.run_until_complete(test())

    def test_disconnect(self):
        async def test():
            mock_trojan_transport = AsyncMock()
            mock_trojan_transport.disconnect = AsyncMock()
            mock_trojan_transport.is_connected = Mock(return_value=True)

            mock_bash_process = AsyncMock()
            transport = ShellTrojanTransport(
                registry=self.registry,
                process=mock_bash_process,
            )

            transport._trojan_transport = mock_trojan_transport

            await transport.disconnect()

            mock_trojan_transport.disconnect.assert_called_once()
            self.assertIsNone(transport._trojan_transport)

        self.loop.run_until_complete(test())

    def test_send_request_not_connected(self):
        async def test():
            mock_process = self._make_mock_process([])
            transport = ShellTrojanTransport(
                registry=self.registry,
                process=mock_process,
            )
            transport._trojan_transport = None

            with self.assertRaises(ConnectionError) as context:
                await transport.send_request("test_method", {"param": "value"})

            self.assertIn("未建立连接", str(context.exception))

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
