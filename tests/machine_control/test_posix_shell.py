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
            registry=self.registry,
        )

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_connect_passes_process_to_transport(self):
        async def test():
            mock_process = AsyncMock()
            mock_process.pid = "1"

            mock_transport_instance = AsyncMock()
            mock_transport_instance.start_reading = Mock()

            with (
                patch(
                    "linhai.machine_control.posix_shell.posix_shell_control.setup_trojan_in_shell",
                    new_callable=AsyncMock,
                    return_value="/tmp/trojan.py",
                ) as mock_setup,
                patch(
                    "linhai.machine_control.posix_shell.posix_shell_control.TrojanTransport",
                    return_value=mock_transport_instance,
                ) as mock_transport_class,
            ):
                result = await self.control.connect(mock_process)
                self.assertTrue(result)
                mock_setup.assert_called_once_with(mock_process, self.registry)
                mock_transport_class.assert_called_once_with(
                    registry=self.registry, process=mock_process
                )
                self.assertEqual(self.control.transport, mock_transport_instance)

        self.loop.run_until_complete(test())

    def test_connect_propagates_exception(self):
        async def test():
            mock_process = AsyncMock()
            mock_process.pid = "1"

            with patch(
                "linhai.machine_control.posix_shell.posix_shell_control.setup_trojan_in_shell",
                new_callable=AsyncMock,
                side_effect=RuntimeError("connection failed"),
            ):
                with self.assertRaises(RuntimeError):
                    await self.control.connect(mock_process)

        self.loop.run_until_complete(test())

    def test_connect_returns_false_when_setup_fails(self):
        async def test():
            mock_process = AsyncMock()
            mock_process.pid = "1"

            with patch(
                "linhai.machine_control.posix_shell.posix_shell_control.setup_trojan_in_shell",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await self.control.connect(mock_process)
                self.assertFalse(result)
                self.assertIsNone(self.control.transport)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
