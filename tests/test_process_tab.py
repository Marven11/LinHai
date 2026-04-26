import asyncio
import time
import unittest
from unittest.mock import Mock

from linhai.agent.lifecycle import Lifecycle
from linhai.agent.message import AgentMessage
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.base import AnswerTokenUsage
from linhai.config import TUIConfig
from linhai.machine_control.process import (
    ProcessCreateInfo,
    ProcessKillResult,
    ProcessWaitResult,
)
from linhai.registry import Registry
from linhai.tui.app import TUIApp
from linhai.tui.process_tab import ProcessRowWidget, ProcessTabWidget
from textual.widgets import Static


class _FakeProcess:
    def __init__(self, pid: str = "12345", exits_on_wait: bool = True):
        self._pid = pid
        self._exits_on_wait = exits_on_wait
        self._killed = False

    @property
    def pid(self) -> str:
        return self._pid

    async def stdio_write(self, content: str, with_enter: bool):
        pass

    async def stdio_read(self, wait_seconds: float, unescape_ansi: bool = True):
        pass

    async def wait(self, timeout: float):
        if self._exits_on_wait:
            return ProcessWaitResult(pid=self._pid, success=True, returncode=0)
        return ProcessWaitResult(pid=self._pid, success=False, error="timeout")

    async def kill(self, graceful: bool = True):
        self._killed = True
        return ProcessKillResult(pid=self._pid, success=True, message="killed")


def _make_registry() -> tuple[Registry, Lifecycle]:
    from linhai.agent.main import Agent
    import argparse

    registry = Registry()

    mock_agent = Mock(spec=Agent)
    mock_agent.get_threshold_info.return_value = {
        "hard_limit": 8000,
        "used_tokens": 6000,
        "usage_ratio": 0.75,
    }
    mock_agent.last_token_usage = AnswerTokenUsage(
        input_tokens=1000,
        output_tokens=200,
        total_tokens=1200,
        cached_input_tokens=500,
    )
    mock_llm = Mock()
    mock_llm.get_name.return_value = "test-llm"
    mock_llm.get_token_limit.return_value = 8000
    mock_llm_manager = Mock()
    mock_llm_manager.llms = [mock_llm]
    mock_agent.llm_manager = mock_llm_manager
    mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm)

    mock_agent_message = Mock(spec=AgentMessage)
    mock_agent_message.messages = []
    mock_agent_message.pinned_messages = []
    mock_agent_message.notification_messages = {}
    mock_orchestration = Mock(spec=AgentContextOrchestration)
    mock_orchestration.large_messages = set()
    mock_orchestration.agent_message = mock_agent_message
    mock_orchestration.cleaned_messages = {}

    registry.register_member("agent", mock_agent)
    registry.register_member("agent_message", mock_agent_message)
    registry.register_member("agent_context_orchestration", mock_orchestration)
    lifecycle = Lifecycle(registry)

    mock_cli_args = argparse.Namespace()
    mock_cli_args.message = None
    mock_cli_args.file = None
    mock_cli_args.planning = False
    registry.register_member("cli_args", mock_cli_args)

    from linhai.tool.main import ToolManager

    mock_tool_manager = Mock(spec=ToolManager)
    mock_tool_manager.register_toolset = Mock()
    registry.register_member("tool_manager", mock_tool_manager)

    return registry, lifecycle


def _make_app(registry: Registry) -> TUIApp:
    return TUIApp(
        registry=registry,
        tui_config=TUIConfig(),
        init_messages=[],
        init_files=[],
    )


class TestProcessCreateInfo(unittest.TestCase):
    def test_creation_sets_defaults(self):
        proc = _FakeProcess()
        info = ProcessCreateInfo(
            process=proc,
            argv=["ls", "-la"],
            machine_id="master_host",
        )
        self.assertIs(info.process, proc)
        self.assertEqual(info.argv, ["ls", "-la"])
        self.assertEqual(info.machine_id, "master_host")
        self.assertIsNone(info.initial_returncode)
        self.assertGreater(info.created_at, 0.0)

    def test_creation_with_explicit_values(self):
        proc = _FakeProcess()
        t = time.monotonic()
        info = ProcessCreateInfo(
            process=proc,
            argv=["python", "script.py"],
            machine_id="posix_shell",
            created_at=t,
            initial_returncode=0,
        )
        self.assertEqual(info.created_at, t)
        self.assertEqual(info.initial_returncode, 0)


