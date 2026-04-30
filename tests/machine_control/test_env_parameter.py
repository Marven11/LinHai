import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.machine_control.bash_host.bash_host import BashHostControl
from linhai.machine_control.master_host.master_host import MasterHostControl
from linhai.machine_control.posix_shell.posix_shell_control import PosixShellControl
from linhai.machine_control.trojan.trojan import Trojan
from linhai.registry import Registry


def _create_host_control() -> MasterHostControl:
    from linhai.sandbox import NoSandbox

    registry = Registry()
    registry.register_member("process_sandbox", NoSandbox())
    return MasterHostControl(registry)


class TestMasterHostEnvParameter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.host_control = _create_host_control()

    def tearDown(self):
        self.host_control._processes.clear()

    async def test_create_process_passes_env(self):
        with patch("asyncio.create_subprocess_exec") as mock_create:
            mock_process = AsyncMock()
            mock_process.pid = 77777
            mock_process.returncode = 0
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_create.return_value = mock_process

            env = {"FOO": "bar", "BAZ": "qux"}
            await self.host_control.create_process(["env"], env=env)
            mock_create.assert_called_once()
            self.assertEqual(mock_create.call_args.kwargs.get("env"), env)

    async def test_create_process_env_none(self):
        with patch("asyncio.create_subprocess_exec") as mock_create:
            mock_process = AsyncMock()
            mock_process.pid = 77778
            mock_process.returncode = 0
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_create.return_value = mock_process

            await self.host_control.create_process(["env"])
            mock_create.assert_called_once()
            self.assertIsNone(mock_create.call_args.kwargs.get("env"))


class TestBashHostEnvParameter(unittest.TestCase):
    def setUp(self):
        import asyncio

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.registry = MagicMock(spec=Registry)
        self.registry.send_if_exists = AsyncMock()
        self.registry.members = {}
        self.control = BashHostControl(registry=self.registry)

    def tearDown(self):
        self.loop.close()

    def test_create_process_with_env(self):
        async def test():
            self.control.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, "42", ""),
                    (0, "NONE", ""),
                ]
            )
            self.control._tmp_dir = "/tmp/test"
            result = await self.control.create_process(
                ["echo", "hello"], env={"MY_VAR": "my_val"}, wait_second=0.0
            )
            self.assertTrue(result.success)
            start_cmd_call = self.control.execute_raw.call_args_list[1]
            cmd = start_cmd_call[0][0]
            self.assertIn("MY_VAR", cmd)
            self.assertIn("my_val", cmd)

        self.loop.run_until_complete(test())

    def test_create_process_without_env(self):
        async def test():
            self.control.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, "42", ""),
                ]
            )
            self.control._tmp_dir = "/tmp/test"
            result = await self.control.create_process(
                ["echo", "hello"], wait_second=0.0
            )
            self.assertTrue(result.success)
            start_cmd_call = self.control.execute_raw.call_args_list[1]
            cmd = start_cmd_call[0][0]
            self.assertNotIn("=", cmd.split("echo")[0])

        self.loop.run_until_complete(test())


class TestPosixShellEnvParameter(unittest.IsolatedAsyncioTestCase):
    async def test_create_process_passes_env(self):
        control = MagicMock(spec=PosixShellControl)
        control.create_process = PosixShellControl.create_process.__get__(control)
        control.call_tool = AsyncMock(
            return_value=MagicMock(
                content='{"pid": "123", "message": "running"}',
            )
        )
        control._processes = {}
        control.registry = MagicMock(spec=Registry)
        control.registry.members = {}
        env = {"KEY": "VALUE"}
        await control.create_process(["env"], env=env)
        call_args = control.call_tool.call_args
        self.assertEqual(call_args[0][1]["env"], env)

    async def test_create_process_no_env(self):
        control = MagicMock(spec=PosixShellControl)
        control.create_process = PosixShellControl.create_process.__get__(control)
        control.call_tool = AsyncMock(
            return_value=MagicMock(
                content='{"pid": "124", "message": "running"}',
            )
        )
        control._processes = {}
        control.registry = MagicMock(spec=Registry)
        control.registry.members = {}
        await control.create_process(["env"])
        call_args = control.call_tool.call_args
        self.assertNotIn("env", call_args[0][1])


class TestTrojanEnvParameter(unittest.IsolatedAsyncioTestCase):
    async def test_create_process_passes_env(self):
        trojan = Trojan(marker_bytes=b"<linhai_pulse_aabb>")
        with patch("asyncio.create_subprocess_exec") as mock_create:
            mock_process = AsyncMock()
            mock_process.pid = 88888
            mock_process.returncode = 0
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_create.return_value = mock_process

            env = {"MY_KEY": "MY_VAL"}
            await trojan.process_create(["env"], env=env)
            mock_create.assert_called_once()
            self.assertEqual(mock_create.call_args.kwargs.get("env"), env)

    async def test_create_process_env_none(self):
        trojan = Trojan(marker_bytes=b"<linhai_pulse_aabb>")
        with patch("asyncio.create_subprocess_exec") as mock_create:
            mock_process = AsyncMock()
            mock_process.pid = 88889
            mock_process.returncode = 0
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_create.return_value = mock_process

            await trojan.process_create(["env"])
            mock_create.assert_called_once()
            self.assertIsNone(mock_create.call_args.kwargs.get("env"))


if __name__ == "__main__":
    unittest.main()
