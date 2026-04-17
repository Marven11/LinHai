import asyncio
import unittest
from unittest.mock import patch

from linhai.machine_control.master_host.tmux_terminal import (
    TmuxTerminal,
    KEY_TO_TMUX,
    is_tmux_available,
    _SESSION_PREFIX,
    _session_exists,
    _MAX_NAME_RETRIES,
)


class TestKeyConversion(unittest.TestCase):
    def test_enter_key(self):
        self.assertEqual(KEY_TO_TMUX["enter"], "Enter")

    def test_escape_key(self):
        self.assertEqual(KEY_TO_TMUX["esc"], "Escape")

    def test_ctrl_c(self):
        self.assertEqual(KEY_TO_TMUX["ctrl+c"], "C-c")

    def test_ctrl_d(self):
        self.assertEqual(KEY_TO_TMUX["ctrl+d"], "C-d")

    def test_function_keys(self):
        for i in range(1, 13):
            self.assertEqual(KEY_TO_TMUX[f"f{i}"], f"F{i}")

    def test_arrow_keys(self):
        self.assertEqual(KEY_TO_TMUX["up"], "Up")
        self.assertEqual(KEY_TO_TMUX["down"], "Down")
        self.assertEqual(KEY_TO_TMUX["left"], "Left")
        self.assertEqual(KEY_TO_TMUX["right"], "Right")


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

    def tearDown(self):
        for t in self.terminals_to_cleanup:
            t.close()
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
        self.loop.run_until_complete(asyncio.sleep(0.5))
        screen = t.get_screen()
        self.assertIn("hello_tmux_test", screen)

    def test_send_key_enter(self):
        t = self._create_terminal()
        t.send("echo key_test")
        t.send_key("enter")
        self.loop.run_until_complete(asyncio.sleep(0.5))
        screen = t.get_screen()
        self.assertIn("key_test", screen)

    def test_send_key_unknown_raises(self):
        t = self._create_terminal()
        with self.assertRaises(ValueError):
            t.send_key("unknown_key")

    def test_close_and_verify(self):
        t = self._create_terminal()
        t.send("echo before_close")
        t.send_key("enter")
        self.loop.run_until_complete(asyncio.sleep(0.3))
        t.close()
        self.terminals_to_cleanup.remove(t)

    def test_session_exists_true(self):
        t = self._create_terminal()
        self.assertTrue(_session_exists(t.session_name))

    def test_session_exists_false(self):
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
        call_count = 0
        original_session_exists = _session_exists

        def side_effect(name):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True
            return original_session_exists(name)

        mock_exists.side_effect = side_effect
        t = TmuxTerminal()
        self.terminals_to_cleanup.append(t)
        self.assertTrue(t.session_name.startswith(_SESSION_PREFIX))

    def test_start_reading_is_noop(self):
        t = self._create_terminal()
        self.loop.run_until_complete(t.start_reading())


if __name__ == "__main__":
    unittest.main()
