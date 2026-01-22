"""Command-line interface for LinHai agent."""

import argparse
import asyncio
from typing import Dict, List, Optional, Union

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane, Input
from textual import events
from textual_autocomplete import AutoComplete, DropdownItem

from linhai.agent import Agent, Lifecycle
from linhai.agent.base import Message
from linhai.config import CLIConfig
from linhai.group_chat import GroupChat
from linhai.llm import (
    AnswerTokenUsage,
)
from linhai.parsed_message import ParsedAnswer
from linhai.subagent.message_wrapper import (
    SubAgentParsedAnswerWrapper,
)
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.machine_control.master_host import close_all_terminals
from linhai.tool.mcp_connector import MCPConnector
from linhai.utils import CliRuntimeNotice

from .components import (
    RainbowAsciiArt,
    AnimatedWelcomeWidget,
    RuntimeMessageWidget,
    MessageWidget,
    UserMessageWidget,
    FooterWidget,
)
from .context_tab import ContextTabWidget
from ..token_manager import TokenManager
from .command_handler import CommandHandler

ASCII_ART = r"""
  █████       █████ ██████   █████ █████   █████   █████████   █████
 ▒▒███       ▒▒███ ▒▒██████ ▒▒███ ▒▒███   ▒▒███   ███▒▒▒▒▒███ ▒▒███
  ▒███        ▒███  ▒███▒███ ▒███  ▒███    ▒███  ▒███    ▒███  ▒███
  ▒███        ▒███  ▒███▒▒███▒███  ▒███████████  ▒███████████  ▒███
  ▒███        ▒███  ▒███ ▒▒██████  ▒███▒▒▒▒▒███  ▒███▒▒▒▒▒███  ▒███
  ▒███      █ ▒███  ▒███  ▒▒█████  ▒███    ▒███  ▒███    ▒███  ▒███
  ███████████ █████ █████  ▒▒█████ █████   █████ █████   █████ █████
 ▒▒▒▒▒▒▒▒▒▒▒ ▒▒▒▒▒ ▒▒▒▒▒    ▒▒▒▒▒ ▒▒▒▒▒   ▒▒▒▒▒ ▒▒▒▒▒   ▒▒▒▒▒ ▒▒▒▒▒
"""


