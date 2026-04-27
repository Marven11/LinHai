import os
import time
from linhai.agent import Agent
from linhai.agent.messages import RuntimeMessage
from linhai.agent.lifecycle import Lifecycle
from linhai.registry import Registry
from linhai.plugin import Plugin


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
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ):
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
        agent = self.registry.get_member_typechecked("agent", Agent)
        await agent.message_processor.add_new_message(RuntimeMessage(hint))
        return None

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

        return None
