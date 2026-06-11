"""Command-line interface for LinHai agent."""

from pathlib import Path
import argparse

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import TabbedContent, TabPane
from textual import events, work

from linhai.agent import Agent, Lifecycle
from linhai.config import TUIConfig
from linhai.registry import Registry
from linhai.task_supervisor import TextualTaskSupervisor
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.machine_control.master_host import close_all_terminals_async
from linhai.tool.base import SuccessfulToolResult
from linhai.tool.mcp_connector import MCPConnector

from .components import (
    RainbowAsciiArt,
    AnimatedWelcomeWidget,
    FooterWidget,
    ExtendedTextArea,
    CommandCompletionMenu,
    ProblemWidget,
)
from .context_tab import ContextTabWidget
from .planning_tab import PlanningTabWidget
from .process_tab import ProcessTabWidget
from ..token_manager import TokenManager
from ..utils.i18n import t
from .messages_list import MessagesList

ASCII_ART = r"""
  █████       █████ ██████   █████ █████   █████   █████████   █████
 ░░███       ░░███ ░░██████ ░░███ ░░███   ░░███   ███░░░░░███ ░░███
  ░███        ░███  ░███░███ ░███  ░███    ░███  ░███    ░███  ░███
  ░███        ░███  ░███░░███░███  ░███████████  ░███████████  ░███
  ░███        ░███  ░███ ░░██████  ░███░░░░░███  ░███░░░░░███  ░███
  ░███      █ ░███  ░███  ░░█████  ░███    ░███  ░███    ░███  ░███
  ███████████ █████ █████  ░░█████ █████   █████ █████   █████ █████
 ░░░░░░░░░░░ ░░░░░ ░░░░░    ░░░░░ ░░░░░   ░░░░░ ░░░░░   ░░░░░ ░░░░░"""

ASCII_ART_SMALL = r"""
 ██   ████ ██  ██ ██  ██  ████  ████
░██  ░░██ ░███░██░██ ░██ ██ ░██░░██ 
░██   ░██ ░██ ███░██████░██████ ░██ 
░██   ░██ ░██░░██░██░░██░██░░██ ░██ 
░████ ████░██ ░██░██ ░██░██ ░██ ████
░░░░ ░░░░ ░░   ░░░░  ░░ ░░  ░░ ░░░░"""


