import pytest

from linhai.machine_control.master_host.terminal import (
    terminal_create,
    terminal_send_string,
    terminal_read_screen,
    terminal_close,
    close_all_terminals_async,
    configure_terminals,
    terminals,
)
from linhai.machine_control.master_host.tmux_terminal import TmuxTerminal

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _setup_terminal():
    terminals.clear()
    configure_terminals(True)
    yield
    await close_all_terminals_async()
    terminals.clear()
    configure_terminals(False)


async def test_tmux_terminal_create_and_send():
    term_id = await terminal_create()
    assert term_id in terminals
    assert isinstance(terminals[term_id], TmuxTerminal)

    result = await terminal_send_string(term_id, "echo e2e_tmux_test", with_enter=True)
    assert "e2e_tmux_test" in result

    screen = await terminal_read_screen(term_id)
    assert "e2e_tmux_test" in screen

    await terminal_close(term_id)
    assert term_id not in terminals


async def test_tmux_terminal_send_keys():
    term_id = await terminal_create()
    result = await terminal_send_string(term_id, "echo ctrl_l_test", with_enter=True)
    assert "ctrl_l_test" in result

    from linhai.machine_control.master_host import terminal_send_keys

    result = await terminal_send_keys(term_id, ["ctrl+l"])
    assert "ctrl+l" in result or "Ctrl" in result

    await terminal_close(term_id)


async def test_tmux_close_all_async():
    id1 = await terminal_create()
    id2 = await terminal_create()
    assert len(terminals) >= 2
    await close_all_terminals_async()
    assert len(terminals) == 0
