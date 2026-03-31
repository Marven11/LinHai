import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from linhai.sandbox import (
    DEFAULT_MACOS_PROFILE_TEMPLATE,
    BubbleWrapSandbox,
    MacOsSandbox,
    NoSandbox,
    ProcessSandboxProtocol,
)


class TestProcessSandboxProtocol(unittest.TestCase):
    def test_no_sandbox_satisfies_protocol(self):
        def accept_sandbox(sandbox: ProcessSandboxProtocol) -> None:
            pass

        accept_sandbox(NoSandbox())

    def test_macos_sandbox_satisfies_protocol(self):
        def accept_sandbox(sandbox: ProcessSandboxProtocol) -> None:
            pass

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sb", delete=False) as f:
            f.write(DEFAULT_MACOS_PROFILE_TEMPLATE)
            profile_path = f.name
        try:
            with patch.object(Path, "home", return_value=Path("/home/test")):
                accept_sandbox(MacOsSandbox(profile_path))
        finally:
            os.unlink(profile_path)

    def test_bubblewrap_sandbox_satisfies_protocol(self):
        def accept_sandbox(sandbox: ProcessSandboxProtocol) -> None:
            pass

        accept_sandbox(BubbleWrapSandbox(["bwrap"]))


class TestNoSandbox(unittest.TestCase):
    def test_returns_same_argv(self):
        sandbox = NoSandbox()
        argv = ["python", "-c", "print(1)"]
        result = sandbox.wrap_argv(argv)
        self.assertEqual(result, ["python", "-c", "print(1)"])

    def test_returns_copy(self):
        sandbox = NoSandbox()
        argv = ["python"]
        result = sandbox.wrap_argv(argv)
        self.assertEqual(result, argv)
        self.assertIsNot(result, argv)

    def test_empty_argv(self):
        sandbox = NoSandbox()
        self.assertEqual(sandbox.wrap_argv([]), [])


def _create_profile_file() -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".sb", delete=False)
    f.write(DEFAULT_MACOS_PROFILE_TEMPLATE)
    f.close()
    return f.name


class TestMacOsSandbox(unittest.TestCase):
    @patch.object(Path, "home", return_value=Path("/home/testuser"))
    def test_renders_template_and_saves_to_tempfile(self, mock_home):
        with patch("os.getcwd", return_value="/workdir"):
            profile_path = _create_profile_file()
            try:
                sandbox = MacOsSandbox(profile_path)
            finally:
                os.unlink(profile_path)

        rendered_path = sandbox._profile_path
        self.assertTrue(os.path.exists(rendered_path))
        with open(rendered_path) as f:
            content = f.read()
        self.assertIn("/workdir", content)
        self.assertIn("/home/testuser/.cache", content)
        self.assertIn("/home/testuser/.local/share/linhai", content)
        os.unlink(rendered_path)

    @patch.object(Path, "home", return_value=Path("/home/testuser"))
    def test_wrap_argv_prepends_sandbox_exec(self, mock_home):
        with patch("os.getcwd", return_value="/workdir"):
            profile_path = _create_profile_file()
            try:
                sandbox = MacOsSandbox(profile_path)
            finally:
                os.unlink(profile_path)
        result = sandbox.wrap_argv(["python", "-c", "print(1)"])
        self.assertEqual(result[0], "sandbox-exec")
        self.assertEqual(result[1], "-f")
        self.assertEqual(result[2], sandbox._profile_path)
        self.assertEqual(result[3:], ["python", "-c", "print(1)"])
        os.unlink(sandbox._profile_path)

    @patch.object(Path, "home", return_value=Path("/home/testuser"))
    def test_profile_contains_required_sections(self, mock_home):
        with patch("os.getcwd", return_value="/workdir"):
            profile_path = _create_profile_file()
            try:
                sandbox = MacOsSandbox(profile_path)
            finally:
                os.unlink(profile_path)
        with open(sandbox._profile_path) as f:
            content = f.read()
        self.assertIn("(deny file-write*)", content)
        self.assertIn("(allow file-read*)", content)
        self.assertIn("(allow process-fork)", content)
        self.assertIn("(allow process-exec)", content)
        os.unlink(sandbox._profile_path)

    @patch.object(Path, "home", return_value=Path("/home/testuser"))
    def test_uses_passed_profile_content(self, mock_home):
        custom_template = (
            '(version 1)\n(deny default)\n(allow file-read* (subpath "{pwd}"))\n'
        )
        with patch("os.getcwd", return_value="/custom/workdir"):
            f = tempfile.NamedTemporaryFile(mode="w", suffix=".sb", delete=False)
            f.write(custom_template)
            f.close()
            try:
                sandbox = MacOsSandbox(f.name)
            finally:
                os.unlink(f.name)
        with open(sandbox._profile_path) as f:
            content = f.read()
        self.assertIn("/custom/workdir", content)
        self.assertNotIn("{pwd}", content)
        self.assertIn("(deny default)", content)
        os.unlink(sandbox._profile_path)


