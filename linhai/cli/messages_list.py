"""Messages list management for CLI."""

import asyncio
from typing import List, Optional, Union

from textual.containers import VerticalScroll
from textual.widgets import Static
from textual import events

from linhai.agent import Agent, Lifecycle
from linhai.group_chat import GroupChat
from linhai.config import CLIConfig
from linhai.parsed_message import ParsedAnswer
from linhai.utils import CliRuntimeNotice
from linhai.llm import AnswerTokenUsage, UserMessage

from .components import (
    RainbowAsciiArt,
    AnimatedWelcomeWidget,
    RuntimeMessageWidget,
    MessageWidget,
    UserMessageWidget,
    MessageGenerationWidget,
)


class MessagesList(VerticalScroll):
    """管理消息列表的widget，处理消息创建、挂载和自动滚动."""

    def __init__(
        self,
        group_chat: GroupChat,
        cli_config: CLIConfig,
        theme: str,
        lifecycle: Lifecycle,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.group_chat = group_chat
        self.cli_config = cli_config
        self.theme = theme
        self.messages: List[Union[MessageWidget, UserMessageWidget, MessageGenerationWidget]] = []
        self.current_message_generation_widget: Optional[MessageGenerationWidget] = None
        self.is_user_scroll_to_end = True
        self.auto_scroll_timer_task: Optional[asyncio.Task] = None
        self.output_watcher_task: Optional[asyncio.Task] = None

        self.group_chat.register_queue("parsed_agent_answer")
        self.group_chat.register_queue("ui_log")
        group_chat.register_member("messages_list", self)
        lifecycle.register_after_message_generation(self.after_message_generation)

    async def start_listening(self):
        """启动监听队列的任务."""
        self.output_watcher_task = asyncio.create_task(self.watch_output_queue())
        self.auto_scroll_timer_task = asyncio.create_task(self._auto_scroll_timer())

    async def add_initial_messages(self, init_messages: List[str]):
        """添加初始消息."""
        for init_message in init_messages:
            user_msg = UserMessage(message=init_message)
            self.messages.append(
                UserMessageWidget(
                    content=init_message,
                    sender_name="user",
                    theme=self.theme,
                )
            )
            await self.group_chat.send("user_message", user_msg)

            widget = UserMessageWidget(
                user_msg.message, sender_name="user", theme=self.theme
            )
            self.mount(widget)
            widget.update_display()

    async def add_user_message(self, message_text: str):
        """添加用户消息."""
        user_msg = UserMessage(message=message_text)
        self.messages.append(
            UserMessageWidget(
                content=message_text,
                sender_name="user",
                theme=self.theme,
            )
        )
        await self.group_chat.send("user_message", user_msg)

        widget = UserMessageWidget(
            user_msg.message, sender_name="user", theme=self.theme
        )
        self.mount(widget)
        widget.update_display()
        self.is_user_scroll_to_end = True
        self.scroll_end(animate=False)

    async def _handle_single_parsed_answer(self, parsed_answer: ParsedAnswer) -> None:
        agent = self.group_chat.get_members("agent", Agent)
        llm_name, _llm = agent.get_current_llm_info()

        generation_widget = MessageGenerationWidget()
        self.mount(generation_widget)
        self.messages.append(generation_widget)

        self.current_message_generation_widget = generation_widget

        message_widget = MessageWidget(
            role="assistant",
            sender_name=llm_name,
            theme=self.theme,
            parsed_answer=parsed_answer,
        )
        generation_widget.set_message_widget(message_widget)

    async def after_message_generation(self, answer, full_response, tool_calls):
        # 当消息生成完成后，如果用户没有手动滚动，则滚动到底部
        if self.should_auto_scroll():
            self.scroll_end(animate=False)

    async def watch_parsed_agent_answer_queue(self) -> None:
        while True:
            output = await self.group_chat.receive("parsed_agent_answer")
            if isinstance(output, ParsedAnswer):
                asyncio.create_task(self._handle_single_parsed_answer(output))
            else:
                raise RuntimeError(
                    f"Unknown Type in parsed_agent_answer: {type(output)=} {output=}"
                )

    async def watch_ui_log_queue(self) -> None:
        while True:
            output = await self.group_chat.receive("ui_log")

            if isinstance(output, CliRuntimeNotice):
                widget = RuntimeMessageWidget(
                    level=output.level, content=output.content
                )

                if self.current_message_generation_widget:
                    self.current_message_generation_widget.add_runtime_message(widget)
                else:
                    self.mount(widget)

            else:
                raise RuntimeError(f"Unknown Type in ui_log: {type(output)=} {output=}")


    async def watch_output_queue(self) -> None:
        parsed_answer_task = asyncio.create_task(self.watch_parsed_agent_answer_queue())
        ui_log_task = asyncio.create_task(self.watch_ui_log_queue())

        done, pending = await asyncio.wait(
            [
                parsed_answer_task,
                ui_log_task,
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        for task in done:
            if task.exception():
                exception = task.exception()
                raise (
                    exception
                    if exception
                    else Exception("Task failed without exception")
                )

    async def _auto_scroll_timer(self):
        while True:
            await asyncio.sleep(0.1)
            if self.should_auto_scroll():
                self.scroll_end(animate=False)

    def should_auto_scroll(self) -> bool:
        return (
            self.is_user_scroll_to_end
            and self.scroll_y >= self.max_scroll_y - 7
        )

    def on_mouse_scroll_down(self, _event: events.MouseScrollDown) -> None:
        self.is_user_scroll_to_end = self.is_vertical_scroll_end

    def on_mouse_scroll_up(self, _event: events.MouseScrollUp) -> None:
        self.is_user_scroll_to_end = False

    def add_runtime_message(self, level: str, content: str) -> None:
        """添加运行时消息到消息列表。"""
        widget = RuntimeMessageWidget(level=level, content=content)
        self.mount(widget)
        if self.should_auto_scroll():
            self.scroll_end(animate=False)

    async def on_unmount(self) -> None:
        """组件卸载时清理任务"""
        await self.cleanup()

    async def cleanup(self):
        """清理任务."""
        if self.output_watcher_task:
            self.output_watcher_task.cancel()
        if self.auto_scroll_timer_task:
            self.auto_scroll_timer_task.cancel()
