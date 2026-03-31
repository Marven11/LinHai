"""Master host control module for tools that interact with the local machine."""

from .master_host import MasterHostControl

from .http import http_request
from .command import change_directory
from .terminal import (
    terminal_create,
    terminal_send_keys,
    terminal_send_string,
    terminal_read_screen,
    terminal_close,
    close_all_terminals,
    terminals,
    PyteTerminal,
)
from .file import (
    read_file,
    write_file,
    replace_file_content,
    list_files,
    get_absolute_path,
    read_file_with_sed,
    modify_file_with_sed,
)


__all__ = [
    "http_request",
    "change_directory",
    "terminal_create",
    "terminal_send_keys",
    "terminal_send_string",
    "terminal_read_screen",
    "terminal_close",
    "close_all_terminals",
    "read_file",
    "write_file",
    "replace_file_content",
    "list_files",
    "get_absolute_path",
    "read_file_with_sed",
    "modify_file_with_sed",
    "MasterHostControl",
    "PyteTerminal",
    "terminals",
]
