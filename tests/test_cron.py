import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from linhai.cron import CronPlugin, CronDiffMessage, _format_result, parse_cron_arg
from linhai.task_supervisor import PlainTaskSupervisor


class TestCronDiffMessage(unittest.TestCase):

    def test_create(self):
        msg = CronDiffMessage(
            cron_expression="* * * * *",
            command="curl http://example.com/feed",
            result="stdout:\n\nhello\n\nstderr:\n\n\n\npid:\n\n123",
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
        result = _format_result("hello out", "hello err", 42)
        self.assertIn("stdout:", result)
        self.assertIn("hello out", result)
        self.assertIn("stderr:", result)
        self.assertIn("hello err", result)
        self.assertIn("pid:", result)
        self.assertIn("42", result)


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

        def get_member_typechecked_side_effect(name, cls):
            if name == "task_supervisor":
                return self.task_supervisor
            if name == "state_machine":
                return self.state_machine
            if name == "agent":
                return self.agent
            return None

        self.registry.get_member_typechecked = Mock(
            side_effect=get_member_typechecked_side_effect
        )

    def test_initialization(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")
        self.assertEqual(plugin.cron_expression, "* * * * *")
        self.assertEqual(plugin.command, "echo hello")
        self.assertIsNone(plugin._last_result)

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
        stdout, stderr, pid = asyncio.run(plugin._run_command_with_timeout(10))
        self.assertIn("hello", stdout)
        self.assertEqual(stderr, "")
        self.assertIsInstance(pid, int)

    def test_run_command_with_timeout_timeout(self):
        plugin = CronPlugin(self.registry, "* * * * *", "sleep 60")
        stdout, stderr, pid = asyncio.run(plugin._run_command_with_timeout(0.5))
        self.assertIsInstance(pid, int)

    def test_run_loop_sends_diff_on_change(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")
        plugin._last_result = "old result"

        with patch.object(plugin, "_run_command_with_timeout") as mock_run:
            mock_run.return_value = ("new stdout", "new stderr", 123)

            async def run_one_iteration():
                from linhai.cron import _format_result

                from unittest.mock import patch as async_patch

                with async_patch("linhai.cron.croniter") as mock_croniter:
                    from datetime import datetime, timedelta

                    mock_cron = Mock()
                    mock_cron.get_next.side_effect = [
                        datetime.now() - timedelta(seconds=1),
                        datetime.now() + timedelta(hours=1),
                    ]
                    mock_croniter.return_value = mock_cron

                    stdout, stderr, pid = await plugin._run_command_with_timeout(
                        timeout=3600
                    )
                    current_result = _format_result(stdout, stderr, pid)
                    if (
                        plugin._last_result is not None
                        and current_result != plugin._last_result
                    ):
                        msg = CronDiffMessage(
                            cron_expression=plugin.cron_expression,
                            command=plugin.command,
                            result=current_result,
                        )
                        await self.agent.message_processor.add_new_message(msg)
                        self.state_machine.interrupt_to_working()
                    plugin._last_result = current_result

            asyncio.run(run_one_iteration())
            self.agent.message_processor.add_new_message.assert_called_once()
            self.state_machine.interrupt_to_working.assert_called_once()

    def test_run_loop_no_diff_no_message(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")

        from linhai.cron import _format_result

        plugin._last_result = _format_result("hello\n", "", 0)

        with patch.object(plugin, "_run_command_with_timeout") as mock_run:
            mock_run.return_value = ("hello\n", "", 0)

            async def run_check():
                stdout, stderr, pid = await plugin._run_command_with_timeout(
                    timeout=3600
                )
                current_result = _format_result(stdout, stderr, pid)
                if (
                    plugin._last_result is not None
                    and current_result != plugin._last_result
                ):
                    self.agent.message_processor.add_new_message(Mock())
                plugin._last_result = current_result

            asyncio.run(run_check())
            self.agent.message_processor.add_new_message.assert_not_called()

    def test_first_run_no_message(self):
        plugin = CronPlugin(self.registry, "* * * * *", "echo hello")

        with patch.object(plugin, "_run_command_with_timeout") as mock_run:
            mock_run.return_value = ("hello", "", 123)

            async def run_check():
                from linhai.cron import _format_result

                stdout, stderr, pid = await plugin._run_command_with_timeout(
                    timeout=3600
                )
                current_result = _format_result(stdout, stderr, pid)
                if (
                    plugin._last_result is not None
                    and current_result != plugin._last_result
                ):
                    self.agent.message_processor.add_new_message(Mock())
                plugin._last_result = current_result

            asyncio.run(run_check())
            self.agent.message_processor.add_new_message.assert_not_called()
            self.assertIsNotNone(plugin._last_result)


if __name__ == "__main__":
    unittest.main()
