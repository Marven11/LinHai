"""Telegram bot插件，监听Agent消息并通过telegram发送，接收telegram用户消息。"""

from typing import TYPE_CHECKING
import time
import asyncio
from collections import deque
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

if TYPE_CHECKING:
    from linhai.agent import Agent as AgentType
    from linhai.agent.create import TelegramContext

from linhai.parsed_message import Segment
from linhai.agent.messages import WAITING_USER_MARKER
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.state_machine import AgentStateMachine
from linhai.registry import Registry
from linhai.plugin.message_checkers import Plugin
from linhai.telegram import TelegramMessage, load_sticker
from linhai.utils.common import UiNotice

DRAFT_INTERVAL = 1


class TelegramPlugin(Plugin):
    """Telegram bot插件，实现通过telegram远程控制Agent。"""

    def __init__(self, registry: Registry, telegram_config: "TelegramContext"):
        super().__init__(registry)
        self.config = telegram_config
        self._bot = None
        self._application = None
        self._running = False
        self.send_queue: deque[Segment] = deque()

    async def after_segment_finished(self, _parsed_answer, segment: Segment):
        """在segment完成后将消息加入发送队列。"""
        if segment["segment_type"] != "normal" or not segment["content"].strip():
            return

        self.send_queue.append(segment)

    async def _send_loop(self):
        """发送循环，从队列中获取消息并发送。"""
        while self._running:
            if not self.send_queue:
                await asyncio.sleep(0.05)
                continue

            segment = self.send_queue.popleft()
            draft_id = int(time.time() * 1000)
            assert self._bot is not None

            if len(segment["content"]) < 10:
                await asyncio.sleep(DRAFT_INTERVAL)

            while not segment["is_finished"]:
                start_time = time.time()
                result = await asyncio.gather(
                    self._bot.send_message_draft(
                        chat_id=int(self.config["default_chat_id"]),
                        draft_id=draft_id,
                        text=segment["content"],
                    ),
                    return_exceptions=True,
                )
                duration = time.time() - start_time
                if DRAFT_INTERVAL - duration > 0:
                    await asyncio.sleep(duration)

            final_content = segment["content"].removesuffix(WAITING_USER_MARKER).strip()

            await asyncio.sleep(DRAFT_INTERVAL)

            send_delay = 1

            while self._running:
                result = await asyncio.gather(
                    self._bot.send_message(
                        chat_id=int(self.config["default_chat_id"]),
                        text=final_content,
                    ),
                    return_exceptions=True,
                )

                if not isinstance(result[0], Exception) and result[0]:
                    break
                await asyncio.sleep(send_delay)
                send_delay = min(send_delay * 1.5, 15)

    async def _handle_telegram_message(self, update: Update, _context):
        """处理来自telegram的消息。"""
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content="收到Telegram消息",
            ),
        )
        from linhai.agent import Agent as AgentType

        if not update.message:
            return

        chat_id = str(update.message.chat_id)
        if chat_id != self.config["default_chat_id"]:
            return

        content = update.message.text
        if not content:
            return

        agent = self.registry.get_member_typechecked("agent", AgentType)
        if agent:
            message = TelegramMessage(
                chat_id=chat_id,
                content=content,
                message_id=update.message.message_id,
            )
            await agent.message_processor.add_new_message(message)
            state_machine = self.registry.get_member_typechecked(
                "state_machine", AgentStateMachine
            )
            if state_machine.state == "waiting_user":
                state_machine.transition_to_working()

    async def _handle_telegram_sticker(self, update: Update, _context):
        """处理来自telegram的表情包消息。"""
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content="收到Telegram表情包",
            ),
        )
        from linhai.agent import Agent as AgentType

        if not update.message:
            return

        chat_id = str(update.message.chat_id)
        if chat_id != self.config["default_chat_id"]:
            return

        if not update.message.sticker:
            return

        sticker = update.message.sticker
        if not self._bot:
            return

        file = await self._bot.get_file(sticker.file_id)
        sticker_data = await file.download_as_bytearray()
        sticker_bytes = bytes(sticker_data)

        message = load_sticker(sticker_bytes, self.registry)

        agent = self.registry.get_member_typechecked("agent", AgentType)
        if agent:
            await agent.message_processor.add_new_message(message)
            state_machine = self.registry.get_member_typechecked(
                "state_machine", AgentStateMachine
            )
            if state_machine.state == "waiting_user":
                state_machine.transition_to_working()

    async def before_agent_loop(self, _agent: "AgentType"):
        """在Agent循环开始前启动telegram bot和发送任务。"""

        if self._running:
            return

        self._application = (
            Application.builder().token(self.config["bot_token"]).build()
        )
        self._application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, self._handle_telegram_message
            )
        )
        self._application.add_handler(
            MessageHandler(filters.Sticker.ALL, self._handle_telegram_sticker)
        )

        await self._application.initialize()
        await self._application.start()
        assert self._application.updater is not None
        await self._application.updater.start_polling()
        self._bot = self._application.bot

        self._running = True
        from linhai.task_supervisor import TaskSupervisor

        task_supervisor = self.registry.get_member_typechecked(
            "task_supervisor", TaskSupervisor
        )
        task_supervisor.create_supervised_task("telegram_send_loop", self._send_loop)

    async def shutdown(self):
        """关闭telegram bot和发送任务。"""
        if self._application and self._running:
            self._running = False
            from linhai.task_supervisor import TaskSupervisor

            task_supervisor = self.registry.get_member_typechecked(
                "task_supervisor", TaskSupervisor
            )
            task_supervisor.cancel("telegram_send_loop")
            await self._application.stop()
            await self._application.shutdown()

    def register(self, lifecycle: "Lifecycle") -> None:
        """注册到Lifecycle。"""
        lifecycle.after_segment.register(self.after_segment_finished)
        lifecycle.before_agent_loop.register(self.before_agent_loop)
