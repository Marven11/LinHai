"""Agent module for LinHai."""

from .agent import Agent
from .agent_lifecycle import Lifecycle
from .agent import Agent, create_agent, AgentConfig
from .agent_workflow import compress_history_range

__all__ = [
    "Agent",
    "Lifecycle",
    "create_agent",
    "AgentConfig",
    "compress_history_range",
]
