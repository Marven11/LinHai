import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from linhai.machine_control.trojan.ssh_transport import _AsyncioProcessAdapter
from linhai.machine_control.trojan.transport import TrojanTransport
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor


class TestTrojanTransportE2E(unittest.IsolatedAsyncioTestCase):
    async def test_ping_with_local_bash_process(self):
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

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
            tmp.write(trojan_source.read_bytes())
            trojan_path = tmp.name

        try:
            process = await asyncio.create_subprocess_exec(
                "python3",
                trojan_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

            adapter = _AsyncioProcessAdapter(process)
            transport = TrojanTransport(registry, process=adapter)
            transport.start_reading()

            await asyncio.sleep(0.5)

            result = await transport.send_request("ping", {})
            self.assertIn("result", result)
            self.assertEqual(result["result"]["message"], "pong")

            await transport.disconnect()
        finally:
            Path(trojan_path).unlink(missing_ok=True)

    async def test_process_create_with_local_bash_process(self):
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

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
            tmp.write(trojan_source.read_bytes())
            trojan_path = tmp.name

        try:
            process = await asyncio.create_subprocess_exec(
                "python3",
                trojan_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

            adapter = _AsyncioProcessAdapter(process)
            transport = TrojanTransport(registry, process=adapter)
            transport.start_reading()

            await asyncio.sleep(0.5)

            result = await transport.send_request(
                "process_create", {"argv": ["echo", "hello"]}
            )
            self.assertIn("result", result)
            message_data = result["result"]["message"]
            parsed = json.loads(message_data)
            self.assertIn("stdout", parsed)
            self.assertIn("hello", parsed["stdout"])

            await transport.disconnect()
        finally:
            Path(trojan_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
