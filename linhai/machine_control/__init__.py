"""Machine control module for managing different host machines."""

from .master_host.master_host import MasterHostControl
from .posix_shell.posix_shell_control import PosixShellControl
from .ether_ghost_host.ether_ghost_host import EtherGhostMachineControl
from .bash_host.bash_host import BashHostControl
from .main import MachineControl

__all__ = [
    "MachineControl",
    "MasterHostControl",
    "PosixShellControl",
    "EtherGhostMachineControl",
    "BashHostControl",
]
