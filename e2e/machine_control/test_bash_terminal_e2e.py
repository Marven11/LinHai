import asyncio
import shutil
import unittest

from linhai.machine_control.bash_host import BashHostControl
from linhai.machine_control.bash_host import terminal as _terminal
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.tool.base import SuccessfulToolResult
from tests.test_helpers import _AsyncioProcessAdapter


class TestBashTerminalE2E(unittest.IsolatedAsyncioTestCase):
    async def _create_bash_process(
        self,
    ) -> tuple[_AsyncioProcessAdapter, asyncio.subprocess.Process]:
        bash_path = shutil.which("bash") or shutil.which("sh")
        if bash_path is None:
            self.skipTest("bash/sh not found")
        process = await asyncio.create_subprocess_exec(
            bash_path,
            "-s",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        return _AsyncioProcessAdapter(process), process

    async def _create_control(
        self,
    ) -> tuple[BashHostControl, _AsyncioProcessAdapter, asyncio.subprocess.Process]:
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control = BashHostControl(registry)
        adapter, process = await self._create_bash_process()
        await control.connect(adapter)
        return control, adapter, process

    async def _cleanup(self, process: asyncio.subprocess.Process) -> None:
        _terminal._terminals.clear()
        if process.stdin and not process.stdin.is_closing():
            process.stdin.close()
        process.kill()
        await process.wait()

    async def test_terminal_create_and_send_string(self):
        if shutil.which("tmux") is None:
            self.skipTest("tmux not found")
        control, adapter, process = await self._create_control()
        try:
            result = await control.terminal_create(columns=80, lines=24)
            self.assertIsInstance(
                result, SuccessfulToolResult, f"terminal_create failed: {result}"
            )
            term_id = result.content

            send_result = await control.terminal_send_string(
                term_id, "echo hello_bash_terminal", with_enter=True, wait_seconds=1.0
            )
            self.assertIsInstance(
                send_result, SuccessfulToolResult, f"send_string failed: {send_result}"
            )

            screen = await control.terminal_read_screen(term_id)
            self.assertIsInstance(
                screen, SuccessfulToolResult, f"read_screen failed: {screen}"
            )
            self.assertIn("hello_bash_terminal", screen.content)

            await control.terminal_close(term_id)
        finally:
            await self._cleanup(process)

    async def test_terminal_send_keys(self):
        if shutil.which("tmux") is None:
            self.skipTest("tmux not found")
        control, adapter, process = await self._create_control()
        try:
            result = await control.terminal_create()
            self.assertIsInstance(result, SuccessfulToolResult)
            term_id = result.content

            send_result = await control.terminal_send_string(
                term_id, "echo key_test", with_enter=True, wait_seconds=1.0
            )
            self.assertIsInstance(send_result, SuccessfulToolResult)

            keys_result = await control.terminal_send_keys(term_id, ["up"])
            self.assertIsInstance(keys_result, SuccessfulToolResult)

            screen = await control.terminal_read_screen(term_id)
            self.assertIn("key_test", screen.content)

            await control.terminal_close(term_id)
        finally:
            await self._cleanup(process)

    async def test_terminal_get_terminals(self):
        if shutil.which("tmux") is None:
            self.skipTest("tmux not found")
        control, adapter, process = await self._create_control()
        try:
            empty = await control.get_terminals()
            self.assertIsInstance(empty, SuccessfulToolResult)
            self.assertIn("没有活动", empty.content)

            result = await control.terminal_create()
            self.assertIsInstance(result, SuccessfulToolResult)
            term_id = result.content

            terminals_result = await control.get_terminals()
            self.assertIsInstance(terminals_result, SuccessfulToolResult)
            self.assertIn(term_id, terminals_result.content)

            await control.terminal_close(term_id)
        finally:
            await self._cleanup(process)

    async def test_terminal_no_tmux(self):
        control, adapter, process = await self._create_control()
        try:
            rc, _, _ = await control.execute_raw("mv /usr/bin/tmux /usr/bin/tmux_bak")
            if rc != 0:
                self.skipTest("cannot hide tmux")
            try:
                result = await control.terminal_create()
                self.assertNotIsInstance(result, SuccessfulToolResult)
                self.assertIn("tmux", result.content)
            finally:
                await control.execute_raw("mv /usr/bin/tmux_bak /usr/bin/tmux")
        finally:
            await self._cleanup(process)


if __name__ == "__main__":
    unittest.main()
