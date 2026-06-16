import asyncio
import unittest
from unittest.mock import MagicMock, patch

from linhai.machine_control.master_host.tmux_terminal import (
    TmuxTerminal,
    is_tmux_available,
    _SESSION_PREFIX,
    _session_exists,
    _MAX_NAME_RETRIES,
)


class TestIsTmuxAvailable(unittest.TestCase):
    @patch("linhai.machine_control.master_host.tmux_terminal.shutil.which")
    def test_available(self, mock_which):
        mock_which.return_value = "/usr/bin/tmux"
        self.assertTrue(is_tmux_available())

    @patch("linhai.machine_control.master_host.tmux_terminal.shutil.which")
    def test_not_available(self, mock_which):
        mock_which.return_value = None
        self.assertFalse(is_tmux_available())


class TestTmuxTerminal(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.terminals_to_cleanup = []
        self.mock_run = patch(
            "linhai.machine_control.master_host.tmux_terminal.subprocess.run"
        ).start()
        self.mock_run.side_effect = lambda *a, **k: MagicMock(
            returncode=1 if isinstance(a[0], list) and "has-session" in a[0] else 0,
            stdout="",
        )

    def tearDown(self):
        for t in self.terminals_to_cleanup:
            t.close()
        patch.stopall()
        self.loop.close()

    def _create_terminal(self, **kwargs):
        t = TmuxTerminal(**kwargs)
        self.terminals_to_cleanup.append(t)
        return t

    def test_session_name_prefix(self):
        t = self._create_terminal()
        self.assertTrue(t.session_name.startswith(_SESSION_PREFIX))

    def test_send_and_read(self):
        t = self._create_terminal()
        t.send("echo hello_tmux_test")
        t.send_key("enter")
        send_calls = [
            c for c in self.mock_run.call_args_list if "send-keys" in str(c.args)
        ]
        self.assertTrue(len(send_calls) >= 2)
        self.assertIn("echo hello_tmux_test", str(send_calls[0].args))

    def test_send_key_enter(self):
        t = self._create_terminal()
        t.send("echo key_test")
        t.send_key("enter")
        send_calls = [
            c for c in self.mock_run.call_args_list if "send-keys" in str(c.args)
        ]
        self.assertTrue(any("Enter" in str(c.args) for c in send_calls))

    def test_send_key_unknown_raises(self):
        t = self._create_terminal()
        with self.assertRaises(ValueError):
            t.send_key("unknown_key")

    def test_close_and_verify(self):
        t = self._create_terminal()
        t.send("echo before_close")
        t.send_key("enter")
        t.close()
        self.terminals_to_cleanup.remove(t)
        kill_calls = [
            c for c in self.mock_run.call_args_list if "kill-session" in str(c.args)
        ]
        self.assertEqual(len(kill_calls), 1)

    def test_session_exists_true(self):
        self.mock_run.side_effect = lambda *a, **k: MagicMock(returncode=0, stdout="")
        self.assertTrue(_session_exists("linhai_test_session"))

    def test_session_exists_false(self):
        self.mock_run.side_effect = lambda *a, **k: MagicMock(returncode=1, stdout="")
        self.assertFalse(_session_exists("linhai_nonexistent_session_xyz"))

    @patch("linhai.machine_control.master_host.tmux_terminal._session_exists")
    def test_name_conflict_retries(self, mock_exists):
        mock_exists.return_value = True
        with self.assertRaises(ValueError) as ctx:
            TmuxTerminal()
        self.assertIn("conflict", str(ctx.exception))
        self.assertEqual(mock_exists.call_count, _MAX_NAME_RETRIES)

    @patch("linhai.machine_control.master_host.tmux_terminal._session_exists")
    def test_name_conflict_resolves_on_second_try(self, mock_exists):
        mock_exists.side_effect = [True, False]
        t = TmuxTerminal()
        self.terminals_to_cleanup.append(t)
        self.assertTrue(t.session_name.startswith(_SESSION_PREFIX))

    def test_start_reading_is_noop(self):
        t = self._create_terminal()
        self.loop.run_until_complete(t.start_reading())


if __name__ == "__main__":
    unittest.main()
