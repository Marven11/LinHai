import asyncio
import json
import unittest
from pathlib import Path

from linhai.machine_control.trojan.ssh_transport import SshTrojanTransport
from tests.test_helpers import _AsyncioProcessAdapter
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor


class TestSshTrojanTransportE2E(unittest.IsolatedAsyncioTestCase):
    async def _create_transport_with_bash(self):
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())

        transport = SshTrojanTransport(
            registry=registry,
        )

        trojan_source = (
            Path(__file__).parent.parent.parent.parent
            / "linhai"
            / "machine_control"
            / "trojan"
            / "trojan.py"
        )
        if not trojan_source.exists():
            self.skipTest(f"trojan.py不存在: {trojan_source}")

        process = await asyncio.create_subprocess_exec(
            "bash",
            "-s",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )

        adapter = _AsyncioProcessAdapter(process)
        return transport, adapter

    async def test_connect_with_local_bash(self):
        transport, adapter = await self._create_transport_with_bash()
        result = await transport.connect(adapter)
        self.assertTrue(result)
        self.assertTrue(transport.is_connected())

        try:
            ping_result = await transport.send_request("ping", {})
            self.assertIn("result", ping_result)
            self.assertEqual(ping_result["result"]["message"], "pong")
        finally:
            await transport.disconnect()

    async def test_process_create_with_local_bash(self):
        transport, adapter = await self._create_transport_with_bash()
        result = await transport.connect(adapter)
        self.assertTrue(result)

        try:
            create_result = await transport.send_request(
                "process_create", {"argv": ["echo", "hello"]}
            )
            self.assertIn("result", create_result)
            message_data = create_result["result"]["message"]
            parsed = json.loads(message_data)
            self.assertIn("stdout", parsed)
            self.assertIn("hello", parsed["stdout"])
        finally:
            await transport.disconnect()


if __name__ == "__main__":
    unittest.main()
