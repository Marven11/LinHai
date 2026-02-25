"""Machine control module for managing different host machines."""

from .master_host.master_host import MasterHostControl
from .ssh_host.ssh_host import SshMachineControl
from .ether_ghost_host.ether_ghost_host import EtherGhostMachineControl
from .main import MachineControl

__all__ = [
    "MachineControl",
    "MasterHostControl",
    "SshMachineControl",
    "EtherGhostMachineControl",
]
