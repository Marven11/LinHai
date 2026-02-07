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
    MessageGenerationWidget,
)
from .context_tab import ContextTabWidget
from ..token_manager import TokenManager
from .command_handler import CommandHandler
from .messages_list import MessagesList

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
        self.group_chat = group_chat
        self.group_chat.register_queue("exit_signal")
        self.group_chat.register_queue("token_usage")
        group_chat.register_member("cli_app", self)

        cli_args = group_chat.get_members("cli_args", argparse.Namespace)
        self.init_messages = list(cli_args.message.copy() if cli_args.message else [])
        if cli_args.file:
            self.init_messages += [
                f"[{file_path.name}]({file_path})" for file_path in cli_args.file
            ]

        self.current_response_buffer = ""
        self.output_watcher_task: Optional[asyncio.Task] = None
        self.agent_task: Optional[asyncio.Task] = None
        self.exit_signal_task: Optional[asyncio.Task] = None
        self.token_usage_task: Optional[asyncio.Task] = None

        self.token_manager = TokenManager(group_chat)

        self.completions = []
        self.command_completions = self._generate_command_completions()
        self.autocomplete = None

        self.cli_config = cli_config
        self.command_handler = CommandHandler(self.group_chat)

        self.group_chat.add_postinit(self.postinit)

    def postinit(self):
        lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
        lifecycle.register_after_message_generation(self.after_message_generation)
        self.exit_signal_task = asyncio.create_task(self.watch_exit_signal_queue())
        self.token_usage_task = asyncio.create_task(self.watch_token_usage_queue())

    def compose(self) -> ComposeResult:
        """组合UI组件"""
        with TabbedContent(id="main-tabs"):
            with TabPane("Agent", id="agent-tab"):
                lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
                self.messages_list = MessagesList(
                    group_chat=self.group_chat,
                    cli_config=self.cli_config,
                    theme=self.theme,
                    lifecycle=lifecycle,
                    id="chat-container",
                )
                yield self.messages_list

                yield Input(placeholder="输入消息...", id="input")
                yield FooterWidget(
                    self.group_chat,
                    self.token_manager,
                    use_nerd_font=self.cli_config.use_nerd_font,
                )

            with TabPane("Context", id="context-tab"):
                yield ContextTabWidget(self.group_chat)

    async def after_message_generation(self, answer, full_response, tool_calls):
        token_usage = answer.get_token_usage()
        if token_usage is not None:
            self.token_manager.update_cumulative_usage(token_usage)
            self.token_manager.current_token_usage = None
            self.update_token_display(token_usage.total_tokens)



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

    def _generate_command_completions(self) -> list[str]:
        """动态生成/命令补全列表"""
        return [
            "/queue",
            "/help",
            "/status",
        ]

    async def on_mount(self) -> None:
        """应用挂载时启动输出队列监听"""
        self.completions = self._generate_dynamic_completions()
        await self.messages_list.start_listening()
        if self.init_messages:
            await self.messages_list.add_initial_messages(self.init_messages)
        else:
            rainbow_art = RainbowAsciiArt(ASCII_ART)
            rainbow_art.add_class("welcome-message")
            self.messages_list.mount(rainbow_art)
            agent = self.group_chat.get_members("agent", Agent)
            llm_name, _llm = agent.get_current_llm_info()
            version = "v0.1.0"
            animated_welcome = AnimatedWelcomeWidget(version, llm_name)
            animated_welcome.add_class("welcome-message")
            self.messages_list.mount(animated_welcome)

        self.agent_task = asyncio.create_task(
            self.group_chat.get_members("agent", Agent).run()
        )

        input_element = self.query_one("#input", Input)

        self.autocomplete = AutoComplete(
            target=input_element,
            candidates=lambda _state: [
                DropdownItem(item)
                for item in self.completions + self._generate_command_completions()
            ],
        )
        self.mount(self.autocomplete)
        self.set_focus(input_element)

        cliapp_tool = ToolSet()

        @cliapp_tool.register_tool(
            name="suicide",
            desc="杀死自己并退出APP",
            args={
                "return_code": ToolArgInfo(
                    desc="退出代码，0表示成功，非0表示错误", type="int"
                ),
            },
            required_args=["return_code"],
        )
        def _suicide(return_code: int):
            """杀死自己并退出程序，指定返回代码

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
        if hasattr(self, 'messages_list'):
            await self.messages_list.cleanup()
        if self.agent_task:
            self.agent_task.cancel()
        if self.exit_signal_task:
            self.exit_signal_task.cancel()
        if self.token_usage_task:
            self.token_usage_task.cancel()
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

    async def _handle_regular_message(self, message_text: str) -> None:
        input_element = self.query_one("#input", Input)
        await self.messages_list.add_user_message(message_text)
        input_element.value = ""

    async def _handle_message_submission(self) -> None:
        """处理消息提交"""
        from textual.widgets import Input

        input_element = self.query_one("#input", Input)
        message_text = input_element.value.strip()

        if not message_text:
            return

        container = self.query_one("#chat-container")
        welcome_widgets = container.query("RainbowAsciiArt, AnimatedWelcomeWidget")
        for widget in welcome_widgets:
            widget.remove()

        await self._handle_regular_message(message_text)