class CLIApp(App):
    """Textual-based CLI application for LinHai agent interaction."""

    CSS = """
    Screen {
        layout: vertical;
        background: #2E3440;
    }
    TabbedContent {
        height: 1fr;
    }
    TabbedContent > ContentSwitcher {
        height: 1fr;
    }
    TabPane {
        height: 1fr;
        background: #2E3440;
    }
    #chat-container {
        min-height: 60%;
        background: #2E3440;
        scrollbar-size-vertical: 1;
    }
    #notes-container {
        background: #2E3440;
        padding: 1;
        scrollbar-size-vertical: 1;
    }
    #input {
        min-height: 1;
        height: auto;
        background: #2E3440;
        border: solid $primary;
    }
    AutoComplete {
        & AutoCompleteList {
            max-height: 2;
        }
    }
    """

    def __init__(
        self,
        group_chat: GroupChat,
        cli_config: CLIConfig,
    ):
        super().__init__()
        self.theme = cli_config.theme
        self.messages: List[Union[MessageWidget, UserMessageWidget]] = []
        self.group_chat = group_chat

        self.group_chat.register_queue("parsed_agent_answer")
        self.group_chat.register_queue("ui_log")
        self.group_chat.register_queue("exit_signal")
        self.group_chat.register_queue("subagent_message")
        self.group_chat.register_queue("token_usage")
        group_chat.register_member("cli_app", self)

        # 从cli_args构建init_messages
        cli_args = group_chat.get_members("cli_args", argparse.Namespace)
        self.init_messages = list(cli_args.message or [])
        if cli_args.file:
            self.init_messages.extend(
                [f"<Filepath {file_path}>" for file_path in cli_args.file]
            )

        self.current_response_buffer = ""
        self.output_watcher_task: Optional[asyncio.Task] = None
        self.agent_task: Optional[asyncio.Task] = None

        self.token_manager = TokenManager(group_chat)

        self.is_user_scroll_to_end = False

        self.subagent_current_messages: Dict[str, MessageWidget] = {}

        self.completions = []  # 初始化为空，等待agent注册后再生成
        self.command_completions = self._generate_command_completions()
        self.autocomplete = None

        self.cli_config = cli_config
        self.command_handler = CommandHandler(self.group_chat)
        self.auto_scroll_timer_task: Optional[asyncio.Task] = None

        self.group_chat.add_postinit(self.postinit)

    def postinit(self):
        self.group_chat.get_members(
            "lifecycle", Lifecycle
        ).register_after_message_generation(self.after_message_generation)

    def compose(self) -> ComposeResult:
        """组合UI组件"""
        with TabbedContent(id="main-tabs"):
            with TabPane("Agent", id="agent-tab"):
                with VerticalScroll(id="chat-container"):
                    for msg in self.messages:
                        yield msg

                yield Input(placeholder="输入消息...", id="input")
                yield FooterWidget(
                    self.group_chat,
                    self.token_manager,
                    use_nerd_font=self.cli_config.use_nerd_font,
                )

            with TabPane("SubAgent", id="subagent-tab"):
                with VerticalScroll(id="subagent-container"):
                    yield Static("SubAgent消息将显示在这里", id="subagent-content")

            with TabPane("Context", id="context-tab"):
                yield ContextTabWidget(self.group_chat)

    async def _handle_single_parsed_answer(self, parsed_answer: ParsedAnswer) -> None:
        agent = self.group_chat.get_members("agent", Agent)
        llm_name, _llm = agent.get_current_llm_info()

        container = self.query_one("#chat-container")
        widget = MessageWidget(
            role="assistant",
            sender_name=llm_name,
            theme=self.theme,
            parsed_answer=parsed_answer,
        )
        container.mount(widget)
        self.messages.append(widget)

    async def after_message_generation(self, answer, full_response, tool_calls):
        token_usage = answer.get_token_usage()
        if token_usage is not None:
            self.token_manager.update_cumulative_usage(token_usage)
            self.token_manager.current_token_usage = None
            self.update_token_display(token_usage.total_tokens)

    async def watch_parsed_agent_answer_queue(self) -> None:
        """监听parsed_agent_answer队列并处理解析后的Agent回答"""
        while True:
            output = await self.group_chat.receive("parsed_agent_answer")
            if isinstance(output, ParsedAnswer):
                # 为每个ParsedAnswer启动独立的处理任务
                asyncio.create_task(self._handle_single_parsed_answer(output))
            else:
                raise RuntimeError(
                    f"Unknown Type in parsed_agent_answer: {type(output)=} {output=}"
                )

    async def watch_ui_log_queue(self) -> None:
        """监听ui_log队列并处理运行时日志"""
        while True:
            output = await self.group_chat.receive("ui_log")

            if isinstance(output, CliRuntimeNotice):

                container = self.query_one("#chat-container")
                widget = RuntimeMessageWidget(
                    level=output.level, content=output.content
                )
                container.mount(widget)

            else:
                raise RuntimeError(f"Unknown Type in ui_log: {type(output)=} {output=}")

    async def watch_exit_signal_queue(self) -> None:
        """监听exit_signal队列并处理退出信号"""
        while True:
            output = await self.group_chat.receive("exit_signal")

            if isinstance(output, dict) and "return_code" in output:
                return_code = output["return_code"]
                self.exit(return_code=return_code)
                return
            else:
                raise RuntimeError(
                    f"Unknown Type in exit_signal: {type(output)=} {output=}"
                )

    async def watch_subagent_message_queue(self) -> None:
        """监听subagent_message队列并处理SubAgent消息"""
        while True:
            output = await self.group_chat.receive("subagent_message")
            if isinstance(output, SubAgentParsedAnswerWrapper):
                await self._handle_subagent_parsed_answer(output)
            elif isinstance(output, CliRuntimeNotice):
                subagent_container = self.query_one("#subagent-container")
                widget = RuntimeMessageWidget(
                    level=output.level, content=output.content
                )
                subagent_container.mount(widget)
            else:
                raise RuntimeError(
                    f"Unknown Type in subagent_message: {type(output)=} {output=}"
                )

    async def watch_token_usage_queue(self) -> None:
        """监听token_usage队列并处理token使用信息"""
        while True:
            output = await self.group_chat.receive("token_usage")
            if isinstance(output, AnswerTokenUsage):
                self.token_manager.current_token_usage = output
            else:
                raise RuntimeError(
                    f"Unknown Type in token_usage: {type(output)=} {output=}"
                )

    async def _handle_subagent_parsed_answer(
        self, wrapper: SubAgentParsedAnswerWrapper
    ) -> None:
        """处理SubAgent的ParsedAnswer"""
        # SubAgent的ParsedAnswer应该像主Agent的ParsedAnswer一样处理
        # 使用MessageWidget显示，传递segment给子widget
        subagent_name = wrapper.subagent_name
        parsed_answer = wrapper.parsed_answer

        container = self.query_one("#subagent-container")
        widget = MessageWidget(
            role="assistant",
            sender_name=subagent_name,
            theme=self.theme,
            parsed_answer=parsed_answer,
        )
        container.mount(widget)

    async def watch_output_queue(self) -> None:
        """启动五个独立的任务分别监听不同的队列"""

        parsed_answer_task = asyncio.create_task(self.watch_parsed_agent_answer_queue())
        ui_log_task = asyncio.create_task(self.watch_ui_log_queue())
        exit_signal_task = asyncio.create_task(self.watch_exit_signal_queue())
        subagent_message_task = asyncio.create_task(self.watch_subagent_message_queue())
        token_usage_task = asyncio.create_task(self.watch_token_usage_queue())

        done, pending = await asyncio.wait(
            [
                parsed_answer_task,
                ui_log_task,
                exit_signal_task,
                subagent_message_task,
                token_usage_task,
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if exit_signal_task in done:
            return

        for task in done:
            if task.exception():
                exception = task.exception()
                raise (
                    exception
                    if exception
                    else Exception("Task failed without exception")
                )

    def _generate_dynamic_completions(self) -> list[str]:
        """动态生成@补全列表"""
        try:
            from linhai.agent import Agent

            agent = self.group_chat.get_members("agent", Agent)
            if agent:

                llm_names = agent.llm_names
                return [f"@{name}" for name in llm_names]
        except OSError:
            pass
        return []

    async def _auto_scroll_timer(self):
        """定时滚动timer，每0.1秒检查是否需要自动滚动"""
        while True:
            await asyncio.sleep(0.1)
            if self.should_auto_scroll():
                container = self.query_one("#chat-container")
                container.scroll_end(animate=False)

    def _generate_command_completions(self) -> list[str]:
        """动态生成/命令补全列表"""
        return [
            "/queue",
            "/help",
            "/status",
            "/todolist_list",
            "/todolist_add",
            "/todolist_delete",
        ]

    async def on_mount(self) -> None:
        """应用挂载时启动输出队列监听"""
        self.completions = self._generate_dynamic_completions()

        self.output_watcher_task = asyncio.create_task(self.watch_output_queue())

        if self.init_messages:
            for init_message in self.init_messages:
                from linhai.llm import UserMessage

                user_msg = UserMessage(message=init_message)
                self.messages.append(
                    UserMessageWidget(
                        content=init_message,
                        sender_name="user",
                        theme=self.theme,
                    )
                )
                await self.group_chat.send("user_message", user_msg)

                agent = self.group_chat.get_members("agent", Agent)
                widget = UserMessageWidget(
                    user_msg.message, sender_name="user", theme=self.theme
                )
                container = self.query_one("#chat-container")
                container.mount(widget)
                widget.update_display()

        else:
            agent = self.group_chat.get_members("agent", Agent)
            llm_name, _llm = agent.get_current_llm_info()
            version = "v0.1.0"

            container = self.query_one("#chat-container")

            rainbow_art = RainbowAsciiArt(ASCII_ART)
            rainbow_art.add_class("welcome-message")
            container.mount(rainbow_art)

            animated_welcome = AnimatedWelcomeWidget(version, llm_name)
            animated_welcome.add_class("welcome-message")
            container.mount(animated_welcome)

        self.agent_task = asyncio.create_task(
            self.group_chat.get_members("agent", Agent).run()
        )

        # 启动自动滚动定时器
        self.auto_scroll_timer_task = asyncio.create_task(self._auto_scroll_timer())

        input_element = self.query_one("#input")
        assert isinstance(input_element, Input)

        self.autocomplete = AutoComplete(
            target=input_element,
            candidates=lambda _state: [
                DropdownItem(item)
                for item in self.completions + self._generate_command_completions()
            ],
        )
        self.mount(self.autocomplete)

        cliapp_tool = ToolSet()

        @cliapp_tool.register_tool(
            name="exit_app",
            desc="退出agent并关闭APP",
            args={
                "return_code": ToolArgInfo(
                    desc="退出代码，0表示成功，非0表示错误", type="int"
                ),
            },
            required_args=["return_code"],
        )
        def _exit_app(return_code: int):
            """退出Agent程序，指定返回代码

            Args:
                return_code: 退出代码，0表示成功，非0表示错误

            Returns:
                退出消息（实际上程序会退出，所以不会返回）
            """
            self.exit(return_code=return_code)

        from linhai.tool.main import ToolManager

        self.group_chat.get_members("tool_manager", ToolManager).add_toolset(
            cliapp_tool
        )

    async def on_unmount(self) -> None:
        """应用卸载时取消任务并关闭所有终端"""
        if self.output_watcher_task:
            self.output_watcher_task.cancel()
        if self.agent_task:
            self.agent_task.cancel()
        if self.auto_scroll_timer_task:
            self.auto_scroll_timer_task.cancel()

        close_all_terminals()

    def update_token_display(self, current_answer_token: int) -> None:
        """更新token使用量显示，包括百分比"""
        footer_widget = self.query_one(FooterWidget)
        footer_widget.update_token_info(current_answer_token)

    async def on_key(self, event: events.Key) -> None:
        """处理键盘事件"""
        if self.output_watcher_task and self.output_watcher_task.done():
            await self.output_watcher_task
            raise RuntimeError("Output watcher task is dead!")
        if self.agent_task and self.agent_task.done():
            await self.agent_task
            raise RuntimeError("Agent task is dead!")

        if event.key == "ctrl+enter" or event.key == "enter":
            await self._handle_message_submission()
            event.stop()
            return

        if event.key == "ctrl+c":
            close_all_terminals()
            await self.group_chat.get_members(
                "mcp_connector", MCPConnector
            ).disconnect_all_mcp_servers()
            self.app.exit()

    def should_auto_scroll(self) -> bool:
        container = self.query_one("#chat-container")
        return (
            self.is_user_scroll_to_end
            and container.scroll_y >= container.max_scroll_y - 7
        )

    def on_mouse_scroll_down(self, _event: events.MouseScrollDown) -> None:
        container = self.query_one("#chat-container")

        self.is_user_scroll_to_end = container.is_vertical_scroll_end

    def on_mouse_scroll_up(self, _event: events.MouseScrollUp) -> None:
        self.is_user_scroll_to_end = False

    async def _handle_regular_message(self, message_text: str) -> None:
        """处理普通消息，发送到agent。"""
        container = self.query_one("#chat-container")
        input_element = self.query_one("#input")

        from linhai.llm import UserMessage

        user_msg = UserMessage(message=message_text)
        self.messages.append(
            UserMessageWidget(
                content=message_text,
                sender_name="user",
                theme=self.theme,
            )
        )
        await self.group_chat.send("user_message", user_msg)
        input_element.value = ""  # type: ignore

        widget = UserMessageWidget(
            user_msg.message, sender_name="user", theme=self.theme
        )
        container.mount(widget)
        widget.update_display()
        self.is_user_scroll_to_end = True
        container.scroll_end(animate=False)

    async def _process_todolist_command(self, message_text: str) -> bool:
        assert self.command_handler is not None
        return await self.command_handler.handle_command(message_text)

    async def _handle_message_submission(self) -> None:
        """处理消息提交"""
        from textual.widgets import Input

        input_element = self.query_one("#input")
        assert isinstance(
            input_element, Input
        ), f"Expected Input widget, got {type(input_element)}"
        message_text = input_element.value.strip()

        if not message_text:
            return

        container = self.query_one("#chat-container")
        welcome_widgets = container.query("RainbowAsciiArt, AnimatedWelcomeWidget")
        for widget in welcome_widgets:
            widget.remove()

        if await self._process_todolist_command(message_text):
            input_element.value = ""  # 清除输入框
            return

        await self._handle_regular_message(message_text)