class TestAfterProcessCreateCallback(unittest.IsolatedAsyncioTestCase):
    async def test_callback_triggered(self):
        registry, lifecycle = _make_registry()
        received = []

        async def cb(info: ProcessCreateInfo):
            received.append(info)

        lifecycle.after_process_create.register(cb)

        proc = _FakeProcess()
        info = ProcessCreateInfo(process=proc, argv=["echo"], machine_id="master_host")
        await lifecycle.after_process_create.trigger(info)

        self.assertEqual(len(received), 1)
        self.assertIs(received[0].process, proc)
        self.assertEqual(received[0].argv, ["echo"])


class TestProcessTabRealApp(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch

        self.locale_patch = patch(
            "linhai.utils.i18n.locale.getlocale", return_value=("en_US", "UTF-8")
        )
        self.locale_patch.start()
        super().setUp()

    def tearDown(self):
        self.locale_patch.stop()
        super().tearDown()

    def test_process_create_shows_in_tab(self):
        registry, lifecycle = _make_registry()
        app = _make_app(registry)

        async def _run():
            async with app.run_test() as pilot:
                process_tab = pilot.app.query_one(ProcessTabWidget)
                self.assertEqual(len(process_tab._entries), 0)

                proc = _FakeProcess("100")
                info = ProcessCreateInfo(
                    process=proc,
                    argv=["sleep", "10"],
                    machine_id="master_host",
                    initial_returncode=None,
                )
                await lifecycle.after_process_create.trigger(info)
                await pilot.pause()

                self.assertEqual(len(process_tab._entries), 1)
                self.assertIn("100", process_tab._entries)

                rows = process_tab.query(ProcessRowWidget)
                self.assertEqual(len(rows), 1)

                status_static = rows[0].query_one(".status")
                self.assertIn("Running", str(status_static.render()))

        asyncio.run(_run())

    def test_process_user_kill(self):
        registry, lifecycle = _make_registry()
        app = _make_app(registry)

        async def _run():
            async with app.run_test() as pilot:
                process_tab = pilot.app.query_one(ProcessTabWidget)

                proc = _FakeProcess("200")
                info = ProcessCreateInfo(
                    process=proc,
                    argv=["long_running_cmd"],
                    machine_id="master_host",
                    initial_returncode=None,
                )
                await lifecycle.after_process_create.trigger(info)
                await pilot.pause()

                rows = process_tab.query(ProcessRowWidget)
                self.assertEqual(len(rows), 1)

                from textual.widgets import Button

                kill_btn = rows[0].query_one(Button)
                self.assertFalse(kill_btn.disabled)
                self.assertEqual(kill_btn.label, "Kill")

                kill_btn.press()
                await pilot.pause()

                self.assertTrue(proc._killed)

                status_static = rows[0].query_one(".status")
                self.assertIn("Exit 0", str(status_static.render()))

                self.assertFalse(kill_btn.display)

        asyncio.run(_run())

    def test_process_exits_naturally(self):
        registry, lifecycle = _make_registry()
        app = _make_app(registry)

        async def _run():
            async with app.run_test() as pilot:
                process_tab = pilot.app.query_one(ProcessTabWidget)

                proc = _FakeProcess("300", exits_on_wait=True)
                info = ProcessCreateInfo(
                    process=proc,
                    argv=["echo", "hello"],
                    machine_id="master_host",
                    initial_returncode=None,
                )
                await lifecycle.after_process_create.trigger(info)
                await pilot.pause()

                rows = process_tab.query(ProcessRowWidget)
                self.assertEqual(len(rows), 1)
                status_static = rows[0].query_one(".status")
                self.assertIn("Running", str(status_static.render()))

                process_tab._poll_statuses()
                await pilot.pause()
                await pilot.pause()

                entry = process_tab._entries.get("300")
                self.assertIsNotNone(entry)
                _, returncode, exit_time = entry
                self.assertEqual(returncode, 0)

                status_static = rows[0].query_one(".status")
                self.assertIn("Exit 0", str(status_static.render()))

        asyncio.run(_run())

    def test_multiple_processes(self):
        registry, lifecycle = _make_registry()
        app = _make_app(registry)

        async def _run():
            async with app.run_test() as pilot:
                process_tab = pilot.app.query_one(ProcessTabWidget)

                for i in range(3):
                    proc = _FakeProcess(f"pid-{i}")
                    info = ProcessCreateInfo(
                        process=proc,
                        argv=["cmd", str(i)],
                        machine_id="master_host",
                        initial_returncode=None,
                    )
                    await lifecycle.after_process_create.trigger(info)
                    await pilot.pause()

                self.assertEqual(len(process_tab._entries), 3)
                rows = process_tab.query(ProcessRowWidget)
                self.assertEqual(len(rows), 3)

        asyncio.run(_run())


class TestProcessTabExitCleanup(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch

        self.locale_patch = patch(
            "linhai.utils.i18n.locale.getlocale", return_value=("en_US", "UTF-8")
        )
        self.locale_patch.start()
        super().setUp()

    def tearDown(self):
        self.locale_patch.stop()
        super().tearDown()

    def test_exited_process_records_exit_time(self):
        registry, lifecycle = _make_registry()
        app = _make_app(registry)

        async def _run():
            async with app.run_test() as pilot:
                process_tab = pilot.app.query_one(ProcessTabWidget)

                proc = _FakeProcess("400", exits_on_wait=True)
                info = ProcessCreateInfo(
                    process=proc,
                    argv=["echo", "test"],
                    machine_id="master_host",
                    initial_returncode=None,
                )
                await lifecycle.after_process_create.trigger(info)
                await pilot.pause()

                self.assertIsNone(process_tab._entries["400"][2])

                process_tab._poll_statuses()
                await pilot.pause()
                await pilot.pause()

                entry = process_tab._entries.get("400")
                self.assertIsNotNone(entry)
                _, returncode, exit_time = entry
                self.assertEqual(returncode, 0)
                self.assertIsNotNone(exit_time)

        asyncio.run(_run())

    def test_exited_process_cleaned_after_timeout(self):
        registry, lifecycle = _make_registry()
        app = _make_app(registry)

        async def _run():
            async with app.run_test() as pilot:
                process_tab = pilot.app.query_one(ProcessTabWidget)
                process_tab._EXIT_CLEANUP_SECONDS = 0.0

                proc = _FakeProcess("500", exits_on_wait=True)
                info = ProcessCreateInfo(
                    process=proc,
                    argv=["echo", "cleanup"],
                    machine_id="master_host",
                    initial_returncode=None,
                )
                await lifecycle.after_process_create.trigger(info)
                await pilot.pause()

                process_tab._poll_statuses()
                await pilot.pause()
                await pilot.pause()

                self.assertIn("500", process_tab._entries)

                process_tab._poll_statuses()
                await pilot.pause()

                self.assertNotIn("500", process_tab._entries)
                self.assertNotIn("500", process_tab._rows)
                rows = process_tab.query(ProcessRowWidget)
                self.assertEqual(len(rows), 0)

                empty = process_tab.query_one("#process-empty", Static)
                self.assertTrue(empty.display)

        asyncio.run(_run())

    def test_recently_exited_process_not_cleaned(self):
        registry, lifecycle = _make_registry()
        app = _make_app(registry)

        async def _run():
            async with app.run_test() as pilot:
                process_tab = pilot.app.query_one(ProcessTabWidget)
                process_tab._EXIT_CLEANUP_SECONDS = 99999.0

                proc = _FakeProcess("600", exits_on_wait=True)
                info = ProcessCreateInfo(
                    process=proc,
                    argv=["echo", "keep"],
                    machine_id="master_host",
                    initial_returncode=None,
                )
                await lifecycle.after_process_create.trigger(info)
                await pilot.pause()

                process_tab._poll_statuses()
                await pilot.pause()
                await pilot.pause()

                process_tab._poll_statuses()
                await pilot.pause()

                self.assertIn("600", process_tab._entries)
                rows = process_tab.query(ProcessRowWidget)
                self.assertEqual(len(rows), 1)

        asyncio.run(_run())

    def test_mixed_running_and_old_exited(self):
        registry, lifecycle = _make_registry()
        app = _make_app(registry)

        async def _run():
            import time as _time

            async with app.run_test() as pilot:
                process_tab = pilot.app.query_one(ProcessTabWidget)
                process_tab._EXIT_CLEANUP_SECONDS = 0.0

                exited_proc = _FakeProcess("700", exits_on_wait=True)
                exited_info = ProcessCreateInfo(
                    process=exited_proc,
                    argv=["echo", "old"],
                    machine_id="master_host",
                    initial_returncode=None,
                )
                await lifecycle.after_process_create.trigger(exited_info)
                await pilot.pause()

                running_proc = _FakeProcess("701", exits_on_wait=False)
                running_info = ProcessCreateInfo(
                    process=running_proc,
                    argv=["sleep", "inf"],
                    machine_id="master_host",
                    initial_returncode=None,
                )
                await lifecycle.after_process_create.trigger(running_info)
                await pilot.pause()

                process_tab._entries["700"] = (exited_info, 0, _time.monotonic() - 1.0)

                self.assertEqual(len(process_tab._entries), 2)

                process_tab._poll_statuses()
                await pilot.pause()

                self.assertNotIn("700", process_tab._entries)
                self.assertIn("701", process_tab._entries)
                rows = process_tab.query(ProcessRowWidget)
                self.assertEqual(len(rows), 1)

        asyncio.run(_run())


class TestProcessTabMarkupEscaping(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch

        self.locale_patch = patch(
            "linhai.utils.i18n.locale.getlocale", return_value=("en_US", "UTF-8")
        )
        self.locale_patch.start()
        super().setUp()

    def tearDown(self):
        self.locale_patch.stop()
        super().tearDown()

    def test_argv_with_square_brackets_no_crash(self):
        registry, lifecycle = _make_registry()
        app = _make_app(registry)

        async def _run():
            async with app.run_test() as pilot:
                process_tab = pilot.app.query_one(ProcessTabWidget)

                proc = _FakeProcess("800")
                info = ProcessCreateInfo(
                    process=proc,
                    argv=[
                        "bash",
                        "-c",
                        "PATH=/nix/store/bin:$PATH cargo flamegraph --bin encode_bench --output flamegraph.svg 2>&1",
                    ],
                    machine_id="master_host",
                    initial_returncode=None,
                )
                await lifecycle.after_process_create.trigger(info)
                await pilot.pause()

                rows = process_tab.query(ProcessRowWidget)
                self.assertEqual(len(rows), 1)

                argv_static = rows[0].query_one(".argv", Static)
                rendered = str(argv_static.render())
                self.assertIn("flamegraph", rendered)

        asyncio.run(_run())

    def test_argv_with_markup_like_content_no_crash(self):
        registry, lifecycle = _make_registry()
        app = _make_app(registry)

        async def _run():
            async with app.run_test() as pilot:
                process_tab = pilot.app.query_one(ProcessTabWidget)

                proc = _FakeProcess("801")
                info = ProcessCreateInfo(
                    process=proc,
                    argv=["echo", "[bold]text[/bold]", "[link]url[/link]"],
                    machine_id="master_host",
                    initial_returncode=None,
                )
                await lifecycle.after_process_create.trigger(info)
                await pilot.pause()

                rows = process_tab.query(ProcessRowWidget)
                self.assertEqual(len(rows), 1)

                argv_static = rows[0].query_one(".argv", Static)
                rendered = str(argv_static.render())
                self.assertIn("[bold]", rendered)

        asyncio.run(_run())


class TestProcessTabI18n(unittest.TestCase):
    """测试process_tab.py中的国际化功能。"""

    def test_process_tab_uses_i18n_function(self):
        """验证process_tab.py导入了i18n函数t()。"""
        import linhai.tui.process_tab as process_tab_module

        # 检查是否导入了t函数
        self.assertTrue(
            hasattr(process_tab_module, "t"),
            "process_tab.py should import t() from linhai.utils.i18n",
        )

        # 检查t函数是否正确导入
        from linhai.utils.i18n import t as i18n_t

        self.assertEqual(
            process_tab_module.t,
            i18n_t,
            "t() function in process_tab.py should be from linhai.utils.i18n",
        )

    def test_i18n_strings_in_code(self):
        """验证process_tab.py中的字符串使用了i18n函数。"""
        import inspect
        import linhai.tui.process_tab as process_tab_module

        source = inspect.getsource(process_tab_module)

        # 检查是否使用了t()函数调用
        self.assertIn(
            't({"en": "Running", "zh_CN": "运行中"})',
            source,
            "Should use i18n for 'Running' string",
        )
        self.assertIn(
            't({"en": "Kill", "zh_CN": "终止"})',
            source,
            "Should use i18n for 'Kill' string",
        )
        self.assertIn(
            't({"en": "Exit {}", "zh_CN": "退出 {}"})',
            source,
            "Should use i18n for 'Exit {}' string",
        )
        self.assertIn(
            't({"en": "No processes created yet.", "zh_CN": "尚未创建进程。"})',
            source,
            "Should use i18n for 'No processes created yet.' string",
        )


if __name__ == "__main__":
    unittest.main()
