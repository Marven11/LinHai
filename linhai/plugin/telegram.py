"""Telegram bot插件，监听Agent消息并通过telegram发送，接收telegram用户消息。

流式输出使用edit_message_text实现，而非draft API。

draft API的问题：send_message_draft会为每次调用创建独立的临时消息，
导致用户在聊天中看到多条重复消息。Telegram官方文档未说明draft API的正确用法，
实际使用中draft消息和最终send_message的消息会同时存在，造成消息重复。

解决方案：在segment开始生成时（after_segment回调），立即通过send_message发送初始消息，
然后通过edit_message_text反复编辑同一条消息来更新内容，实现流式输出效果。
这样始终只有一条消息，不会重复。
"""

from typing import TYPE_CHECKING, Literal
import asyncio
import logging
from collections import deque
from telegram import Update, Message, ReactionTypeEmoji
from telegram.ext import Application, MessageHandler, filters
from telegram.error import RetryAfter, BadRequest

if TYPE_CHECKING:
    from linhai.agent.create import TelegramContext
    from linhai.base import Message as BaseMessage
    from linhai.type_hints import WithSecret

from linhai.agent import Agent

from linhai.parsed_message import NormalSegment, Segment
from linhai.agent.messages import WAITING_USER_MARKER, RuntimeMessage
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.state_machine import AgentStateMachine
from linhai.registry import Registry
from linhai.plugin.message_checkers import Plugin
from linhai.telegram import TelegramMessage, load_sticker
from linhai.tool.base import (
    ToolSet,
    ToolArgInfo,
    SuccessfulToolResult,
    FailedToolResult,
    ToolResult,
)
from linhai.utils.common import UiNotice
from linhai.utils.i18n import t

EDIT_INTERVAL = 2


