"""测试Planning tab功能"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import asyncio
import tempfile
from pathlib import Path

from linhai.sandbox import NoSandbox
from linhai.tui.planning_tab import PlanningTabWidget, FILE_NAMES
from linhai.tui.app import TUIApp
from linhai.registry import Registry


class TestPlanningTabWidget(unittest.TestCase):
    """测试PlanningTabWidget"""

    def test_creation(self):
        """测试PlanningTabWidget创建"""
        registry = Registry()
        widget = PlanningTabWidget(registry)
        self.assertIsNotNone(widget)
        self.assertEqual(widget.refresh_interval, 0.5)
        self.assertIsNone(widget.planning_folder)

    def test_get_planning_folder_none(self):
        """测试planning_folder未注册时返回None"""
        registry = Registry()
        widget = PlanningTabWidget(registry)
        self.assertIsNone(widget._get_planning_folder())

    def test_get_planning_folder_registered(self):
        """测试planning_folder注册后能获取"""
        registry = Registry()
        path = Path("/tmp/test_planning")
        registry.register_member("planning_folder", path)
        widget = PlanningTabWidget(registry)
        result = widget._get_planning_folder()
        self.assertEqual(result, path)

    @patch("linhai.tui.planning_tab.PlanningTabWidget.update_display")
    @patch("linhai.tui.planning_tab.PlanningTabWidget.set_interval")
    def test_on_mount(self, mock_set_interval, mock_update_display):
        """测试组件挂载"""
        registry = Registry()
        widget = PlanningTabWidget(registry)
        widget.on_mount()
        mock_update_display.assert_called_once()
        mock_set_interval.assert_called_once_with(0.5, widget.update_display)

    def test_update_display_reads_files(self):
        """测试update_display读取文件内容"""
        with tempfile.TemporaryDirectory() as tmpdir:
            planning_folder = Path(tmpdir)
            for name in FILE_NAMES:
                (planning_folder / name).write_text(
                    f"content of {name}", encoding="utf-8"
                )

            registry = Registry()
            registry.register_member("planning_folder", planning_folder)
            widget = PlanningTabWidget(registry)

            from textual.widgets import Markdown

            mock_markdown = Mock(spec=Markdown)
            widget.query_one = Mock(return_value=mock_markdown)

            widget.update_display()

            self.assertEqual(mock_markdown.update.call_count, 3)

    def test_update_display_skips_unchanged(self):
        """测试update_display跳过未修改的文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            planning_folder = Path(tmpdir)
            for name in FILE_NAMES:
                (planning_folder / name).write_text(
                    f"content of {name}", encoding="utf-8"
                )

            registry = Registry()
            registry.register_member("planning_folder", planning_folder)
            widget = PlanningTabWidget(registry)

            from textual.widgets import Markdown

            mock_markdown = Mock(spec=Markdown)
            widget.query_one = Mock(return_value=mock_markdown)

            widget.update_display()
            first_count = mock_markdown.update.call_count

            widget.update_display()
            self.assertEqual(mock_markdown.update.call_count, first_count)

    def test_update_display_detects_changes(self):
        """测试文件内容更新后刷新显示"""
        with tempfile.TemporaryDirectory() as tmpdir:
            planning_folder = Path(tmpdir)
            status_file = planning_folder / "STATUS.md"
            status_file.write_text("old content", encoding="utf-8")
            for name in FILE_NAMES:
                if not (planning_folder / name).exists():
                    (planning_folder / name).write_text("", encoding="utf-8")

            registry = Registry()
            registry.register_member("planning_folder", planning_folder)
            widget = PlanningTabWidget(registry)

            from textual.widgets import Markdown

            mock_markdown = Mock(spec=Markdown)
            widget.query_one = Mock(return_value=mock_markdown)

            widget.update_display()
            first_count = mock_markdown.update.call_count

            status_file.write_text("new content", encoding="utf-8")

            widget.update_display()
            self.assertEqual(mock_markdown.update.call_count, first_count + 1)


