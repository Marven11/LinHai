import argparse

from typing import TYPE_CHECKING
from linhai.agent.base import RuntimeMessage
from linhai.utils import CliRuntimeNotice
from .message_checkers import Plugin

if TYPE_CHECKING:
    from linhai.agent import Agent
    from linhai.agent.lifecycle import Lifecycle


class AfkPlugin(Plugin):
    async def before_waiting_user(self, agent: "Agent"):
        cli_args = self.registry.get_member_typechecked("cli_args", argparse.Namespace)
        if not cli_args.afk:
            return

        agent.state = "working"

        await agent.message_processor.add_new_message(
            RuntimeMessage(
                f"当前等待用户的功能已经失效，因为用户使用了--afk参数。"
                f"这说明用户禁止你等待用户输入并离开了电脑"
            )
        )

        await self.registry.send_if_exists(
            "ui_log",
            CliRuntimeNotice(level="INFO", content="AFK模式激活，已阻止等待用户功能"),
        )

    def register(self, lifecycle: "Lifecycle") -> None:
        lifecycle.register_before_waiting_user(self.before_waiting_user)
