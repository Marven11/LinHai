"""Command-line interface for LinHai agent."""

import asyncio
from typing import List, Optional, Union

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane, Input
from textual import events
from textual_autocomplete import AutoComplete, DropdownItem

from linhai.agent import Agent
from linhai.config import CLIConfig
from linhai.group_chat import GroupChat
from linhai.llm import (
    Answer,
    AnswerToken,
    AnswerTokenUsage,
)
from linhai.subagent.message_wrapper import (
    SubAgentAnswerTokenWrapper,
    SubAgentAnswerCompleteWrapper,
)
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.tool.tools.terminal import close_all_terminals
from linhai.tool.mcp_connector import MCPConnector
from linhai.utils import CliRuntimeNotice

from .components import (
    RainbowAsciiArt,
    AnimatedWelcomeWidget,
    RuntimeMessageWidget,
    MessageWidget,
    ReasoningContentWidget,
    FooterWidget,
)
from .token_manager import TokenManager
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
        init_messages: list[str] | None = None,
    ):
        super().__init__()
        self.theme = "nord"
        self.messages: List[Union[MessageWidget, ReasoningContentWidget]] = []
        self.group_chat = group_chat
        self.group_chat.register_queue("agent_answer")
        self.group_chat.register_queue("ui_log")
        self.group_chat.register_queue("exit_signal")
        self.group_chat.register_queue("subagent_message")
        group_chat.register_member("cli_app", self)

        self.init_messages = init_messages

        self.current_response_buffer = ""
        self.output_watcher_task: Optional[asyncio.Task] = None
        self.agent_task: Optional[asyncio.Task] = None

        self.token_manager = TokenManager()

        self.is_user_scroll_to_end = False

        self.subagent_current_messages: dict[
            str, Union[MessageWidget, ReasoningContentWidget]
        ] = {}

        self.completions = []  # 初始化为空，等待agent注册后再生成
        self.command_completions = self._generate_command_completions()
        self.autocomplete = None

        self.cli_config = cli_config
        self.command_handler = CommandHandler(self.group_chat)

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

    async def watch_agent_answer_queue(self) -> None:
        """监听agent_answer队列并处理Agent回答"""
        current_message = None
        while True:
            output = await self.group_chat.receive("agent_answer")
            if isinstance(output, AnswerToken):
                if output.reasoning_content:
                    is_reasoning = True
                    content = output.reasoning_content
                else:
                    is_reasoning = False
                    content = output.content
                if not content:
                    continue

                if current_message and (
                    isinstance(current_message, ReasoningContentWidget) != is_reasoning
                ):
                    current_message.update_display()
                    current_message.stop()
                    current_message = None

                container = self.query_one("#chat-container")

                if current_message is None:

                    agent = self.group_chat.get_members("agent", Agent)
                    llm_name, _llm = agent.get_current_llm_info()
                    if is_reasoning:
                        current_message = ReasoningContentWidget(
                            role="assistant",
                            content=content,
                            sender_name=llm_name,
                        )
                    else:
                        current_message = MessageWidget(
                            role="assistant",
                            content=content,
                            sender_name=llm_name,
                        )
                    await asyncio.sleep(0)
                    container.mount(current_message)
                    self.messages.append(current_message)
                    current_message.update_display()
                else:
                    current_message.feed_string(content)

                if self.should_auto_scroll():
                    container.scroll_end(animate=False)
            elif isinstance(output, AnswerTokenUsage):
                self.token_manager.current_token_usage = output
            elif isinstance(output, Answer):

                token_usage = output.get_token_usage()
                if token_usage is not None:
                    self.token_manager.update_cumulative_usage(token_usage)
                    self.token_manager.current_token_usage = None
                    self.update_token_display(token_usage.total_tokens)

                if current_message:
                    current_message.update_display()
                    current_message.stop()
                current_message = None
            else:
                raise RuntimeError(
                    f"Unknown Type in agent_answer: {type(output)=} {output=}"
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

                if self.should_auto_scroll():
                    container.scroll_end(animate=False)
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
            await self._handle_subagent_message(output)

    async def _handle_subagent_message(self, output) -> None:
        """处理单个SubAgent消息"""
        if isinstance(output, SubAgentAnswerTokenWrapper):
            await self._handle_subagent_token_wrapper(output)
        elif isinstance(output, SubAgentAnswerCompleteWrapper):
            await self._handle_subagent_answer_complete_wrapper(output)
        elif isinstance(output, CliRuntimeNotice):
            await self._handle_subagent_runtime_notice(output)
        elif isinstance(output, dict) and "subagent_name" in output:
            await self._handle_subagent_legacy_dict(output)
        else:
            raise RuntimeError(
                f"Unknown Type in subagent_message: {type(output)=} {output=}"
            )

    async def _handle_subagent_token_wrapper(
        self, wrapper: SubAgentAnswerTokenWrapper
    ) -> None:
        """处理SubAgentAnswerTokenWrapper"""
        subagent_name = wrapper.subagent_name
        token = wrapper.token

        content = token.content
        is_reasoning = token.reasoning_content is not None

        subagent_container = self.query_one("#subagent-container")

        self._cleanup_subagent_message_widget_if_needed(subagent_name, is_reasoning)

        if subagent_name not in self.subagent_current_messages:
            current_message = self._create_subagent_message_widget(
                subagent_name, content, is_reasoning
            )
            self.subagent_current_messages[subagent_name] = current_message
            subagent_container.mount(current_message)
            current_message.update_display()
        else:
            current_message = self.subagent_current_messages[subagent_name]
            current_message.append_content(content)

    async def _handle_subagent_answer_complete_wrapper(
        self, wrapper: SubAgentAnswerCompleteWrapper
    ) -> None:
        """处理SubAgentAnswerCompleteWrapper"""
        subagent_name = wrapper.subagent_name
        answer = wrapper.answer

        if subagent_name in self.subagent_current_messages:
            self.subagent_current_messages[subagent_name].update_display()
            del self.subagent_current_messages[subagent_name]

    async def _handle_subagent_runtime_notice(self, notice: CliRuntimeNotice) -> None:
        """处理CliRuntimeNotice"""
        subagent_container = self.query_one("#subagent-container")
        widget = RuntimeMessageWidget(level=notice.level, content=notice.content)
        subagent_container.mount(widget)

    async def _handle_subagent_legacy_dict(self, output_dict: dict) -> None:
        """处理旧格式的字典消息（向后兼容）"""
        subagent_name = output_dict["subagent_name"]
        content = output_dict["content"]
        message_type = output_dict.get("type", "message")
        is_reasoning = output_dict.get("is_reasoning", False)

        subagent_container = self.query_one("#subagent-container")

        if message_type == "token":
            self._cleanup_subagent_message_widget_if_needed(subagent_name, is_reasoning)

            if subagent_name not in self.subagent_current_messages:
                current_message = self._create_subagent_message_widget(
                    subagent_name, content, is_reasoning
                )
                self.subagent_current_messages[subagent_name] = current_message
                subagent_container.mount(current_message)
                current_message.update_display()
            else:
                current_message = self.subagent_current_messages[subagent_name]
                current_message.append_content(content)
        elif message_type == "message_complete":
            if subagent_name in self.subagent_current_messages:
                self.subagent_current_messages[subagent_name].update_display()
                del self.subagent_current_messages[subagent_name]
        else:
            assert False, f"Unsupported Type: {message_type}"

    def _cleanup_subagent_message_widget_if_needed(
        self, subagent_name: str, is_reasoning: bool
    ) -> None:
        """如果需要，清理旧的SubAgent消息widget"""
        current_widget = self.subagent_current_messages.get(subagent_name)
        if current_widget:
            if isinstance(current_widget, ReasoningContentWidget) and not is_reasoning:
                del self.subagent_current_messages[subagent_name]
            elif isinstance(current_widget, MessageWidget) and is_reasoning:
                del self.subagent_current_messages[subagent_name]

    def _create_subagent_message_widget(
        self, subagent_name: str, content: str, is_reasoning: bool
    ):
        """创建SubAgent消息widget"""
        if is_reasoning:
            return ReasoningContentWidget(
                role="assistant",
                content=content,
                sender_name=subagent_name,
            )
        else:
            return MessageWidget(
                role="assistant",
                content=content,
                sender_name=subagent_name,
            )

    async def watch_output_queue(self) -> None:
        """启动四个独立的任务分别监听不同的队列"""

        agent_answer_task = asyncio.create_task(self.watch_agent_answer_queue())
        ui_log_task = asyncio.create_task(self.watch_ui_log_queue())
        exit_signal_task = asyncio.create_task(self.watch_exit_signal_queue())
        subagent_message_task = asyncio.create_task(self.watch_subagent_message_queue())

        done, pending = await asyncio.wait(
            [agent_answer_task, ui_log_task, exit_signal_task, subagent_message_task],
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

                llm_names = agent.context.get("llm_names", [])
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
                    MessageWidget(
                        role="user",
                        content=init_message,
                        sender_name="user",
                    )
                )
                await self.group_chat.send("user_message", user_msg)

                agent = self.group_chat.get_members("agent", Agent)
                widget = MessageWidget("user", user_msg.message, sender_name="user")
                container = self.query_one("#chat-container")
                container.mount(widget)
                widget.update_display()

                if self.should_auto_scroll():
                    container.scroll_end(animate=False)
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

        for message in self.messages:
            message.stop()

        for message in self.subagent_current_messages.values():
            message.stop()

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
            MessageWidget(
                role="user",
                content=message_text,
                sender_name="user",
            )
        )
        await self.group_chat.send("user_message", user_msg)
        input_element.value = ""  # type: ignore

        widget = MessageWidget("user", user_msg.message, sender_name="user")
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
