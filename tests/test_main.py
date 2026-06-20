"""测试main.py中CLI参数到build_args的映射"""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
from pathlib import Path
from linhai.main import main


class TestMainCLIParameterMapping(unittest.TestCase):

    @patch("linhai.main.TUIApp")
    @patch("linhai.agent.create.create_agent_from_context")
    @patch("linhai.agent.create.create_agent_build_context")
    def test_llm_option_maps_to_build_args(
        self, mock_build_context, mock_create_agent, mock_cli_app
    ):
        mock_context = {
            "registry": MagicMock(),
            "config_basedir": Path("."),
            "message": [],
            "file": [],
        }
        mock_build_context.return_value = mock_context

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        test_args = ["linhai", "--llm", "test_llm"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit):
                main()

        mock_build_context.assert_called_once()
        call_kwargs = mock_build_context.call_args[1]
        build_args = call_kwargs["build_args"]
        self.assertEqual(build_args["llm_name"], "test_llm")

    @patch("linhai.main.TUIApp")
    @patch("linhai.agent.create.create_agent_from_context")
    @patch("linhai.agent.create.create_agent_build_context")
    def test_message_option_maps_to_build_args(
        self, mock_build_context, mock_create_agent, mock_cli_app
    ):
        mock_context = {
            "registry": MagicMock(),
            "config_basedir": Path("."),
            "message": [],
            "file": [],
        }
        mock_build_context.return_value = mock_context

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        test_args = ["linhai", "-m", "test message"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit):
                main()

        mock_build_context.assert_called_once()
        call_kwargs = mock_build_context.call_args[1]
        build_args = call_kwargs["build_args"]
        self.assertEqual(build_args["message"], ["test message"])

    @patch("linhai.main.TUIApp")
    @patch("linhai.agent.create.create_agent_from_context")
    @patch("linhai.agent.create.create_agent_build_context")
    def test_afk_flag_maps_to_build_args(
        self, mock_build_context, mock_create_agent, mock_cli_app
    ):
        mock_context = {
            "registry": MagicMock(),
            "config_basedir": Path("."),
            "message": [],
            "file": [],
        }
        mock_build_context.return_value = mock_context

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        test_args = ["linhai", "--afk"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit):
                main()

        mock_build_context.assert_called_once()
        call_kwargs = mock_build_context.call_args[1]
        build_args = call_kwargs["build_args"]
        self.assertTrue(build_args["afk"])

    @patch("linhai.main.TUIApp")
    @patch("linhai.agent.create.create_agent_from_context")
    @patch("linhai.agent.create.create_agent_build_context")
    def test_planning_flag_maps_to_build_args(
        self, mock_build_context, mock_create_agent, mock_cli_app
    ):
        mock_context = {
            "registry": MagicMock(),
            "config_basedir": Path("."),
            "message": [],
            "file": [],
        }
        mock_build_context.return_value = mock_context

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        test_args = ["linhai", "--planning"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit):
                main()

        mock_build_context.assert_called_once()
        call_kwargs = mock_build_context.call_args[1]
        build_args = call_kwargs["build_args"]
        self.assertTrue(build_args["planning"])

    @patch("linhai.main.TUIApp")
    @patch("linhai.agent.create.create_agent_from_context")
    @patch("linhai.agent.create.create_agent_build_context")
    def test_claw_flag_maps_to_build_args(
        self, mock_build_context, mock_create_agent, mock_cli_app
    ):
        mock_context = {
            "registry": MagicMock(),
            "config_basedir": Path("."),
            "message": [],
            "file": [],
        }
        mock_build_context.return_value = mock_context

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        test_args = ["linhai", "--claw"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit):
                main()

        mock_build_context.assert_called_once()
        call_kwargs = mock_build_context.call_args[1]
        build_args = call_kwargs["build_args"]
        self.assertTrue(build_args["claw_enabled"])

    @patch("linhai.main.TUIApp")
    @patch("linhai.agent.create.create_agent_from_context")
    @patch("linhai.agent.create.create_agent_build_context")
    def test_profile_option_maps_to_build_args(
        self, mock_build_context, mock_create_agent, mock_cli_app
    ):
        mock_context = {
            "registry": MagicMock(),
            "config_basedir": Path("."),
            "message": [],
            "file": [],
        }
        mock_build_context.return_value = mock_context

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        test_args = ["linhai", "--profile", "dev"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit):
                main()

        mock_build_context.assert_called_once()
        call_kwargs = mock_build_context.call_args[1]
        build_args = call_kwargs["build_args"]
        self.assertEqual(build_args["profile_name"], "dev")

    @patch("linhai.main.TUIApp")
    @patch("linhai.agent.create.create_agent_from_context")
    @patch("linhai.agent.create.create_agent_build_context")
    @patch("builtins.open")
    def test_file_option_maps_to_build_args(
        self, mock_open, mock_build_context, mock_create_agent, mock_cli_app
    ):
        mock_context = {
            "registry": MagicMock(),
            "config_basedir": Path("."),
            "message": [],
            "file": [],
        }
        mock_build_context.return_value = mock_context

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        mock_file = MagicMock()
        mock_file.read.return_value = "file content"
        mock_open.return_value.__enter__.return_value = mock_file

        test_args = ["linhai", "-f", "test.txt"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit):
                main()

        mock_build_context.assert_called_once()
        call_kwargs = mock_build_context.call_args[1]
        build_args = call_kwargs["build_args"]
        self.assertEqual(len(build_args["file"]), 1)

    @patch("linhai.main.TUIApp")
    @patch("linhai.agent.create.create_agent_from_context")
    @patch("linhai.agent.create.create_agent_build_context")
    def test_disable_waiting_marker_maps_to_build_args(
        self, mock_build_context, mock_create_agent, mock_cli_app
    ):
        mock_context = {
            "registry": MagicMock(),
            "config_basedir": Path("."),
            "message": [],
            "file": [],
        }
        mock_build_context.return_value = mock_context

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_app = MagicMock()
        mock_app.run_async = AsyncMock(return_value=None)
        mock_app.return_code = 0
        mock_cli_app.return_value = mock_app

        test_args = ["linhai", "--disable-waiting-marker"]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit):
                main()

        mock_build_context.assert_called_once()
        call_kwargs = mock_build_context.call_args[1]
        build_args = call_kwargs["build_args"]
        self.assertTrue(build_args["disable_waiting_marker"])


if __name__ == "__main__":
    unittest.main()
