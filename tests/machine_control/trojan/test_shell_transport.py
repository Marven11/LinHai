import unittest
import asyncio
import shutil
from unittest.mock import AsyncMock, Mock, patch

from linhai.machine_control.trojan.shell_transport import (
    setup_trojan_in_shell,
    _execute_in_shell,
    _split_marker_for_echo,
)
from linhai.machine_control.process import (
    ProcessReadResult,
    ProcessWriteResult,
)
from linhai.registry import Registry


class TestExecuteInShell(unittest.TestCase):

    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.send_if_exists_mock = AsyncMock()
        self.registry.send_if_exists = self.send_if_exists_mock

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def _make_mock_process(self, read_responses):
        mock_process = AsyncMock()
        mock_process.pid = "1"
        mock_process.stdio_write = AsyncMock(
            return_value=ProcessWriteResult(pid="1", success=True, message="ok")
        )
        responses = iter(read_responses)
        default = ProcessReadResult(pid="1", success=True, stdout=b"", stderr=b"")

        async def read_side_effect(wait_seconds):
            return next(responses, default)

        mock_process.stdio_read = AsyncMock(side_effect=read_side_effect)
        return mock_process

    @unittest.skipIf(shutil.which("bash") is None, "no bash")
    def test_command_timeout(self):
        async def test():
            empty_read = ProcessReadResult(
                pid="1", success=True, stdout=b"", stderr=b""
            )
            mock_process = self._make_mock_process([empty_read, empty_read])

            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop_instance = Mock()
                time_values = iter([0, 0, 0.3, 0.6])
                mock_loop_instance.time = Mock(side_effect=lambda: next(time_values))
                mock_loop.return_value = mock_loop_instance

                exit_code, output, error = await _execute_in_shell(
                    mock_process, "test command", timeout=0.5
                )

                self.assertEqual(exit_code, 1)
                self.assertEqual(error, "命令执行超时")

        self.loop.run_until_complete(test())


class TestSetupTrojanInShell(unittest.TestCase):

    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.send_if_exists_mock = AsyncMock()
        self.registry.send_if_exists = self.send_if_exists_mock

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def _make_mock_process(self, read_responses):
        mock_process = AsyncMock()
        mock_process.pid = "1"
        mock_process.stdio_write = AsyncMock(
            return_value=ProcessWriteResult(pid="1", success=True, message="ok")
        )
        responses = iter(read_responses)
        default = ProcessReadResult(pid="1", success=True, stdout=b"", stderr=b"")

        async def read_side_effect(wait_seconds):
            return next(responses, default)

        mock_process.stdio_read = AsyncMock(side_effect=read_side_effect)
        return mock_process

    @unittest.skipIf(shutil.which("bash") is None, "no bash")
    def test_setup_success(self):
        async def test():
            marker_open = "<linhai_cmd_aaaa>"
            marker_close = "</linhai_cmd_aaaa>"
            read_responses = [
                ProcessReadResult(
                    pid="1",
                    success=True,
                    stdout=(
                        f"echo '{marker_open}'; python3 -V 2>&1; RC=$?; echo \"${{RC}}{marker_close}\"\n"
                        f"{marker_open}\nPython 3.14.2\n0{marker_close}\n"
                    ).encode(),
                    stderr=b"",
                ),
                ProcessReadResult(
                    pid="1",
                    success=True,
                    stdout=(
                        f"{marker_open}\n/tmp/trojan.py\n0{marker_close}\n"
                    ).encode(),
                    stderr=b"",
                ),
            ]
            mock_process = self._make_mock_process(read_responses)

            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.read_text", return_value="# trojan content"),
                patch(
                    "linhai.machine_control.trojan.shell_transport.uuid.uuid4"
                ) as mock_uuid,
            ):
                mock_uuid.return_value.hex = "aaaa"
                result = await setup_trojan_in_shell(mock_process, self.registry)
                self.assertIsNotNone(result)
                self.assertIsInstance(result, tuple)
                self.assertEqual(len(result), 2)
                self.assertTrue(self.send_if_exists_mock.called)

        self.loop.run_until_complete(test())

    @unittest.skipIf(shutil.which("bash") is None, "no bash")
    def test_python_version_check_failure(self):
        async def test():
            marker_open = "<linhai_cmd_aaaa>"
            marker_close = "</linhai_cmd_aaaa>"
            read_responses = [
                ProcessReadResult(
                    pid="1",
                    success=True,
                    stdout=(
                        f"{marker_open}\nPython 2.7.18\n0{marker_close}\n"
                    ).encode(),
                    stderr=b"",
                ),
            ]
            mock_process = self._make_mock_process(read_responses)

            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.read_text", return_value="# trojan content"),
                patch(
                    "linhai.machine_control.trojan.shell_transport.uuid.uuid4"
                ) as mock_uuid,
            ):
                mock_uuid.return_value.hex = "aaaa"
                result = await setup_trojan_in_shell(mock_process, self.registry)
                self.assertIsNone(result)

        self.loop.run_until_complete(test())


class TestSplitMarkerForEcho(unittest.TestCase):

    def test_split_marker_command_does_not_contain_full_marker(self):
        marker = "<linhai_cmd_a1b2>"
        result = _split_marker_for_echo(marker)
        self.assertNotIn(marker, result)

    def test_split_marker_output_is_correct(self):
        marker = "<linhai_cmd_a1b2>"
        result = _split_marker_for_echo(marker)
        self.assertIn('""', result)
        halves = result.split('""')
        self.assertEqual("".join(halves), marker)

    def test_split_marker_close_tag(self):
        marker = "</linhai_cmd_a1b2>"
        result = _split_marker_for_echo(marker)
        self.assertNotIn(marker, result)
        self.assertEqual("".join(result.split('""')), marker)


if __name__ == "__main__":
    unittest.main()
