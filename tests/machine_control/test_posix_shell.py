import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from linhai.machine_control.posix_shell.posix_shell_control import PosixShellControl
from linhai.machine_control.process import (
    ProcessReadResult,
    ProcessWriteResult,
    ProcessKillResult,
)
from linhai.registry import Registry


class TestPosixShellControlConnect(unittest.TestCase):

    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.send_if_exists_mock = AsyncMock()
        self.registry.send_if_exists = self.send_if_exists_mock
        self.registry.has_member = Mock(return_value=False)

        self.control = PosixShellControl(
            host="test-host", registry=self.registry, port=22, username="testuser"
        )

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_connect_passes_process_to_transport(self):
        async def test():
            mock_process = AsyncMock()
            mock_process.pid = "1"
            mock_process.stdio_write = AsyncMock(
                return_value=ProcessWriteResult(pid="1", success=True, message="ok")
            )
            mock_process.stdio_read = AsyncMock(
                return_value=ProcessReadResult(
                    pid="1", success=True, stdout=b"CMD_RESULT_0:0\n", stderr=b""
                )
            )
            mock_process.kill = AsyncMock(
                return_value=ProcessKillResult(pid="1", success=True, message="ok")
            )

            mock_transport_instance = AsyncMock()
            mock_transport_instance.connect = AsyncMock(return_value=True)
            mock_transport_instance.disconnect = AsyncMock()

            with patch(
                "linhai.machine_control.posix_shell.posix_shell_control.ShellTrojanTransport",
                return_value=mock_transport_instance,
            ) as mock_transport_class:
                result = await self.control.connect(mock_process)
                self.assertTrue(result)
                mock_transport_class.assert_called_once_with(
                    registry=self.registry, process=mock_process
                )
                mock_transport_instance.connect.assert_called_once_with()
                self.assertEqual(self.control.transport, mock_transport_instance)

        self.loop.run_until_complete(test())

    def test_connect_propagates_exception(self):
        async def test():
            mock_process = AsyncMock()
            mock_process.pid = "1"

            mock_transport_instance = AsyncMock()
            mock_transport_instance.connect = AsyncMock(
                side_effect=RuntimeError("connection failed")
            )
            mock_transport_instance.disconnect = AsyncMock()

            with patch(
                "linhai.machine_control.posix_shell.posix_shell_control.ShellTrojanTransport",
                return_value=mock_transport_instance,
            ):
                with self.assertRaises(RuntimeError):
                    await self.control.connect(mock_process)

        self.loop.run_until_complete(test())

    def test_connect_returns_false_when_transport_fails(self):
        async def test():
            mock_process = AsyncMock()
            mock_process.pid = "1"

            mock_transport_instance = AsyncMock()
            mock_transport_instance.connect = AsyncMock(return_value=False)
            mock_transport_instance.disconnect = AsyncMock()

            with patch(
                "linhai.machine_control.posix_shell.posix_shell_control.ShellTrojanTransport",
                return_value=mock_transport_instance,
            ) as mock_transport_class:
                result = await self.control.connect(mock_process)
                self.assertFalse(result)
                mock_transport_class.assert_called_once_with(
                    registry=self.registry, process=mock_process
                )
                mock_transport_instance.connect.assert_called_once_with()
                self.assertEqual(self.control.transport, mock_transport_instance)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
