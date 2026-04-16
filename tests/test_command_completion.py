import unittest
from unittest.mock import Mock, AsyncMock, patch

from linhai.tui.app import TUIApp
from linhai.registry import Registry
from linhai.config import TUIConfig
from linhai.tui.messages_list import MessagesList
from linhai.sandbox import NoSandbox


def _create_test_app():
    registry = Registry()
    registry.register_queue("user_message")

    from linhai.agent.main import Agent
    from linhai.agent.message import AgentMessage
    from linhai.agent.orchestration import AgentContextOrchestration
    from linhai.agent.lifecycle import Lifecycle

    Lifecycle(registry)

    mock_agent = Mock(spec=Agent)
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

    import argparse

    registry.register_member("cli_args", argparse.Namespace(planning=False))

    from linhai.base import AnswerTokenUsage

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
    mock_llm_manager = Mock()
    mock_llm_manager.llms = []
    mock_agent.llm_manager = mock_llm_manager

    app = TUIApp(
        registry=registry,
        tui_config=TUIConfig(),
        init_messages=[],
        init_files=[],
    )

    mock_messages_list = AsyncMock(spec=MessagesList)
    mock_messages_list.add_user_message = AsyncMock()
    mock_messages_list.add_initial_messages = AsyncMock()
    mock_messages_list.start_listening = AsyncMock()
    mock_messages_list.cleanup = AsyncMock()
    mock_messages_list.mount = Mock()
    app.messages_list = mock_messages_list

    return app


class TestCommandCompletion(unittest.IsolatedAsyncioTestCase):

    @patch("linhai.tui.app.TUIApp.on_mount")
    async def test_tab_completes_partial_command(self, mock_on_mount):
        mock_on_mount.return_value = None
        app = _create_test_app()

        async with app.run_test() as pilot:
            input_el = pilot.app.query_one("#input")
            input_el.text = "/qu"
            input_el.move_cursor((0, 3))
            input_el._update_completion()
            input_el._complete_command()

            self.assertEqual(input_el.text, "/queue ")

    @patch("linhai.tui.app.TUIApp.on_mount")
    async def test_arrow_and_tab_selects_second(self, mock_on_mount):
        mock_on_mount.return_value = None
        app = _create_test_app()

        async with app.run_test() as pilot:
            input_el = pilot.app.query_one("#input")
            input_el.text = "/"
            input_el.move_cursor((0, 1))
            input_el._update_completion()

            from linhai.tui.components import CommandCompletionMenu

            menu = pilot.app.query_one("#completion-menu", CommandCompletionMenu)
            menu.select_down()
            input_el._complete_command()

            from linhai.agent.command_callback import CommandCallback

            commands = CommandCallback.get_command_completions()
            expected = commands[1] + " "
            self.assertEqual(input_el.text, expected)

    @patch("linhai.tui.app.TUIApp.on_mount")
    async def test_completion_at_beginning_preserves_rest(self, mock_on_mount):
        mock_on_mount.return_value = None
        app = _create_test_app()

        async with app.run_test() as pilot:
            input_el = pilot.app.query_one("#input")
            input_el.text = "/qu不要忘了测试"
            input_el.move_cursor((0, 3))
            input_el._update_completion()
            input_el._complete_command()

            self.assertEqual(input_el.text, "/queue 不要忘了测试")

    @patch("linhai.tui.app.TUIApp.on_mount")
    async def test_completion_preserves_trailing_text(self, mock_on_mount):
        mock_on_mount.return_value = None
        app = _create_test_app()

        async with app.run_test() as pilot:
            input_el = pilot.app.query_one("#input")
            input_el.text = "/qu xxx"
            input_el.move_cursor((0, 3))
            input_el._update_completion()
            input_el._complete_command()

            self.assertEqual(input_el.text, "/queue xxx")


if __name__ == "__main__":
    unittest.main()
