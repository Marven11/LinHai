from __future__ import annotations

import shlex
import time
from datetime import datetime
from typing import Callable, Awaitable

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Static

from linhai.machine_control.process import ProcessCreateInfo, ProcessIOError
from linhai.registry import Registry
from linhai.utils.i18n import t


class ProcessRowWidget(Horizontal):
    DEFAULT_CSS = """
    ProcessRowWidget {
        height: 1;
        padding: 0 1;
    }
    ProcessRowWidget .argv {
        width: 1fr;
        text-overflow: ellipsis;
        text-wrap: nowrap;
        overflow: hidden;
        color: $text;
    }
    ProcessRowWidget .machine {
        width: 14;
        color: $text-muted;
    }
    ProcessRowWidget .time {
        width: 10;
        color: $text-muted;
    }
    ProcessRowWidget .status {
        width: 8;
    }
    ProcessRowWidget .status-running {
        color: #A3BE8C;
    }
    ProcessRowWidget .status-exited {
        color: $text-muted;
    }
    ProcessRowWidget Button.kill-btn {
        width: 8;
        height: 1;
        padding: 0 1;
        text-style: bold;
    }
    """

    def __init__(
        self,
        info: ProcessCreateInfo,
        returncode: int | None,
        kill_callback: Callable[[str], Awaitable[None]],
    ) -> None:
        super().__init__()
        self._info = info
        self._returncode = returncode
        self._kill_callback = kill_callback

    def compose(self) -> ComposeResult:
        cmd = shlex.join(self._info.argv)
        yield Static(cmd, classes="argv", markup=False)
        yield Static(self._info.machine_id, classes="machine", markup=False)
        created_str = datetime.fromtimestamp(self._info.created_at).strftime("%H:%M:%S")
        yield Static(created_str, classes="time")
        if self._returncode is None:
            yield Static(
                t({"en": "Running", "zh_CN": "运行中"}), classes="status status-running"
            )
            yield Button(
                t({"en": "Kill", "zh_CN": "终止"}), variant="error", classes="kill-btn"
            )
        else:
            yield Static(
                t({"en": "Exit {}", "zh_CN": "退出 {}"}).format(self._returncode),
                classes="status status-exited",
            )
            yield Static("", classes="kill-btn")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if "kill-btn" in event.button.classes:
            await self._kill_callback(self._info.process.pid)

    def update_status(self, returncode: int | None) -> None:
        if returncode == self._returncode:
            return
        self._returncode = returncode
        status_widget = self.query_one(".status", Static)
        kill_btns = self.query(".kill-btn")
        if returncode is None:
            status_widget.update(t({"en": "Running", "zh_CN": "运行中"}))
            status_widget.set_class(True, "status-running")
            status_widget.set_class(False, "status-exited")
        else:
            status_widget.update(
                t({"en": "Exit {}", "zh_CN": "退出 {}"}).format(returncode)
            )
            status_widget.set_class(False, "status-running")
            status_widget.set_class(True, "status-exited")
            for btn in kill_btns:
                if isinstance(btn, Button):
                    btn.display = False


class ProcessTabWidget(Static):
    DEFAULT_CSS = """
    ProcessTabWidget {
        width: 100%;
        height: 100%;
    }
    ProcessTabWidget VerticalScroll {
        scrollbar-size-vertical: 1;
    }
    """

    def __init__(self, registry: Registry) -> None:
        super().__init__()
        self.registry = registry
        self._entries: dict[str, tuple[ProcessCreateInfo, int | None, float | None]] = (
            {}
        )
        self._rows: dict[str, ProcessRowWidget] = {}

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(
                t({"en": "No processes created yet.", "zh_CN": "尚未创建进程。"}),
                id="process-empty",
            )

    def on_mount(self) -> None:
        from linhai.agent.lifecycle import Lifecycle

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        lifecycle.after_process_create.register(self._on_process_create)
        self.set_interval(2.0, self._poll_statuses)

    _EXIT_CLEANUP_SECONDS = 300.0

    async def _on_process_create(self, info: ProcessCreateInfo) -> None:
        pid = info.process.pid
        self._entries[pid] = (info, info.initial_returncode, None)
        empty = self.query_one("#process-empty", Static)
        empty.display = False
        row = ProcessRowWidget(info, info.initial_returncode, self._kill_process)
        self._rows[pid] = row
        scroll = self.query_one(VerticalScroll)
        scroll.mount(row)

    async def _kill_process(self, pid: str) -> None:
        entry = self._entries.get(pid)
        if entry is None:
            return
        info, _, _ = entry
        await info.process.kill()
        self._entries[pid] = (info, 0, time.monotonic())
        row = self._rows.get(pid)
        if row is not None:
            row.update_status(0)

    def _poll_statuses(self) -> None:
        now = time.monotonic()
        to_remove: list[str] = []
        for pid, (info, returncode, exit_time) in list(self._entries.items()):
            if exit_time is not None and now - exit_time > self._EXIT_CLEANUP_SECONDS:
                to_remove.append(pid)
                continue
            if returncode is not None:
                continue
            self._check_process_status(pid, info)
        for pid in to_remove:
            self._entries.pop(pid, None)
            row = self._rows.pop(pid, None)
            if row is not None:
                row.remove()
        if to_remove and not self._entries:
            empty = self.query_one("#process-empty", Static)
            empty.display = True

    @work(exclusive=True)
    async def _check_process_status(self, pid: str, info: ProcessCreateInfo) -> None:
        result = await info.process.wait(timeout=0.01)
        if isinstance(result, ProcessIOError):
            entry = self._entries.get(pid)
            if entry is not None:
                _, old_rc, _ = entry
                if old_rc is None:
                    self._entries[pid] = (info, -1, time.monotonic())
            row = self._rows.get(pid)
            if row is not None:
                row.update_status(-1)
            return
        if result.success:
            entry = self._entries.get(pid)
            if entry is not None:
                _, old_rc, _ = entry
                if old_rc is None:
                    self._entries[pid] = (info, result.returncode, time.monotonic())
            row = self._rows.get(pid)
            if row is not None:
                row.update_status(result.returncode)
