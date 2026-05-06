import os
import time
from linhai.agent import Agent
from linhai.agent.messages import RuntimeMessage
from linhai.agent.lifecycle import AfterToolcallResult, Lifecycle
from linhai.registry import Registry
from linhai.plugin import Plugin

SHELL_COMMANDS = frozenset(
    {
        "echo",
        "cat",
        "cd",
        "grep",
        "sed",
        "awk",
        "python",
        "python3",
        "sh",
        "bash",
        "curl",
        "wget",
        "cp",
        "mv",
        "rm",
        "mkdir",
        "chmod",
        "chown",
        "pip",
        "npm",
        "git",
        "docker",
        "systemctl",
        "service",
        "export",
        "source",
        "apt",
        "yum",
        "dnf",
        "tar",
        "find",
        "ls",
        "head",
        "tail",
        "wc",
        "sort",
        "uniq",
        "tee",
        "xargs",
        "touch",
        "ln",
        "df",
        "du",
        "kill",
        "ps",
        "top",
        "env",
        "which",
        "whoami",
        "hostname",
        "uname",
        "date",
        "sleep",
        "man",
        "less",
        "more",
        "nano",
        "vim",
        "vi",
        "emacs",
        "jq",
        "nc",
        "ssh",
        "scp",
        "rsync",
        "make",
        "cmake",
        "gcc",
        "g++",
        "cargo",
        "rustc",
        "go",
        "node",
        "ruby",
        "perl",
        "php",
        "java",
        "javac",
        "dotnet",
        "swift",
        "tr",
        "cut",
        "paste",
        "diff",
        "patch",
        "column",
        "printf",
        "read",
        "test",
        "true",
        "false",
        "return",
        "exit",
        "set",
        "unset",
        "shift",
        "eval",
        "exec",
        "trap",
        "wait",
        "apt-get",
        "apt-cache",
        "dpkg",
        "snap",
        "brew",
        "pacman",
        "journalctl",
        "ip",
        "ifconfig",
        "ping",
        "traceroute",
        "dig",
        "nslookup",
        "host",
        "ss",
        "netstat",
        "lsof",
        "strace",
        "ltrace",
        "gdb",
        "valgrind",
        "objdump",
        "nm",
        "readelf",
    }
)


class StdioCommandCheckerPlugin(Plugin):
    TIME_WINDOW_SECONDS = 300

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self._last_warning_time: float | None = None

    def register(self, lifecycle: Lifecycle) -> None:
        lifecycle.after_toolcall.register(self.after_toolcall)

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: str,
        message,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> AfterToolcallResult | None:
        if tool_name != "process_stdio_write":
            return None

        content = toolcall_arguments.get("content")
        if not content or not isinstance(content, str):
            return None

        if not _is_shell_command(content):
            return None

        if self._last_warning_time is not None:
            if time.time() - self._last_warning_time < self.TIME_WINDOW_SECONDS:
                return None

        self._last_warning_time = time.time()
        agent = self.registry.get_member_typechecked("agent", Agent)
        await agent.message_processor.add_new_message(
            RuntimeMessage(
                "警告：检测到你通过process_stdio_write向进程发送了shell命令。"
                "这会导致使用次优方式读写文件（例如滥用sed写入）并可能造成文件损坏。"
                "请使用connect_posix_shell_as_machine工具将该shell进程连接为机器，"
                "然后直接使用read_file、write_file、replace_file_content等工具操作文件。"
            )
        )
        return None


def _is_shell_command(content: str) -> bool:
    stripped = content.lstrip()
    if not stripped:
        return False
    first_token = stripped.split()[0] if stripped.split() else ""
    base = os.path.basename(first_token)
    return base in SHELL_COMMANDS
