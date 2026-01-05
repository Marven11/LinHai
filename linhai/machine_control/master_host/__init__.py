"""Master host control module for tools that interact with the local machine."""

"""Master host control module for tools that interact with the local machine."""

from .master_host import MasterHostControl

from .http import http_request
from .command import run_command, change_directory
from .terminal import (
    terminal_create,
    terminal_send_keys,
    terminal_send_string,
    terminal_read_screen,
    terminal_close,
    close_all_terminals,
    terminal_toolset,
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
    insert_at_line,
)


__all__ = [
    "http_request",
    "run_command",
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
    "insert_at_line",
    "MasterHostControl",
    "PyteTerminal",
    "terminals",
    "terminal_toolset",
]
