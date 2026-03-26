"""Telegram bot插件，监听Agent消息并通过telegram发送，接收telegram用户消息。"""

from typing import TYPE_CHECKING
import asyncio
from collections import deque

if TYPE_CHECKING:
    from linhai.agent import Agent as AgentType
    from linhai.config import TelegramConfig

from linhai.agent.lifecycle import Lifecycle
from linhai.group_chat import GroupChat
from linhai.plugin.message_checkers import Plugin
from linhai.telegram import TelegramMessage
from linhai.utils import CliRuntimeNotice


class TelegramPlugin(Plugin):
    """Telegram bot插件，实现通过telegram远程控制Agent。"""

    def __init__(self, group_chat: GroupChat, telegram_config: "TelegramConfig"):
        super().__init__(group_chat)
        self.config = telegram_config
        self._bot = None
        self._application = None
        self._running = False
        self.send_queue = deque()
        self._send_task = None
        self._send_delay = 5.0

    async def after_segment_finished(self, _parsed_answer, segment):
        """在segment完成后将消息加入发送队列。"""
        if segment["segment_type"] != "normal":
            return

        content = segment["content"].strip()
        if not content:
            return

        self.send_queue.append(content)

    async def _send_loop(self):
        """发送循环，从队列中获取消息并发送。"""
        while self._running:
            if not self.send_queue:
                await asyncio.sleep(0.1)
                continue

            content = self.send_queue.popleft()

            if self._bot is None:
                self.send_queue.appendleft(content)
                await asyncio.sleep(self._send_delay)
                self._send_delay *= 1.5
                continue

            result = await asyncio.gather(
                self._bot.send_message(
                    chat_id=self.config.default_chat_id,
                    text=content,
                ),
                return_exceptions=True,
            )

            if result[0] is not None:
                self.send_queue.appendleft(content)
                await asyncio.sleep(self._send_delay)
                self._send_delay *= 1.5
            else:
                self._send_delay = 5.0

    async def _handle_telegram_message(self, update, _context):
        """处理来自telegram的消息。"""
        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content="收到Telegram消息",
            ),
        )
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
            if agent.state == "waiting_user":
                agent.state = "working"

    async def before_agent_loop(self, _agent: "AgentType"):
        """在Agent循环开始前启动telegram bot和发送任务。"""
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
        assert self._application.updater is not None
        await self._application.updater.start_polling()
        self._bot = self._application.bot

        self._send_task = asyncio.create_task(self._send_loop())
        self._running = True

    async def shutdown(self):
        """关闭telegram bot和发送任务。"""
        if self._application and self._running:
            self._running = False
            if self._send_task:
                self._send_task.cancel()
            await self._application.stop()
            await self._application.shutdown()

    def register(self, lifecycle: "Lifecycle") -> None:
        """注册到Lifecycle。"""
        lifecycle.register_after_segment_finished(self.after_segment_finished)
        lifecycle.register_before_agent_loop(self.before_agent_loop)