class TelegramPlugin(Plugin):
    """Telegram bot插件，实现通过telegram远程控制Agent。"""

    def __init__(self, registry: Registry, telegram_config: "TelegramContext"):
        super().__init__(registry)
        self.config = telegram_config
        self._bot = None
        self._application = None
        self._running = False
        self.send_queue: deque[NormalSegment] = deque()
        self._latest_message_id: int | None = None
        self._latest_chat_id: int | None = None

    async def _on_segment_start(self, _parsed_answer, segment: Segment):
        """在segment开始生成时将消息加入发送队列。

        监听after_segment事件而非after_segment_finished。
        after_segment在segment创建时触发（parsed_message.py:_process_token），
        此时segment刚进入生成状态，is_finished为False，content会随token到达持续增长。
        segment对象以引用方式存入队列，_process_token直接修改segment["content"]，
        队列中的同一对象会自动获得最新内容。
        """
        if segment["segment_type"] == "normal":
            self.send_queue.append(segment)

    async def _edit_with_retry(self, chat_id: int, message_id: int, text: str) -> bool:
        """编辑telegram消息，处理429限流和消息未修改的情况。

        使用asyncio.gather(..., return_exceptions=True)捕获异常，
        避免try/except（项目规范禁止EAFP风格）。
        遇到RetryAfter（429限流）时等待指定时间后重试一次。
        遇到BadRequest（如消息内容未变化）时返回False表示跳过。
        """
        assert self._bot is not None
        result = await asyncio.gather(
            self._bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
            ),
            return_exceptions=True,
        )
        if isinstance(result[0], RetryAfter):
            retry_after = result[0].retry_after
            if not isinstance(retry_after, int):
                retry_after = int(retry_after.total_seconds())
            await asyncio.sleep(retry_after)
            retry_result = await asyncio.gather(
                self._bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                ),
                return_exceptions=True,
            )
            return not isinstance(retry_result[0], Exception)
        if isinstance(result[0], BadRequest):
            return False
        return not isinstance(result[0], Exception)

    async def _send_loop(self):
        """发送循环，通过edit_message_text实现流式输出。

        从队列获取segment后，等待内容积累，发送初始消息，
        然后循环编辑直到segment完成，最后做最终编辑移除WAITING_USER_MARKER。
        初始发送失败时使用指数退避重试。
        """
        while self._running:
            if not self.send_queue:
                await asyncio.sleep(0.05)
                continue

            segment = self.send_queue.popleft()
            assert self._bot is not None
            chat_id = int(self.config["default_chat_id"])

            while not segment["content"].strip() and not segment["is_finished"]:
                await asyncio.sleep(0.1)

            if not segment["content"].strip():
                continue

            send_delay = 1
            message_id: int | None = None
            sent_text = ""
            while self._running:
                sent_text = segment["content"]
                result = await asyncio.gather(
                    self._bot.send_message(chat_id=chat_id, text=sent_text),
                    return_exceptions=True,
                )
                if isinstance(result[0], Exception) and not isinstance(
                    result[0], RetryAfter
                ):
                    await asyncio.sleep(send_delay)
                    send_delay = min(send_delay * 1.5, 15)
                    continue
                if isinstance(result[0], RetryAfter):
                    retry_after = result[0].retry_after
                    if not isinstance(retry_after, int):
                        retry_after = int(retry_after.total_seconds())
                    await asyncio.sleep(retry_after)
                    continue
                if isinstance(result[0], Message):
                    message_id = result[0].message_id
                    break

            if message_id is None:
                continue

            last_sent_content = sent_text

            while self._running and not segment["is_finished"]:
                await asyncio.sleep(EDIT_INTERVAL)
                current_content = segment["content"]
                if current_content == last_sent_content:
                    continue

                success = await self._edit_with_retry(
                    chat_id, message_id, current_content
                )
                if success:
                    last_sent_content = current_content

            final_content = segment["content"].removesuffix(WAITING_USER_MARKER).strip()
            if final_content and final_content != last_sent_content:
                await self._edit_with_retry(chat_id, message_id, final_content)
            elif not final_content:
                assert self._bot is not None
                await asyncio.gather(
                    self._bot.delete_message(chat_id=chat_id, message_id=message_id),
                    return_exceptions=True,
                )

    async def _handle_telegram_message(self, update: Update, _context):
        """处理来自telegram的消息。"""
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content="收到Telegram消息",
            ),
        )
        from linhai.agent import Agent

        if not update.message:
            return

        chat_id = str(update.message.chat_id)
        if chat_id != self.config["default_chat_id"]:
            return

        content = update.message.text
        if not content:
            return

        agent = self.registry.get_member_typechecked("agent", Agent)
        self._latest_chat_id = update.message.chat_id
        self._latest_message_id = update.message.message_id
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
        from linhai.agent import Agent

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

        agent = self.registry.get_member_typechecked("agent", Agent)
        await agent.message_processor.add_new_message(message)
        state_machine = self.registry.get_member_typechecked(
            "state_machine", AgentStateMachine
        )
        if state_machine.state == "waiting_user":
            state_machine.transition_to_working()

    def create_toolset(self) -> ToolSet:
        toolset = ToolSet()
        plugin_self = self

        @toolset.register_tool(
            name="send_telegram_reaction",
            desc=t(
                {
                    "zh_CN": "向telegram消息发送emoji reaction。只支持传入telegram支持的emoji",
                    "en": "Send an emoji reaction to a telegram message. Only telegram-supported emojis are accepted",
                }
            ),
            args={
                "emoji": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "要发送的emoji，只支持telegram支持的emoji",
                            "en": "The emoji to send, only telegram-supported emojis are accepted",
                        }
                    ),
                    schema={"type": "string"},
                ),
                "chat_id": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "目标聊天的chat_id，不提供则使用最近收到消息的chat_id",
                            "en": "Target chat_id, defaults to latest received message's chat_id",
                        }
                    ),
                    schema={"type": "integer"},
                ),
                "message_id": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "目标消息的message_id，不提供则使用最近收到消息的message_id",
                            "en": "Target message_id, defaults to latest received message's message_id",
                        }
                    ),
                    schema={"type": "integer"},
                ),
            },
            required_args=["emoji"],
        )
        async def send_telegram_reaction(
            emoji: str,
            chat_id: int | None = None,
            message_id: int | None = None,
        ) -> ToolResult:
            if plugin_self._bot is None:
                return FailedToolResult(content="telegram bot未初始化")
            target_chat_id = (
                chat_id if chat_id is not None else plugin_self._latest_chat_id
            )
            target_message_id = (
                message_id if message_id is not None else plugin_self._latest_message_id
            )
            if target_chat_id is None or target_message_id is None:
                return FailedToolResult(content="没有可回复的telegram消息")
            result = await asyncio.gather(
                plugin_self._bot.set_message_reaction(
                    chat_id=target_chat_id,
                    message_id=target_message_id,
                    reaction=[ReactionTypeEmoji(emoji=emoji)],
                ),
                return_exceptions=True,
            )
            if isinstance(result[0], Exception):
                return FailedToolResult(content=f"发送reaction失败: {result[0]}")
            return SuccessfulToolResult(content=f"已发送reaction: {emoji}")

        return toolset

    async def before_agent_loop(self, _agent: "Agent"):
        """在Agent循环开始前启动telegram bot和发送任务。"""

        if self._running:
            return

        from telegram import Bot

        bot = Bot(token=self.config["bot_token"])
        self._application = Application.builder().bot(bot).build()
        self._bot = bot

        self._application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, self._handle_telegram_message
            )
        )
        self._application.add_handler(
            MessageHandler(filters.Sticker.ALL, self._handle_telegram_sticker)
        )

        self._running = True

        from linhai.tool.main import ToolManager

        tool_manager = self.registry.get_member_typechecked("tool_manager", ToolManager)
        tool_manager.register_toolset("telegram", self.create_toolset())

        from linhai.task_supervisor import TaskSupervisor

        task_supervisor = self.registry.get_member_typechecked(
            "task_supervisor", TaskSupervisor
        )

        task_supervisor.create_supervised_task(
            "telegram_polling", self._run_polling_forever
        )
        task_supervisor.create_supervised_task("telegram_send_loop", self._send_loop)

    async def _run_polling_forever(self):
        """Initialize and start polling using async API.

        Uses Application.initialize() + start() + updater.start_polling() instead of
        Application.run_polling() to avoid creating a new event loop inside
        the already-running Textual event loop. bootstrap_retries=-1 ensures
        infinite retry during the bootstrap phase.
        """
        if not self._running:
            return
        assert self._application is not None
        assert self._application.updater is not None
        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling(bootstrap_retries=-1)
        while self._running:
            await asyncio.sleep(1)

    async def shutdown(self):
        """关闭telegram bot和发送任务。"""
        if self._application and self._running:
            self._running = False
            from linhai.task_supervisor import TaskSupervisor

            task_supervisor = self.registry.get_member_typechecked(
                "task_supervisor", TaskSupervisor
            )
            task_supervisor.cancel("telegram_send_loop")
            task_supervisor.cancel("telegram_polling")
            await self._application.stop()
            await self._application.shutdown()

    async def _on_exit(self):
        """退出时优雅停止telegram。"""
        await self.shutdown()

    def register(self, lifecycle: "Lifecycle") -> None:
        """注册到Lifecycle。"""
        lifecycle.after_segment.register(self._on_segment_start)
        lifecycle.before_agent_loop.register(self.before_agent_loop)
        lifecycle.before_exit.register(self._on_exit)


