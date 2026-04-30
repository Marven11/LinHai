from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from linhai.machine_control.bash_host.bash_host import BashHostControl
from linhai.machine_control.bash_host import terminal as _terminal
from linhai.tool.base import SuccessfulToolResult, FailedToolResult


class TestBashTerminal(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.host = Mock(spec=BashHostControl)
        self.host.execute_raw = AsyncMock()
        _terminal._terminals.clear()

    def tearDown(self):
        _terminal._terminals.clear()
        self.loop.close()

    def test_terminal_create_no_tmux(self):
        async def test():
            self.host.execute_raw = AsyncMock(return_value=(1, "", "not found"))
            result = await _terminal.terminal_create(self.host)
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("tmux", result.content)

        self.loop.run_until_complete(test())

    def test_terminal_create_success(self):
        async def test():
            self.host.execute_raw = AsyncMock(
                side_effect=[
                    (0, "/usr/bin/tmux", ""),
                    (0, "", ""),
                ]
            )
            result = await _terminal.terminal_create(self.host, columns=80, lines=24)
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertTrue(len(result.content) > 0)
            self.assertIn(result.content, _terminal._terminals)

        self.loop.run_until_complete(test())

    def test_terminal_create_failure(self):
        async def test():
            self.host.execute_raw = AsyncMock(
                side_effect=[
                    (0, "/usr/bin/tmux", ""),
                    (1, "", "session exists"),
                ]
            )
            result = await _terminal.terminal_create(self.host)
            self.assertIsInstance(result, FailedToolResult)

        self.loop.run_until_complete(test())

    def test_terminal_send_keys_not_found(self):
        async def test():
            result = await _terminal.terminal_send_keys(self.host, "fake_id", ["enter"])
            self.assertIsInstance(result, FailedToolResult)

        self.loop.run_until_complete(test())

    def test_terminal_send_keys_special(self):
        async def test():
            _terminal._terminals["t1"] = {
                "session_name": "linhai_test",
                "columns": "80",
                "lines": "24",
            }
            self.host.execute_raw = AsyncMock(return_value=(0, "", ""))
            result = await _terminal.terminal_send_keys(
                self.host, "t1", ["enter", "ctrl+c"]
            )
            self.assertIsInstance(result, SuccessfulToolResult)

        self.loop.run_until_complete(test())

    def test_terminal_send_keys_single_char(self):
        async def test():
            _terminal._terminals["t1"] = {
                "session_name": "linhai_test",
                "columns": "80",
                "lines": "24",
            }
            self.host.execute_raw = AsyncMock(return_value=(0, "", ""))
            result = await _terminal.terminal_send_keys(self.host, "t1", ["a"])
            self.assertIsInstance(result, SuccessfulToolResult)

        self.loop.run_until_complete(test())

    def test_terminal_send_keys_unknown(self):
        async def test():
            _terminal._terminals["t1"] = {
                "session_name": "linhai_test",
                "columns": "80",
                "lines": "24",
            }
            result = await _terminal.terminal_send_keys(
                self.host, "t1", ["unknown_key"]
            )
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("未知按键", result.content)

        self.loop.run_until_complete(test())

    def test_terminal_send_string_not_found(self):
        async def test():
            result = await _terminal.terminal_send_string(
                self.host, "fake_id", "ls", True
            )
            self.assertIsInstance(result, FailedToolResult)

        self.loop.run_until_complete(test())

    def test_terminal_send_string_with_enter(self):
        async def test():
            _terminal._terminals["t1"] = {
                "session_name": "linhai_test",
                "columns": "80",
                "lines": "24",
            }
            self.host.execute_raw = AsyncMock(return_value=(0, "$ ", ""))
            result = await _terminal.terminal_send_string(
                self.host, "t1", "ls", with_enter=True, wait_seconds=0.0
            )
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("ls", result.content)

        self.loop.run_until_complete(test())

    def test_terminal_send_string_failure(self):
        async def test():
            _terminal._terminals["t1"] = {
                "session_name": "linhai_test",
                "columns": "80",
                "lines": "24",
            }
            self.host.execute_raw = AsyncMock(return_value=(1, "", "error"))
            result = await _terminal.terminal_send_string(
                self.host, "t1", "ls", with_enter=False, wait_seconds=0.0
            )
            self.assertIsInstance(result, FailedToolResult)

        self.loop.run_until_complete(test())

    def test_terminal_read_screen_not_found(self):
        async def test():
            result = await _terminal.terminal_read_screen(self.host, "fake_id")
            self.assertIsInstance(result, FailedToolResult)

        self.loop.run_until_complete(test())

    def test_terminal_read_screen_success(self):
        async def test():
            _terminal._terminals["t1"] = {
                "session_name": "linhai_test",
                "columns": "80",
                "lines": "24",
            }
            self.host.execute_raw = AsyncMock(return_value=(0, "$ ls\nfile.txt", ""))
            result = await _terminal.terminal_read_screen(self.host, "t1")
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("ls", result.content)

        self.loop.run_until_complete(test())

    def test_terminal_close_not_found(self):
        async def test():
            result = await _terminal.terminal_close(self.host, "fake_id")
            self.assertIsInstance(result, FailedToolResult)

        self.loop.run_until_complete(test())

    def test_terminal_close_success(self):
        async def test():
            _terminal._terminals["t1"] = {
                "session_name": "linhai_test",
                "columns": "80",
                "lines": "24",
            }
            self.host.execute_raw = AsyncMock(return_value=(0, "", ""))
            result = await _terminal.terminal_close(self.host, "t1")
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertNotIn("t1", _terminal._terminals)

        self.loop.run_until_complete(test())

    def test_get_terminals_empty(self):
        async def test():
            result = await _terminal.get_terminals(self.host, "test_machine")
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("没有活动", result.content)

        self.loop.run_until_complete(test())

    def test_get_terminals_with_active(self):
        async def test():
            _terminal._terminals["t1"] = {
                "session_name": "linhai_test",
                "columns": "80",
                "lines": "24",
            }
            self.host.execute_raw = AsyncMock(return_value=(0, "$ prompt", ""))
            result = await _terminal.get_terminals(self.host, "test_machine")
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("t1", result.content)
            self.assertIn("test_machine", result.content)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
