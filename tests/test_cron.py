import unittest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from linhai.cron import CronPlugin, CronDiffMessage, _format_result, parse_cron_arg
from linhai.task_supervisor import PlainTaskSupervisor


class TestCronDiffMessage(unittest.TestCase):

    def test_create(self):
        msg = CronDiffMessage(
            cron_expression="* * * * *",
            command="curl http://example.com/feed",
            result="hello",
        )
        self.assertEqual(msg.cron_expression, "* * * * *")
        self.assertEqual(msg.command, "curl http://example.com/feed")
        self.assertIn("hello", msg.result)

    def test_get_content(self):
        msg = CronDiffMessage(
            cron_expression="* * * * *",
            command="echo hi",
            result="test result",
        )
        content = msg.get_content()
        self.assertIn("<<cron_diff>>", content)
        self.assertIn("<<cron_expression>>* * * * *<<cron_expression>>", content)
        self.assertIn("<<command>>echo hi<<command>>", content)
        self.assertIn("<<result>>test result<<result>>", content)

    def test_to_json_from_json(self):
        msg = CronDiffMessage(
            cron_expression="0 * * * *",
            command="curl http://example.com",
            result="some output",
        )
        json_str = msg.to_json()
        restored = CronDiffMessage.from_json(json_str, None)
        self.assertEqual(msg.cron_expression, restored.cron_expression)
        self.assertEqual(msg.command, restored.command)
        self.assertEqual(msg.result, restored.result)


class TestFormatResult(unittest.TestCase):

    def test_format(self):
        result = _format_result("hello out", 0)
        self.assertIn("hello out", result)
        self.assertIn("returncode", result)
        self.assertIn("0", result)

    def test_format_empty(self):
        result = _format_result("", 1)
        self.assertIn("1", result)


class TestParseCronArg(unittest.TestCase):

    def test_valid(self):
        cron_expr, command = parse_cron_arg("* * * * * curl http://example.com/feed")
        self.assertEqual(cron_expr, "* * * * *")
        self.assertEqual(command, "curl http://example.com/feed")

    def test_valid_complex_command(self):
        cron_expr, command = parse_cron_arg(
            "0 */2 * * * curl -s https://example.com/api/data"
        )
        self.assertEqual(cron_expr, "0 */2 * * *")
        self.assertEqual(command, "curl -s https://example.com/api/data")

    def test_invalid_too_few_parts(self):
        with self.assertRaises(ValueError):
            parse_cron_arg("* * * curl http://example.com")

    def test_invalid_no_command(self):
        with self.assertRaises(ValueError):
            parse_cron_arg("* * * * *")


