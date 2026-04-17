"""Master host control module for tools that interact with the local machine."""

from .master_host import MasterHostControl

from .http import http_request
from .terminal import (
    terminal_create,
    terminal_send_keys,
    terminal_send_string,
    terminal_read_screen,
    terminal_close,
    close_all_terminals,
    close_all_terminals_async,
    terminals,
    PyteTerminal,
    configure_terminals,
)
from .tmux_terminal import TmuxTerminal, is_tmux_available
from .file import (
    read_file,
    write_file,
    replace_file_content,
    list_files,
    get_absolute_path,
    read_file_with_sed,
)

__all__ = [
    "http_request",
    "terminal_create",
    "terminal_send_keys",
    "terminal_send_string",
    "terminal_read_screen",
    "terminal_close",
    "close_all_terminals",
    "close_all_terminals_async",
    "read_file",
    "write_file",
    "replace_file_content",
    "list_files",
    "get_absolute_path",
    "read_file_with_sed",
    "MasterHostControl",
    "PyteTerminal",
    "TmuxTerminal",
    "terminals",
    "configure_terminals",
    "is_tmux_available",
]
