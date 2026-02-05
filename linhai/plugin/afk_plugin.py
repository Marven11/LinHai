import argparse

from typing import TYPE_CHECKING
from linhai.agent.base import WAITING_USER_MARKER, RuntimeMessage
from linhai.utils import CliRuntimeNotice
from .message_checkers import Plugin

if TYPE_CHECKING:
    from linhai.agent import Agent
    from linhai.agent.lifecycle import Lifecycle


class AfkPlugin(Plugin):
    async def after_message_generation(self, _answer, full_response, tool_calls):
        cli_args = self.group_chat.get_members("cli_args", argparse.Namespace)
        if not cli_args.afk:
            return

        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        if WAITING_USER_MARKER in full_response:
            agent.state = "working"

            agent.message_processor.add_new_message(
                RuntimeMessage(
                    f"当前{WAITING_USER_MARKER!r}的功能已经失效，因为用户使用了--afk参数。"
                    f"这说明用户禁止你等待用户输入并离开了电脑"
                )
            )

            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO", content="AFK模式激活，已阻止等待用户功能"
                ),
            )

    def register(self, lifecycle: "Lifecycle") -> None:
        lifecycle.register_after_message_generation(self.after_message_generation)
