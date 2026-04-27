import asyncio
import unittest

from linhai.machine_control.master_host.process import LocalPtyProcess
from linhai.machine_control.trojan.shell_transport import setup_trojan_in_shell
from linhai.machine_control.trojan.transport import TrojanTransport
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor


def _make_registry() -> Registry:
    registry = Registry()
    ts = PlainTaskSupervisor()
    registry.register_member("task_supervisor", ts)
    return registry


class TestTrojanPtyE2e(unittest.IsolatedAsyncioTestCase):
    async def test_pty_bash_machine_ping_after_wait(self) -> None:
        registry = _make_registry()
        pty_proc = await self._create_pty_bash()
        if pty_proc is None:
            self.skipTest("Failed to create PTY bash process")

        try:
            result = await setup_trojan_in_shell(pty_proc, registry)
            if result is None:
                self.skipTest("Trojan injection failed (CI environment)")
            _, marker_hex = result

            transport = TrojanTransport(
                registry=registry, process=pty_proc, marker_hex=marker_hex
            )
            transport.start_reading()
            await asyncio.sleep(0.5)

            response = await asyncio.wait_for(
                transport.send_request("ping", {}), timeout=10.0
            )
            self.assertIn("result", response)

            await asyncio.sleep(90)

            response_after_wait = await asyncio.wait_for(
                transport.send_request("ping", {}), timeout=10.0
            )
            self.assertIn("result", response_after_wait)

            await transport.disconnect()
        finally:
            if pty_proc.returncode is None:
                await pty_proc.kill()

    async def test_pty_bash_immediate_ping(self) -> None:
        registry = _make_registry()
        pty_proc = await self._create_pty_bash()
        if pty_proc is None:
            self.skipTest("Failed to create PTY bash process")

        try:
            result = await setup_trojan_in_shell(pty_proc, registry)
            if result is None:
                self.skipTest("Trojan injection failed (CI environment)")
            _, marker_hex = result

            transport = TrojanTransport(
                registry=registry, process=pty_proc, marker_hex=marker_hex
            )
            transport.start_reading()
            await asyncio.sleep(0.5)

            response = await asyncio.wait_for(
                transport.send_request("ping", {}), timeout=10.0
            )
            self.assertIn("result", response)

            await transport.disconnect()
        finally:
            if pty_proc.returncode is None:
                await pty_proc.kill()

    async def _create_pty_bash(self) -> LocalPtyProcess | None:
        import fcntl
        import os
        import pty as pty_module

        master_fd, slave_fd = pty_module.openpty()
        fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NONBLOCK)
        try:
            process = await asyncio.create_subprocess_exec(
                "/usr/bin/env",
                "bash",
                "-i",
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
            )
            await asyncio.sleep(0.5)
            if process.returncode is not None:
                return None
            return LocalPtyProcess(
                process,
                master_fd,
                slave_fd,
                on_exit=self._noop_on_exit,
            )
        except OSError:
            os.close(master_fd)
            os.close(slave_fd)
            return None

    @staticmethod
    async def _noop_on_exit(pid: str) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