class TestBubbleWrapSandbox(unittest.TestCase):
    def test_merge_argv(self):
        sandbox = BubbleWrapSandbox(["bwrap", "--ro-bind", "/", "/"])
        result = sandbox.wrap_argv(["python", "-c", "print(1)"])
        self.assertEqual(
            result, ["bwrap", "--ro-bind", "/", "/", "python", "-c", "print(1)"]
        )

    def test_empty_bubblewrap_argv(self):
        sandbox = BubbleWrapSandbox([])
        result = sandbox.wrap_argv(["python", "-c", "print(1)"])
        self.assertEqual(result, ["python", "-c", "print(1)"])

    def test_bubblewrap_real_execution(self):
        result = subprocess.run(["which", "bwrap"], capture_output=True)
        if result.returncode != 0:
            self.skipTest("bubblewrap (bwrap) not installed")

        sandbox = BubbleWrapSandbox(
            [
                "bwrap",
                "--ro-bind",
                "/",
                "/",
                "--dev",
                "/dev",
                "--proc",
                "/proc",
                "--unshare-all",
            ]
        )
        wrapped = sandbox.wrap_argv(["python", "-c", "print(1145141919810)"])
        result = subprocess.run(wrapped, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("1145141919810", result.stdout)


class TestRegisterSandbox(unittest.TestCase):
    def test_register_none_creates_no_sandbox(self):
        from linhai.agent.create import _register_sandbox
        from linhai.registry import Registry

        registry = Registry()
        _register_sandbox(registry, None)
        sandbox = registry.get_member_typechecked("process_sandbox", NoSandbox)
        self.assertIsInstance(sandbox, NoSandbox)

    @patch.object(Path, "home", return_value=Path("/home/testuser"))
    def test_register_macos_creates_profile_if_not_exists(self, mock_home):
        from linhai.agent.create import _register_sandbox
        from linhai.config import MacOsSandboxConfig
        from linhai.registry import Registry

        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = os.path.join(tmpdir, "sandbox.sb")
            self.assertFalse(os.path.exists(profile_path))

            with patch("os.getcwd", return_value="/workdir"):
                registry = Registry()
                config = MacOsSandboxConfig(sandbox_profile=profile_path)
                _register_sandbox(registry, config)

            self.assertTrue(os.path.exists(profile_path))
            with open(profile_path) as f:
                content = f.read()
            self.assertEqual(content, DEFAULT_MACOS_PROFILE_TEMPLATE)

            sandbox = registry.get_member_typechecked("process_sandbox", MacOsSandbox)
            self.assertIsInstance(sandbox, MacOsSandbox)
            os.unlink(sandbox._profile_path)

    @patch.object(Path, "home", return_value=Path("/home/testuser"))
    def test_register_macos_uses_existing_profile(self, mock_home):
        from linhai.agent.create import _register_sandbox
        from linhai.config import MacOsSandboxConfig
        from linhai.registry import Registry

        custom_template = "(version 1)\n(deny default)\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sb", delete=False) as f:
            f.write(custom_template)
            profile_path = f.name

        try:
            with patch("os.getcwd", return_value="/workdir"):
                registry = Registry()
                config = MacOsSandboxConfig(sandbox_profile=profile_path)
                _register_sandbox(registry, config)

            sandbox = registry.get_member_typechecked("process_sandbox", MacOsSandbox)
            self.assertIsInstance(sandbox, MacOsSandbox)
            with open(sandbox._profile_path) as f:
                content = f.read()
            self.assertIn("(deny default)", content)
            os.unlink(sandbox._profile_path)
        finally:
            os.unlink(profile_path)

    def test_register_bubblewrap_creates_bubblewrap_sandbox(self):
        from linhai.agent.create import _register_sandbox
        from linhai.config import BubblewrapConfig
        from linhai.registry import Registry

        registry = Registry()
        config = BubblewrapConfig(argv=["bwrap"])
        _register_sandbox(registry, config)
        sandbox = registry.get_member_typechecked("process_sandbox", BubbleWrapSandbox)
        self.assertIsInstance(sandbox, BubbleWrapSandbox)


if __name__ == "__main__":
    unittest.main()
