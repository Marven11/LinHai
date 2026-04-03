import os
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProcessSandboxProtocol(Protocol):
    def wrap_argv(self, argv: list[str]) -> list[str]: ...


class NoSandbox:
    def wrap_argv(self, argv: list[str]) -> list[str]:
        return list(argv)


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
        template = Path(sandbox_profile).read_text()
        rendered = template.format(
            pwd=os.getcwd(),
            home=str(Path.home()),
            tmpdir=tempfile.gettempdir(),
        )
        self._profile_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".sb", delete=False
        )
        self._profile_file.write(rendered)
        self._profile_file.close()
        self._profile_path = self._profile_file.name

    def wrap_argv(self, argv: list[str]) -> list[str]:
        return ["sandbox-exec", "-f", self._profile_path] + list(argv)


class BubbleWrapSandbox:
    def __init__(self, bubblewrap_argv: list[str]) -> None:
        self._bubblewrap_argv = list(bubblewrap_argv)

    def wrap_argv(self, argv: list[str]) -> list[str]:
        return self._bubblewrap_argv + list(argv)
