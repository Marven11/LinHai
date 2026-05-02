import asyncio
import json
import unittest

from linhai.machine_control.trojan.trojan import Trojan


class TestTrojanFinishedProcesses(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.trojan = Trojan(b"<test_marker>")

    async def test_process_wait_stores_finished_process(self):
        result = await self.trojan.process_create(["echo", "hello"], wait_second=2.0)
        data = json.loads(result["message"])
        pid = data["pid"]
        self.assertEqual(data["returncode"], 0)
        self.assertIn(pid, self.trojan._finished_processes)
        self.assertEqual(self.trojan._finished_processes[pid]["returncode"], 0)

    async def test_process_wait_returns_cached_result(self):
        result = await self.trojan.process_create(["echo", "hello"], wait_second=2.0)
        data = json.loads(result["message"])
        pid = data["pid"]

        result2 = await self.trojan.process_wait(pid, timeout=1.0)
        data2 = json.loads(result2["message"])
        self.assertEqual(data2["returncode"], 0)
        self.assertEqual(data2["pid"], pid)

    async def test_process_wait_idempotent(self):
        result = await self.trojan.process_create(["echo", "hello"], wait_second=2.0)
        data = json.loads(result["message"])
        pid = data["pid"]

        for _ in range(5):
            r = await self.trojan.process_wait(pid, timeout=1.0)
            d = json.loads(r["message"])
            self.assertEqual(d["returncode"], 0)

    async def test_process_create_fast_exit_stores_finished(self):
        result = await self.trojan.process_create(["echo", "fast"], wait_second=2.0)
        data = json.loads(result["message"])
        pid = data["pid"]

        self.assertIn(pid, self.trojan._finished_processes)
        self.assertNotIn(pid, self.trojan._processes)

        r = await self.trojan.process_wait(pid, timeout=1.0)
        d = json.loads(r["message"])
        self.assertEqual(d["returncode"], 0)

    async def test_process_kill_stores_finished(self):
        result = await self.trojan.process_create(["sleep", "60"], wait_second=1.0)
        data = json.loads(result["message"])
        pid = data["pid"]

        self.assertNotIn("returncode", data)

        kill_result = await self.trojan.process_kill(pid)
        self.assertIn("message", kill_result)

        self.assertIn(pid, self.trojan._finished_processes)
        self.assertNotIn(pid, self.trojan._processes)

        r = await self.trojan.process_wait(pid, timeout=1.0)
        d = json.loads(r["message"])
        self.assertIsNotNone(d["returncode"])

    async def test_stdio_write_finished_process_returns_error(self):
        result = await self.trojan.process_create(["echo", "done"], wait_second=2.0)
        data = json.loads(result["message"])
        pid = data["pid"]

        write_result = await self.trojan.process_stdio_write(pid, "test")
        self.assertIn("error", write_result)
        self.assertIn("已退出", write_result["error"])

    async def test_stdio_read_finished_process_returns_error(self):
        result = await self.trojan.process_create(["echo", "done"], wait_second=2.0)
        data = json.loads(result["message"])
        pid = data["pid"]

        read_result = await self.trojan.process_stdio_read(pid)
        self.assertIn("error", read_result)
        self.assertIn("已退出", read_result["error"])

    async def test_process_wait_running_then_finished(self):
        result = await self.trojan.process_create(["sleep", "0.5"], wait_second=0.3)
        data = json.loads(result["message"])
        pid = data["pid"]

        r1 = await self.trojan.process_wait(pid, timeout=0.01)
        d1 = json.loads(r1["message"])
        self.assertTrue(d1.get("timeout"))

        await asyncio.sleep(1.0)

        r2 = await self.trojan.process_wait(pid, timeout=5.0)
        d2 = json.loads(r2["message"])
        self.assertEqual(d2["returncode"], 0)

        r3 = await self.trojan.process_wait(pid, timeout=1.0)
        d3 = json.loads(r3["message"])
        self.assertEqual(d3["returncode"], 0)

    async def test_nonexistent_process_raises(self):
        with self.assertRaises(AssertionError):
            await self.trojan.process_wait("999999", timeout=1.0)


if __name__ == "__main__":
    unittest.main()
