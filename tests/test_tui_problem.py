import unittest
from unittest.mock import Mock, patch
import asyncio
from linhai.tui.app import TUIApp
from linhai.tui.components import ProblemWidget
from linhai.registry import Registry
from linhai.config import TUIConfig
from linhai.agent.main import Agent
from linhai.sandbox import NoSandbox
from linhai.problem_manager import PlainProblemManager


def _make_registry():
    registry = Registry()
    mock_agent = Mock(spec=Agent)
    from linhai.agent.message import AgentMessage
    from linhai.agent.orchestration import AgentContextOrchestration
    from linhai.base import AnswerTokenUsage

    mock_agent.get_threshold_info.return_value = {
        "hard_limit": 8000,
        "used_tokens": 6000,
        "usage_ratio": 0.75,
    }
    mock_llm = Mock()
    mock_llm.get_token_limit.return_value = 128000
    mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm)
    mock_agent.last_token_usage = AnswerTokenUsage(
        input_tokens=1000,
        output_tokens=200,
        total_tokens=1200,
        cached_input_tokens=500,
    )

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

    from linhai.agent.lifecycle import Lifecycle

    Lifecycle(registry)

    import argparse

    mock_cli_args = argparse.Namespace(planning=False)
    registry.register_member("cli_args", mock_cli_args)
    registry.register_member("process_sandbox", NoSandbox())
    PlainProblemManager(registry)
    return registry


class TestProblemWidget(unittest.TestCase):
    @patch("linhai.tui.app.TUIApp.on_mount")
    def test_problem_widget_mounted(self, mock_app_mount):
        mock_app_mount.return_value = None
        asyncio.run(self._test_problem_widget_mounted())

    async def _test_problem_widget_mounted(self):
        registry = _make_registry()
        app = TUIApp(
            registry=registry, tui_config=TUIConfig(), init_messages=[], init_files=[]
        )
        async with app.run_test() as pilot:
            widget = pilot.app.query_one(ProblemWidget)
            self.assertIsNotNone(widget)
            self.assertFalse(widget.display)

    @patch("linhai.tui.app.TUIApp.on_mount")
    def test_problem_widget_show_problem(self, mock_app_mount):
        mock_app_mount.return_value = None
        asyncio.run(self._test_problem_widget_show_problem())

    async def _test_problem_widget_show_problem(self):
        from textual.widgets import RadioSet

        registry = _make_registry()
        app = TUIApp(
            registry=registry, tui_config=TUIConfig(), init_messages=[], init_files=[]
        )
        async with app.run_test() as pilot:
            widget = pilot.app.query_one(ProblemWidget)
            pm = registry.get_member_typechecked("problem_manager", PlainProblemManager)
            pm.create_problem("test question?", ["opt_a", "opt_b"])
            widget._check_problems()
            self.assertTrue(widget.display)
            radioset = widget.query_one(".problem-options", RadioSet)
            self.assertIsNotNone(radioset)


if __name__ == "__main__":
    unittest.main()
