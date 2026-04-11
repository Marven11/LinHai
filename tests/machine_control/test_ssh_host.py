import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from linhai.machine_control.ssh_host.ssh_host import SshMachineControl
from linhai.machine_control.process import (
    ProcessReadResult,
    ProcessWriteResult,
    ProcessKillResult,
)
from linhai.registry import Registry


class TestSshMachineControlConnect(unittest.TestCase):

    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.send_if_exists_mock = AsyncMock()
        self.registry.send_if_exists = self.send_if_exists_mock
        self.registry.has_member = Mock(return_value=False)

        self.control = SshMachineControl(
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
                    pid="1", success=True, stdout="CMD_RESULT_0:0\n", stderr=""
                )
            )
            mock_process.kill = AsyncMock(
                return_value=ProcessKillResult(pid="1", success=True, message="ok")
            )

            connect_result = True
            with patch.object(
                self.control.transport, "connect", return_value=connect_result
            ) as mock_connect:
                result = await self.control.connect(mock_process)
                self.assertTrue(result)
                mock_connect.assert_called_once_with(mock_process)

        self.loop.run_until_complete(test())

    def test_connect_propagates_exception(self):
        async def test():
            mock_process = AsyncMock()
            mock_process.pid = "1"

            with patch.object(
                self.control.transport,
                "connect",
                side_effect=RuntimeError("connection failed"),
            ):
                with self.assertRaises(RuntimeError):
                    await self.control.connect(mock_process)

        self.loop.run_until_complete(test())

    def test_connect_returns_false_when_transport_fails(self):
        async def test():
            mock_process = AsyncMock()
            mock_process.pid = "1"

            with patch.object(
                self.control.transport, "connect", return_value=False
            ) as mock_connect:
                result = await self.control.connect(mock_process)
                self.assertFalse(result)
                mock_connect.assert_called_once_with(mock_process)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
