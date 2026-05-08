import os
import time
from linhai.type_hints import WithSecret
from linhai.agent.messages import RuntimeMessage
from linhai.agent.lifecycle import AfterToolcallResult, Lifecycle
from linhai.registry import Registry
from linhai.plugin import Plugin
from linhai.tool.base import SuccessfulToolResult, FailedToolResult


class SudoBashHintPlugin(Plugin):
    TIME_WINDOW_SECONDS = 300

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self._last_hint_time: float | None = None

    def register(self, lifecycle: Lifecycle) -> None:
        lifecycle.after_toolcall.register(self.after_toolcall)

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: str,
        message,
        toolcall_arguments: dict,
        with_secret: WithSecret | None,
        is_tool_failed_duplicated_error: bool,
    ) -> AfterToolcallResult | None:
        if tool_name != "process_create" or status != "success":
            return None

        argv = toolcall_arguments.get("argv")
        if not argv or not isinstance(argv, list) or len(argv) == 0:
            return None

        hint = self._build_hint(argv)
        if hint is None:
            return None

        if self._last_hint_time is not None:
            if time.time() - self._last_hint_time < self.TIME_WINDOW_SECONDS:
                return None

        self._last_hint_time = time.time()
        return AfterToolcallResult(warnings=[RuntimeMessage(hint)])

    @staticmethod
    def _build_hint(argv: list) -> str | None:
        first = argv[0]

        if first == "sudo":
            has_bash_or_sh = any(
                os.path.basename(arg) in ("bash", "sh")
                for arg in argv[1:]
                if not arg.startswith("-")
            )
            if has_bash_or_sh:
                return None
            return (
                "提示：检测到你使用sudo运行了非bash/sh命令。"
                "优先考虑运行sudo -S bash并使用connect_posix_shell_as_machine工具连接posix shell为机器，"
                "以避免用非标准方式读写文件并避免转义带来的心智负担"
            )

        if first == "su":
            return (
                "提示：检测到你使用su命令。"
                "建议使用connect_posix_shell_as_machine工具将su启动的shell连接为机器，"
                "以避免重复输入密码"
            )

        if first == "adb":
            if "shell" not in argv[1:]:
                return None
            return (
                "提示：检测到你使用adb shell命令。"
                "建议使用connect_posix_shell_as_machine工具将adb shell连接为机器"
            )

        python_argv = _extract_python_argv(argv)
        if python_argv is not None and "-c" in python_argv[1:]:
            return (
                "提示：检测到你使用python -c运行python命令。"
                "你有考虑过直接启动python repl并使用吗？"
            )

        return None


PYTHON_BASENAMES = frozenset({"python", "python3"})


def _extract_python_argv(argv: list) -> list | None:
    base = os.path.basename(argv[0])
    if base in PYTHON_BASENAMES:
        return argv
    if argv[0] == "uv" and len(argv) > 2 and argv[1] == "run":
        sub_base = os.path.basename(argv[2])
        if sub_base in PYTHON_BASENAMES:
            return argv[2:]
    return None


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
        with_secret: WithSecret | None,
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
        return AfterToolcallResult(
            warnings=[
                RuntimeMessage(
                    "警告：检测到你通过process_stdio_write向进程发送了shell命令。"
                    "这会导致使用次优方式读写文件（例如滥用sed写入）并可能造成文件损坏。"
                    "请使用connect_posix_shell_as_machine工具将该shell进程连接为机器，"
                    "然后直接使用read_file、write_file、replace_file_content等工具操作文件。"
                )
            ]
        )


class PkillCheckerPlugin(Plugin):
    BLOCKED_COMMANDS = frozenset({"pkill"})

    def register(self, lifecycle: Lifecycle) -> None:
        lifecycle.before_tool_call.register(self.before_tool_call)

    async def before_tool_call(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
    ) -> SuccessfulToolResult | FailedToolResult | dict | None:
        if tool_name != "process_create":
            return None

        argv = toolcall_arguments.get("argv")
        if not argv or not isinstance(argv, list) or len(argv) == 0:
            return None

        if os.path.basename(argv[0]) in self.BLOCKED_COMMANDS:
            return FailedToolResult(
                content="错误：禁止使用pkill杀死进程。如果你需要杀死进程，**优先**手动找到对应的PID, "
                "在**确认进程的cmd后**使用kill杀死；如果你确实需要使用pkill, "
                "使用which pkill找到绝对路径并使用绝对路径重新调用"
            )

        return None


def _is_shell_command(content: str) -> bool:
    stripped = content.lstrip()
    if not stripped:
        return False
    first_token = stripped.split()[0] if stripped.split() else ""
    base = os.path.basename(first_token)
    return base in SHELL_COMMANDS
