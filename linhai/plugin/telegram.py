"""Telegram bot插件，监听Agent消息并通过telegram发送，接收telegram用户消息。"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from linhai.agent import Agent as AgentType
    from linhai.config import TelegramConfig

from linhai.agent.lifecycle import Lifecycle
from linhai.group_chat import GroupChat
from linhai.plugin.message_checkers import Plugin
from linhai.telegram import TelegramMessage


class TelegramPlugin(Plugin):
    """Telegram bot插件，实现通过telegram远程控制Agent。"""

    def __init__(self, group_chat: GroupChat, telegram_config: "TelegramConfig"):
        super().__init__(group_chat)
        self.config = telegram_config
        self._bot = None
        self._application = None
        self._running = False

    async def after_segment_finished(self, _parsed_answer, segment):
        """在segment完成后发送消息到telegram。"""
        if segment["segment_type"] != "normal":
            return

        content = segment["content"].strip()
        if not content:
            return

        await self._send_to_telegram(content)

    async def _send_to_telegram(self, content: str):
        """发送消息到telegram。"""
        if self._bot is None:
            from telegram import Bot

            self._bot = Bot(token=self.config.bot_token)

        await self._bot.send_message(
            chat_id=self.config.default_chat_id,
            text=content,
        )

    async def _handle_telegram_message(self, update, _context):
        """处理来自telegram的消息。"""
        from linhai.agent import Agent as AgentType

        if not update.message:
            return

        chat_id = str(update.message.chat_id)
        if chat_id != self.config.default_chat_id:
            return

        content = update.message.text
        if not content:
            return

        agent = self.group_chat.get_member_typechecked("agent", AgentType)
        if agent:
            message = TelegramMessage(
                chat_id=chat_id,
                content=content,
                message_id=update.message.message_id,
            )
            await agent.message_processor.add_new_message(message)

    async def before_agent_loop(self, _agent: "AgentType"):
        """在Agent循环开始前启动telegram bot。"""
        from telegram.ext import Application, MessageHandler, filters

        if self._running:
            return

        self._application = Application.builder().token(self.config.bot_token).build()
        self._application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, self._handle_telegram_message
            )
        )

        await self._application.initialize()
        await self._application.start()
        self._running = True

    async def shutdown(self):
        """关闭telegram bot。"""
        if self._application and self._running:
            await self._application.stop()
            await self._application.shutdown()
            self._running = False

    def register(self, lifecycle: "Lifecycle") -> None:
        """注册到Lifecycle。"""
        lifecycle.register_after_segment_finished(self.after_segment_finished)
        lifecycle.register_before_agent_loop(self.before_agent_loop)
