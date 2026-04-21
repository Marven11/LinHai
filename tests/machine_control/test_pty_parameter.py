import unittest
from unittest.mock import AsyncMock, MagicMock

from linhai.machine_control.posix_shell.posix_shell_control import PosixShellControl


class TestPtyParameter(unittest.IsolatedAsyncioTestCase):
    async def test_posix_shell_pty_raises(self):
        control = MagicMock(spec=PosixShellControl)
        control.create_process = PosixShellControl.create_process.__get__(control)
        control.call_tool = AsyncMock()
        control._cwd = "/tmp"
        with self.assertRaises(RuntimeError) as ctx:
            await control.create_process(["echo", "test"], pty=True)
        self.assertIn("PosixShell", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