class TestPlanningTabInApp(unittest.TestCase):
    """测试Planning tab在应用中的条件显示"""

    @patch("linhai.tui.app.TUIApp.on_mount")
    def test_planning_tab_not_shown_without_planning(self, mock_on_mount):
        """测试不开启planning模式时没有Planning tab"""
        mock_on_mount.return_value = None

        registry = Registry()
        from linhai.agent.main import Agent
        from linhai.agent.message import AgentMessage
        from linhai.agent.orchestration import AgentContextOrchestration
        from linhai.agent.lifecycle import Lifecycle
        from linhai.base import AnswerTokenUsage
        import argparse

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
        mock_llm.get_token_limit.return_value = 8000
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
        registry.register_member("process_sandbox", NoSandbox())
        Lifecycle(registry)

        mock_cli_args = argparse.Namespace()
        mock_cli_args.message = None
        mock_cli_args.file = None
        mock_cli_args.planning = False
        registry.register_member("cli_args", mock_cli_args)

        from linhai.config import TUIConfig

        app = TUIApp(
            registry=registry, tui_config=TUIConfig(), init_messages=[], init_files=[]
        )

        async def _run_test():
            async with app.run_test() as pilot:
                planning_tab = pilot.app.query("#planning-tab")
                self.assertEqual(len(planning_tab), 0)

        asyncio.run(_run_test())

    @patch("linhai.tui.app.TUIApp.on_mount")
    def test_planning_tab_shown_with_planning(self, mock_on_mount):
        """测试开启planning模式时显示Planning tab"""
        mock_on_mount.return_value = None

        registry = Registry()
        from linhai.agent.main import Agent
        from linhai.agent.message import AgentMessage
        from linhai.agent.orchestration import AgentContextOrchestration
        from linhai.agent.lifecycle import Lifecycle
        from linhai.base import AnswerTokenUsage
        import argparse

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
        mock_llm.get_token_limit.return_value = 8000
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
        registry.register_member("process_sandbox", NoSandbox())
        Lifecycle(registry)

        mock_cli_args = argparse.Namespace()
        mock_cli_args.message = None
        mock_cli_args.file = None
        mock_cli_args.planning = True
        registry.register_member("cli_args", mock_cli_args)

        with tempfile.TemporaryDirectory() as tmpdir:
            planning_folder = Path(tmpdir)
            registry.register_member("planning_folder", planning_folder)

            from linhai.config import TUIConfig

            app = TUIApp(
                registry=registry,
                tui_config=TUIConfig(),
                init_messages=[],
                init_files=[],
            )

            async def _run_test():
                async with app.run_test() as pilot:
                    planning_tab = pilot.app.query("#planning-tab")
                    self.assertEqual(len(planning_tab), 1)

                    planning_widgets = planning_tab[0].query(PlanningTabWidget)
                    self.assertEqual(len(planning_widgets), 1)

            asyncio.run(_run_test())

    @patch("linhai.tui.app.TUIApp.on_mount")
    def test_collapsible_shows_content_after_collapse(self, mock_on_mount):
        """测试折叠STATUS.md后可以看到TODOLIST.md的内容"""
        mock_on_mount.return_value = None

        registry = Registry()
        from linhai.agent.main import Agent
        from linhai.agent.message import AgentMessage
        from linhai.agent.orchestration import AgentContextOrchestration
        from linhai.agent.lifecycle import Lifecycle
        from linhai.base import AnswerTokenUsage
        import argparse

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
        mock_llm.get_token_limit.return_value = 8000
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
        registry.register_member("process_sandbox", NoSandbox())
        Lifecycle(registry)

        mock_cli_args = argparse.Namespace()
        mock_cli_args.message = None
        mock_cli_args.file = None
        mock_cli_args.planning = True
        registry.register_member("cli_args", mock_cli_args)

        with tempfile.TemporaryDirectory() as tmpdir:
            planning_folder = Path(tmpdir)
            (planning_folder / "STATUS.md").write_text(
                "# Status\nSome status", encoding="utf-8"
            )
            (planning_folder / "TODOLIST.md").write_text(
                "# Todolist\nSome tasks", encoding="utf-8"
            )
            (planning_folder / "DESIGN.md").write_text(
                "# Design\nSome design", encoding="utf-8"
            )
            registry.register_member("planning_folder", planning_folder)

            from linhai.config import TUIConfig

            app = TUIApp(
                registry=registry,
                tui_config=TUIConfig(),
                init_messages=[],
                init_files=[],
            )

            async def _run_test():
                async with app.run_test() as pilot:
                    status_collapsible = pilot.app.query_one(
                        "#planning-collapsible-status-md"
                    )
                    self.assertIsNotNone(status_collapsible)

                    from textual.widgets import Collapsible

                    status_collapsible.collapsed = True
                    self.assertTrue(status_collapsible.collapsed)

                    todolist_collapsible = pilot.app.query_one(
                        "#planning-collapsible-todolist-md"
                    )
                    self.assertIsNotNone(todolist_collapsible)
                    self.assertFalse(todolist_collapsible.collapsed)

            asyncio.run(_run_test())


if __name__ == "__main__":
    unittest.main()