class TUIApp(App):
    """Textual-based TUI application for LinHai agent interaction."""

    CSS = """
    Screen {
        layout: vertical;
    }
    TabbedContent {
        height: 1fr;
    }
    TabbedContent > ContentSwitcher {
        height: 1fr;
    }
    TabPane {
        height: 1fr;
    }
    #chat-container {
        min-height: 60%;
        scrollbar-size-vertical: 1;
    }
    #notes-container {
        padding: 1;
        scrollbar-size-vertical: 1;
    }
    #input {
        height: auto;
        border: blank;
    }
    #input-container {
        height: auto;
        layout: horizontal;
        align-vertical: bottom;
    }
    CommandCompletionMenu {
        display: none;
    }
    """

    def __init__(
        self,
        registry: Registry,
        tui_config: TUIConfig,
        init_messages: list[str],
        init_files: list[Path],
    ):
        super().__init__()
        if tui_config.textual_theme is not None:
            self.theme = tui_config.textual_theme
        self.pygments_theme = tui_config.pygments_theme
        theme = self.get_theme(self.theme)
        self.syntax_background = theme.background if theme else "#121212"
        self.registry = registry
        self.registry.register_queue("exit_signal")
        TextualTaskSupervisor(self, registry)

        self.init_messages = list(init_messages)
        if init_files:
            self.init_messages += [
                f"[{file_path.name}]({file_path})" for file_path in init_files
            ]

        self.current_response_buffer = ""

        self.token_manager = TokenManager(registry)

        self.tui_config = tui_config

        self.registry.add_postinit(self.postinit)

    def get_refresh_interval(self) -> float:
        """根据当前消息数量获取widget刷新间隔"""
        message_count = self.messages_list.get_message_count()
        if message_count < 200:
            return 0.05
        return 0.5

    def postinit(self):
        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        lifecycle.after_message_generation.register(self.after_message_generation)
        self.watch_exit_signal_queue()
        self.token_manager.start_watching()

    def compose(self) -> ComposeResult:
        """组合UI组件"""
        with TabbedContent(id="main-tabs"):
            with TabPane("Agent", id="agent-tab"):
                lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
                self.messages_list = MessagesList(
                    registry=self.registry,
                    tui_config=self.tui_config,
                    pygments_theme=self.pygments_theme,
                    syntax_background=self.syntax_background,
                    lifecycle=lifecycle,
                    get_refresh_interval=self.get_refresh_interval,
                    id="chat-container",
                )
                yield self.messages_list

                yield CommandCompletionMenu(self.registry, id="completion-menu")
                yield ProblemWidget(self.registry)
                with Horizontal(id="input-container"):
                    yield ExtendedTextArea(
                        on_enter_key=self._handle_message_submission,
                        placeholder=t(
                            {
                                "zh_CN": "Enter发送，Shift+Enter换行（如果终端支持）",
                                "en": "Enter to send, Shift+Enter for newline (if terminal supports)",
                            }
                        ),
                        id="input",
                        show_line_numbers=False,
                    )
                yield FooterWidget(
                    self.registry,
                    self.token_manager,
                    use_nerd_font=self.tui_config.use_nerd_font,
                )

            with TabPane("Context", id="context-tab"):
                yield ContextTabWidget(self.registry)

            with TabPane("Process", id="process-tab"):
                yield ProcessTabWidget(self.registry)

            cli_args = self.registry.get_member_typechecked(
                "cli_args", argparse.Namespace
            )
            if cli_args.planning:
                with TabPane("Planning", id="planning-tab"):
                    yield PlanningTabWidget(self.registry)

    async def after_message_generation(self, parsed_answer, tool_calls):
        token_usage = parsed_answer._answer.get_token_usage()
        if token_usage is not None:
            self.update_token_display(token_usage.total_tokens)

    @work(exclusive=False)
    async def watch_exit_signal_queue(self) -> None:
        """监听exit_signal队列并处理退出信号"""
        while True:
            output = await self.registry.receive("exit_signal")

            if isinstance(output, dict) and "return_code" in output:
                return_code = output["return_code"]
                self.exit(return_code=return_code)
                return
            else:
                raise RuntimeError(
                    f"Unknown Type in exit_signal: {type(output)=} {output=}"
                )

    @work(exclusive=False)
    async def _run_agent(self) -> None:
        agent = self.registry.get_member_typechecked("agent", Agent)
        await agent.run()

    def _get_command_completions_to_menu(self) -> None:
        from linhai.agent.command_callback import CommandCallback
        from .components import CommandCompletionMenu

        completion_menu = self.query_one("#completion-menu", CommandCompletionMenu)
        completion_menu.add_candidates(CommandCallback.get_command_completions())

        if self.registry.has_member("skills_manager"):
            from linhai.skills import SkillsManager

            skills_manager = self.registry.get_member_typechecked(
                "skills_manager", SkillsManager
            )
            skill_names = [f"/{name}" for name in skills_manager.skills]
            completion_menu.add_candidates(skill_names)

    async def on_mount(self) -> None:
        """应用挂载时启动输出队列监听"""
        self.registry.register_cleanup(close_all_terminals_async)
        await self.messages_list.start_listening()
        if self.init_messages:
            await self.messages_list.add_initial_messages(self.init_messages)
        else:
            rainbow_art = RainbowAsciiArt(
                ASCII_ART, ASCII_ART_SMALL, self.get_refresh_interval
            )
            rainbow_art.add_class("welcome-message")
            self.messages_list.mount(rainbow_art)
            agent = self.registry.get_member_typechecked("agent", Agent)
            llm_name, _llm = agent.get_current_llm_info()
            version = "v0.3.0"
            animated_welcome = AnimatedWelcomeWidget(
                version, llm_name, self.get_refresh_interval
            )
            animated_welcome.add_class("welcome-message")
            self.messages_list.mount(animated_welcome)

        self._get_command_completions_to_menu()
        self._run_agent()

        input_element = self.query_one("#input", ExtendedTextArea)
        self.set_focus(input_element)

        cliapp_tool = ToolSet()

        @cliapp_tool.register_tool(
            name="suicide",
            desc=t({"zh_CN": "杀死自己并退出APP", "en": "Kill self and exit the app"}),
            args={
                "return_code": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "退出代码，0表示成功，非0表示错误",
                            "en": "Exit code, 0 for success, non-zero for error",
                        }
                    ),
                    schema={"type": "integer"},
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

            return SuccessfulToolResult(content="")

        from linhai.tool.main import ToolManager

        self.registry.get_member_typechecked(
            "tool_manager", ToolManager
        ).register_toolset("tui", cliapp_tool)

    async def on_unmount(self) -> None:
        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        await lifecycle.before_exit.trigger()

        if hasattr(self, "messages_list"):
            await self.messages_list.cleanup()

        await self.registry.call_cleanups()

    def update_token_display(self, current_answer_token: int) -> None:
        """更新token使用量显示，包括百分比"""
        footer_widget = self.query_one(FooterWidget)
        footer_widget.update_token_info(current_answer_token)

    async def on_key(self, event: events.Key) -> None:
        """处理键盘事件"""

        if event.key == "enter":
            await self._handle_message_submission()
            event.stop()
            return

        if event.key == "shift+enter":
            input_element = self.query_one("#input", ExtendedTextArea)
            input_element.insert("\n")

    async def _handle_regular_message(self, message_text: str) -> None:
        await self.messages_list.add_user_message(message_text)

    async def _handle_message_submission(self) -> None:
        """处理消息提交"""
        input_element = self.query_one("#input", ExtendedTextArea)
        message_text = input_element.text
        stripped_text = message_text.strip()

        input_element.text = ""

        if not stripped_text:
            return

        container = self.query_one("#chat-container")
        welcome_widgets = container.query("RainbowAsciiArt, AnimatedWelcomeWidget")
        for widget in welcome_widgets:
            widget.remove()

        await self._handle_regular_message(stripped_text)
