import unittest
from unittest.mock import Mock, patch
import asyncio
import tempfile
from pathlib import Path

from linhai.sandbox import NoSandbox
from linhai.tui.planning_tab import PlanningTabWidget, FILE_NAMES
from linhai.tui.app import TUIApp
from linhai.registry import Registry


class TestPlanningTabWidget(unittest.TestCase):
    def test_update_display_detects_changes(self):
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
    @patch("linhai.tui.app.TUIApp.on_mount")
    def test_planning_tab_not_shown_without_planning(self, mock_on_mount):
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
