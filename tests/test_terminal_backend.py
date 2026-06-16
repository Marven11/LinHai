import asyncio
import unittest
from unittest.mock import patch

from linhai.machine_control.master_host.terminal import (
    terminal_create,
    terminal_close,
    close_all_terminals,
    close_all_terminals_async,
    configure_terminals,
    terminals,
    PyteTerminal,
)
from linhai.machine_control.master_host.tmux_terminal import TmuxTerminal


class TestTerminalBackendSelection(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        terminals.clear()

    def tearDown(self):
        close_all_terminals()
        terminals.clear()
        configure_terminals(False)
        self.loop.close()

    def test_default_creates_pyte(self):
        configure_terminals(False)
        term_id = self.loop.run_until_complete(terminal_create())
        self.assertIn(term_id, terminals)
        self.assertIsInstance(terminals[term_id], PyteTerminal)
        self.loop.run_until_complete(terminal_close(term_id))

    @patch(
        "linhai.machine_control.master_host.terminal.is_tmux_available",
        return_value=True,
    )
    def test_tmux_enabled_creates_tmux(self, _):
        configure_terminals(True)
        term_id = self.loop.run_until_complete(terminal_create())
        self.assertIn(term_id, terminals)
        self.assertIsInstance(terminals[term_id], TmuxTerminal)
        self.loop.run_until_complete(terminal_close(term_id))


class TestCloseAllTerminalsAsync(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        terminals.clear()
        configure_terminals(False)

    def tearDown(self):
        terminals.clear()
        self.loop.close()

    def test_close_all_async(self):
        id1 = self.loop.run_until_complete(terminal_create())
        id2 = self.loop.run_until_complete(terminal_create())
        self.assertEqual(len(terminals), 2)
        self.loop.run_until_complete(close_all_terminals_async())
        self.assertEqual(len(terminals), 0)

    def test_close_all_async_empty(self):
        self.loop.run_until_complete(close_all_terminals_async())
        self.assertEqual(len(terminals), 0)


if __name__ == "__main__":
    unittest.main()