class TelegramReactionReminderPlugin(Plugin):
    """当agent收到消息后默默工作（只调工具不说话）时，提醒agent给用户点reaction或说点什么。"""

    NOTIFICATION_SOURCE = "telegram_reaction_reminder"
    REMINDER_MESSAGE = (
        "你收到消息后闷头工作，考虑给用户消息点reaction（如👀）或者说点什么来反馈状态"
    )

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self._has_responded = False

    async def _on_segment_finished(self, _parsed_answer, segment: Segment):
        if segment["segment_type"] == "normal" and segment["content"].strip():
            self._has_responded = True

    async def _on_reaction_tool_called(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: "BaseMessage | None",
        toolcall_arguments: dict,
        with_secret: "WithSecret | None",
        is_tool_failed_duplicated_error: bool,
    ) -> None:
        _ = (
            tool_index,
            status,
            message,
            toolcall_arguments,
            with_secret,
            is_tool_failed_duplicated_error,
        )
        if tool_name == "send_telegram_reaction":
            self._has_responded = True

    async def _before_message_generation(self):
        agent = self.registry.get_member_typechecked("agent", Agent)
        if self._has_responded:
            agent.message_processor.update_notification_message(
                None, source=self.NOTIFICATION_SOURCE
            )
        else:
            agent.message_processor.update_notification_message(
                RuntimeMessage(self.REMINDER_MESSAGE),
                source=self.NOTIFICATION_SOURCE,
            )

    async def _on_before_add_new_message(self, message: "BaseMessage") -> None:
        if isinstance(message, TelegramMessage):
            self._has_responded = False

    def register(self, lifecycle: "Lifecycle") -> None:
        lifecycle.after_toolcall.register(self._on_reaction_tool_called)
        lifecycle.after_segment_finished.register(self._on_segment_finished)
        lifecycle.before_message_generation.register(self._before_message_generation)
        lifecycle.before_add_new_message.register(self._on_before_add_new_message)
