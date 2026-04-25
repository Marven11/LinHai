import os
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProcessSandboxProtocol(Protocol):
    def wrap_argv(self, argv: list[str]) -> list[str]: ...

    def update_pwd(self, new_pwd: str) -> None: ...


class NoSandbox:
    def wrap_argv(self, argv: list[str]) -> list[str]:
        return list(argv)

    def update_pwd(self, new_pwd: str) -> None:
        pass

    def serialize(self) -> dict:
        return {}

    def restore_from(self, data: dict) -> None:
        pass


DEFAULT_MACOS_PROFILE_TEMPLATE = """
(version 1)

;; files

(deny file-write*)

(allow file-write* (subpath "{pwd}"))
(allow file-write* (subpath "{home}/.cache"))
(allow file-write* (subpath "{home}/.local/share/linhai"))
(allow file-write* (subpath "{tmpdir}"))
(allow file-write* (subpath "/private/tmp"))
(allow file-write* (subpath "/tmp"))

(allow file-read*)

;; process

(allow process-fork)
(allow process-exec)

;; network

(allow network-outbound)

;; terminal support

(allow pseudo-tty)
(allow signal)
(allow file-ioctl (literal "/dev/ptmx"))

;; others

(allow sysctl-read)

(allow file-read* (subpath "/dev"))
(allow file-write* (subpath "/dev"))

(allow mach-lookup)
"""


class MacOsSandbox:
    def __init__(self, sandbox_profile: Path | str) -> None:
        self._template = Path(sandbox_profile).read_text()
        self._home = str(Path.home())
        self._tmpdir = tempfile.gettempdir()
        self._pwd = os.getcwd()
        self._profile_path = self._render_profile(self._pwd)

    def _render_profile(self, pwd: str) -> str:
        rendered = self._template.format(
            pwd=pwd,
            home=self._home,
            tmpdir=self._tmpdir,
        )
        profile_file = tempfile.NamedTemporaryFile(mode="w", suffix=".sb", delete=False)
        profile_file.write(rendered)
        profile_file.close()
        return profile_file.name

    def wrap_argv(self, argv: list[str]) -> list[str]:
        return ["sandbox-exec", "-f", self._profile_path] + list(argv)

    def update_pwd(self, new_pwd: str) -> None:
        self._pwd = new_pwd
        self._profile_path = self._render_profile(new_pwd)

    def serialize(self) -> dict:
        return {"pwd": self._pwd}

    def restore_from(self, data: dict) -> None:
        pwd = data.get("pwd")
        if pwd is not None:
            self.update_pwd(pwd)


class BubbleWrapSandbox:
    def __init__(self, argv_template: list[str]) -> None:
        self._argv_template = list(argv_template)
        self._home = str(Path.home())
        self._tmpdir = tempfile.gettempdir()
        self._pwd = os.getcwd()

    def _render(self) -> list[str]:
        return [
            s.format(pwd=self._pwd, home=self._home, tmpdir=self._tmpdir)
            for s in self._argv_template
        ]

    def wrap_argv(self, argv: list[str]) -> list[str]:
        return self._render() + list(argv)

    def update_pwd(self, new_pwd: str) -> None:
        self._pwd = new_pwd

    def serialize(self) -> dict:
        return {"pwd": self._pwd}

    def restore_from(self, data: dict) -> None:
        pwd = data.get("pwd")
        if pwd is not None:
            self.update_pwd(pwd)