class TestCronPlugin(unittest.TestCase):

    def setUp(self):
        self.registry = Mock()
        self.task_supervisor = Mock(spec=PlainTaskSupervisor)
        self.state_machine = Mock()
        self.state_machine.interrupt_to_working = Mock()
        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.temp_dir = tempfile.mkdtemp()
        self.conversation_folder = Path(self.temp_dir)
        (self.conversation_folder / "cron").mkdir(exist_ok=True)

        def get_member_typechecked_side_effect(name, cls):
            if name == "task_supervisor":
                return self.task_supervisor
            if name == "state_machine":
                return self.state_machine
            if name == "agent":
                return self.agent
            if name == "conversation_folder":
                return self.conversation_folder
            return None

        self.registry.get_member_typechecked = Mock(
            side_effect=get_member_typechecked_side_effect
        )

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")
        self.assertEqual(plugin.cron_expression, "* * * * *")
        self.assertEqual(plugin.command, "echo hello")
        self.assertIsNone(plugin._read_last_result())

    def test_register(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")
        mock_lifecycle = Mock()
        plugin.register(mock_lifecycle)
        mock_lifecycle.before_agent_loop.register.assert_called_once_with(
            plugin.before_agent_loop
        )

    def test_before_agent_loop(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")
        mock_agent = Mock()
        asyncio.run(plugin.before_agent_loop(mock_agent))
        self.task_supervisor.create_supervised_task.assert_called_once()

    def test_run_command_with_timeout_success(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")
        stdout, returncode = asyncio.run(plugin._run_command_with_timeout(10))
        self.assertIn("hello", stdout)
        self.assertEqual(returncode, 0)

    def test_run_command_with_timeout_timeout(self):
        plugin = CronPlugin(self.registry, "* * * * *", "sleep 60")
        stdout, returncode = asyncio.run(plugin._run_command_with_timeout(0.5))
        self.assertEqual(returncode, -9)

    def test_save_and_read_result(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")
        self.assertIsNone(plugin._read_last_result())
        plugin._save_result("test content")
        self.assertEqual(plugin._read_last_result(), "test content")

    def test_run_loop_sends_diff_on_change(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")
        plugin._save_result("old result")

        with patch.object(plugin, "_run_command_with_timeout") as mock_run:
            mock_run.return_value = ("new stdout", 0)

            async def run_one_iteration():
                from linhai.cron import _format_result
                import difflib

                from unittest.mock import patch as async_patch

                with async_patch("linhai.cron.croniter") as mock_croniter:
                    from datetime import datetime, timedelta

                    mock_cron = Mock()
                    mock_cron.get_next.side_effect = [
                        datetime.now() - timedelta(seconds=1),
                        datetime.now() + timedelta(hours=1),
                    ]
                    mock_croniter.return_value = mock_cron

                    stdout, returncode = await plugin._run_command_with_timeout(
                        timeout=3600
                    )
                    current_result = _format_result(stdout, returncode)
                    last_result = plugin._read_last_result()
                    if last_result is not None and current_result != last_result:
                        diff_lines = list(
                            difflib.unified_diff(
                                last_result.splitlines(keepends=True),
                                current_result.splitlines(keepends=True),
                                fromfile="previous",
                                tofile="current",
                            )
                        )
                        diff_text = "".join(diff_lines)
                        msg = CronDiffMessage(
                            cron_expression=plugin.cron_expression,
                            command=plugin.command,
                            result=diff_text,
                        )
                        await self.agent.message_processor.add_new_message(msg)
                        self.state_machine.interrupt_to_working()
                    plugin._save_result(current_result)

            asyncio.run(run_one_iteration())
            self.agent.message_processor.add_new_message.assert_called_once()
            call_args = self.agent.message_processor.add_new_message.call_args[0][0]
            self.assertIn("new stdout", call_args.result)
            self.assertIn("-old result", call_args.result)
            self.state_machine.interrupt_to_working.assert_called_once()

    def test_run_loop_no_diff_no_message(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")

        from linhai.cron import _format_result

        plugin._save_result(_format_result("hello\n", 0))

        with patch.object(plugin, "_run_command_with_timeout") as mock_run:
            mock_run.return_value = ("hello\n", 0)

            async def run_check():
                stdout, returncode = await plugin._run_command_with_timeout(
                    timeout=3600
                )
                current_result = _format_result(stdout, returncode)
                last_result = plugin._read_last_result()
                if last_result is not None and current_result != last_result:
                    self.agent.message_processor.add_new_message(Mock())
                plugin._save_result(current_result)

            asyncio.run(run_check())
            self.agent.message_processor.add_new_message.assert_not_called()

    def test_first_run_no_message(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")

        with patch.object(plugin, "_run_command_with_timeout") as mock_run:
            mock_run.return_value = ("hello", 0)

            async def run_check():
                from linhai.cron import _format_result

                stdout, returncode = await plugin._run_command_with_timeout(
                    timeout=3600
                )
                current_result = _format_result(stdout, returncode)
                last_result = plugin._read_last_result()
                if last_result is not None and current_result != last_result:
                    self.agent.message_processor.add_new_message(Mock())
                plugin._save_result(current_result)

            asyncio.run(run_check())
            self.agent.message_processor.add_new_message.assert_not_called()
            self.assertEqual(plugin._read_last_result(), _format_result("hello", 0))


if __name__ == "__main__":
    unittest.main()
