import asyncio
import json
import unittest
from pathlib import Path

from linhai.machine_control.trojan.transport import TrojanTransport
from linhai.machine_control.trojan.shell_transport import setup_trojan_in_shell
from tests.test_helpers import _AsyncioProcessAdapter
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor


class TestSetupTrojanInShellE2E(unittest.IsolatedAsyncioTestCase):
    async def _create_connected_transport(self):
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())

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
        remote_path = await setup_trojan_in_shell(adapter, registry)
        if remote_path is None:
            raise RuntimeError("setup_trojan_in_shell failed")

        transport = TrojanTransport(registry=registry, process=adapter)
        transport.start_reading()
        return transport

    async def test_connect_with_local_bash(self):
        transport = await self._create_connected_transport()

        try:
            ping_result = await transport.send_request("ping", {})
            self.assertIn("result", ping_result)
            self.assertEqual(ping_result["result"]["message"], "pong")
        finally:
            await transport.disconnect()

    async def test_process_create_with_local_bash(self):
        transport = await self._create_connected_transport()

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
