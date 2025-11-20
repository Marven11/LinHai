"""Command-line interface for LinHai agent."""

from typing import List, Optional, cast
import asyncio

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, TextArea, TabbedContent, TabPane
from textual import events
from linhai.llm import (
    ChatMessage,
    AnswerToken,
    AnswerTokenUsage,
    Answer,
    ToolCallMessage,
    ToolConfirmationMessage,
)
from linhai.agent import Agent
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.group_chat import GroupChat
from linhai.utils import CliRuntimeNotice

# Import components from the components module
from .components import (
    RainbowAsciiArt,
    AnimatedWelcomeWidget,
    RuntimeMessageWidget,
    MessageWidget,
    CandidateList,
)

# Import new managers
from .completion import CompletionManager
from .token_manager import TokenManager

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
    #token-usage {
        width: 100%;
        height: 1;
        background: #101520;
        color: #474e5b;
    }
    .welcome-message {
        width: 100%;
        text-align: center;
        content-align: center middle;
    }
    """

    MAX_MESSAGES = 1000

    def __init__(
        self,
        group_chat: GroupChat,
        init_messages: list[str] | None = None,
    ):
        super().__init__()
        self.theme = "nord"
        self.messages: List[MessageWidget] = []
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
        self.current_tool_call: Optional[ToolCallMessage] = None
        self.current_tool_confirmation: Optional[ToolConfirmationMessage] = None

        # 初始化管理器
        self.completion_manager = CompletionManager(group_chat)
        self.token_manager = TokenManager()

        # 自动滚动状态
        self.is_user_scroll_to_end = False

        # 候选列表组件
        self.candidate_list: Optional[CandidateList] = None

        # SubAgent当前消息引用
        self.subagent_current_messages: dict[str, MessageWidget] = {}

    def compose(self) -> ComposeResult:
        """组合UI组件"""
        with TabbedContent(id="main-tabs"):
            with TabPane("Agent", id="agent-tab"):
                with VerticalScroll(id="chat-container"):
                    for msg in self.messages:
                        yield msg

                # 候选列表初始隐藏，根据需要显示（放在输入框上方）
                yield Static("", id="candidate-list-container")
                yield TextArea(
                    placeholder="输入消息...", id="input", language="markdown"
                )
                yield Static("", id="token-usage")

            with TabPane("SubAgent", id="subagent-tab"):
                with VerticalScroll(id="subagent-container"):
                    yield Static("SubAgent消息将显示在这里", id="subagent-content")

    def show_completion_list(self, prefix: str, candidates: list[str]) -> None:
        """显示候选列表"""
        if not candidates:
            self.hide_completion_list()
            return

        self.completion_manager.completion_prefix = prefix
        self.completion_manager.completion_candidates = candidates
        self.completion_manager.completion_active = True

        # 创建或更新候选列表组件
        if self.candidate_list:
            self.candidate_list.candidates = candidates
            self.candidate_list.prefix = prefix
            self.candidate_list.selected_index = 0
            self.candidate_list.update_display()
        else:
            self.candidate_list = CandidateList(candidates, prefix)
            self.query_one("#candidate-list-container").mount(self.candidate_list)

    def hide_completion_list(self) -> None:
        """隐藏候选列表"""
        self.completion_manager.completion_active = False
        if self.candidate_list:
            self.candidate_list.remove()
            self.candidate_list = None

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """处理文本区域内容变化"""
        value = event.text_area.text
        candidates = self.completion_manager.handle_input_change(value)

        if candidates is not None:
            self.show_completion_list(
                self.completion_manager.completion_prefix, candidates
            )
        else:
            self.hide_completion_list()

    async def watch_agent_answer_queue(self):
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

                if current_message and current_message.is_reasoning != is_reasoning:
                    current_message.update_display()
                    current_message = None

                container = self.query_one("#chat-container")

                if current_message is None:
                    # 获取当前LLM名字
                    agent = self.group_chat.get_members("agent", Agent)
                    llm_name, _llm = agent.get_current_llm_info()
                    current_message = MessageWidget(
                        role="assistant",
                        content=content,
                        is_reasoning=is_reasoning,
                        sender_name=llm_name,
                    )
                    await asyncio.sleep(0)
                    container.mount(current_message)
                    self.messages.append(current_message)
                    current_message.update_display()
                    self._trim_messages_if_needed()
                else:
                    current_message.append_content(content)
                # 自动滚动到底部
                if self.should_auto_scroll():
                    container.scroll_end(animate=False)
            elif isinstance(output, AnswerTokenUsage):
                self.token_manager.current_token_usage = output
            elif isinstance(output, Answer):
                # 获取并累加token使用量
                token_usage = output.get_token_usage()
                if token_usage is not None:
                    self.token_manager.update_cumulative_usage(token_usage)
                    self.token_manager.current_token_usage = None
                    # 传入当前回答的token长度
                    self.update_token_display(token_usage.total_tokens)

                if current_message:
                    current_message.update_display()
                current_message = None
            else:
                raise RuntimeError(
                    f"Unknown Type in agent_answer: {type(output)=} {output=}"
                )

    async def watch_ui_log_queue(self):
        """监听ui_log队列并处理运行时日志"""
        while True:
            output = await self.group_chat.receive("ui_log")

            if isinstance(output, CliRuntimeNotice):
                # 处理运行时消息
                container = self.query_one("#chat-container")
                widget = RuntimeMessageWidget(
                    level=output.level, content=output.content
                )
                container.mount(widget)
                self._trim_messages_if_needed()
                # 自动滚动到底部
                if self.should_auto_scroll():
                    container.scroll_end(animate=False)
            else:
                raise RuntimeError(f"Unknown Type in ui_log: {type(output)=} {output=}")

    async def watch_exit_signal_queue(self):
        """监听exit_signal队列并处理退出信号"""
        while True:
            output = await self.group_chat.receive("exit_signal")

            if isinstance(output, dict) and "return_code" in output:
                return_code = output["return_code"]
                self.exit(return_code=return_code)
                return  # 立即返回，不再处理其他消息
            else:
                raise RuntimeError(
                    f"Unknown Type in exit_signal: {type(output)=} {output=}"
                )

    async def watch_subagent_message_queue(self):
        """监听subagent_message队列并处理SubAgent消息"""
        while True:
            output = await self.group_chat.receive("subagent_message")

            if isinstance(output, dict) and "subagent_name" in output:
                # 处理SubAgent消息
                subagent_name = output["subagent_name"]
                content = output["content"]
                message_type = output.get("type", "message")
                is_reasoning = output.get("is_reasoning", False)

                # 在SubAgent标签页显示消息
                subagent_container = self.query_one("#subagent-container")

                if message_type == "token":
                    # 流式token输出
                    if subagent_name not in self.subagent_current_messages:
                        # 创建新消息
                        current_message = MessageWidget(
                            role="assistant",
                            content=content,
                            sender_name=subagent_name,
                            is_reasoning=is_reasoning,
                        )
                        self.subagent_current_messages[subagent_name] = current_message
                        subagent_container.mount(current_message)
                        current_message.update_display()
                    else:
                        # 追加到现有消息
                        current_message = self.subagent_current_messages[subagent_name]
                        current_message.append_content(content)
                elif message_type == "message_complete":
                    # 消息完成，清除当前消息引用
                    if subagent_name in self.subagent_current_messages:
                        self.subagent_current_messages[subagent_name].update_display()
                        del self.subagent_current_messages[subagent_name]
                elif message_type == "runtime_notice":
                    # 运行时通知消息
                    level = output.get("level", "INFO")
                    widget = RuntimeMessageWidget(level=level, content=content)
                    subagent_container.mount(widget)
                else:
                    # 完整消息（向后兼容）
                    widget = MessageWidget(
                        role="assistant",
                        content=content,
                        sender_name=subagent_name,
                        is_reasoning=False,
                    )
                    subagent_container.mount(widget)
                    widget.update_display()

                # 自动滚动到底部
                subagent_container.scroll_end(animate=False)
            else:
                raise RuntimeError(
                    f"Unknown Type in subagent_message: {type(output)=} {output=}"
                )

    async def watch_output_queue(self):
        """启动四个独立的任务分别监听不同的队列"""
        # 创建四个独立的任务
        agent_answer_task = asyncio.create_task(self.watch_agent_answer_queue())
        ui_log_task = asyncio.create_task(self.watch_ui_log_queue())
        exit_signal_task = asyncio.create_task(self.watch_exit_signal_queue())
        subagent_message_task = asyncio.create_task(self.watch_subagent_message_queue())

        # 等待任一任务完成（通常是因为退出信号或异常）
        done, pending = await asyncio.wait(
            [agent_answer_task, ui_log_task, exit_signal_task, subagent_message_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # 取消其他未完成的任务
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # 如果是退出任务，确保正确退出
        if exit_signal_task in done:
            # exit_signal_task已经处理了退出逻辑
            return

        # 如果其他任务出现异常，重新抛出
        for task in done:
            if task.exception():
                exception = task.exception()
                raise (
                    exception
                    if exception
                    else Exception("Task failed without exception")
                )

    async def on_mount(self) -> None:
        """应用挂载时启动输出队列监听"""
        self.output_watcher_task = asyncio.create_task(self.watch_output_queue())

        # 如果有初始消息，自动发送
        if self.init_messages:
            for init_message in self.init_messages:
                user_msg = ChatMessage(role="user", message=init_message)
                self.messages.append(
                    MessageWidget(
                        role="user",
                        content=init_message,
                        sender_name="user",
                        is_reasoning=False,
                    )
                )
                await self.group_chat.send("user_message", user_msg)
                # 更新UI
                agent = self.group_chat.get_members("agent", Agent)
                widget = MessageWidget(
                    user_msg.role, user_msg.message, sender_name="user"
                )
                container = self.query_one("#chat-container")
                container.mount(widget)
                widget.update_display()
                # 自动滚动到底部
                if self.should_auto_scroll():
                    container.scroll_end(animate=False)
        else:
            # 显示欢迎消息（如果没有初始消息）
            agent = self.group_chat.get_members("agent", Agent)
            llm_name, _llm = agent.get_current_llm_info()
            version = "v0.1.0"

            container = self.query_one("#chat-container")

            # 创建彩虹ASCII艺术组件
            rainbow_art = RainbowAsciiArt(ASCII_ART)
            rainbow_art.add_class("welcome-message")
            container.mount(rainbow_art)

            # 显示动画欢迎信息
            animated_welcome = AnimatedWelcomeWidget(version, llm_name)
            animated_welcome.add_class("welcome-message")
            container.mount(animated_welcome)

        self.agent_task = asyncio.create_task(
            self.group_chat.get_members("agent", Agent).run()
        )

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

        # 关闭所有终端
        from linhai.tool.tools.terminal import close_all_terminals

        close_all_terminals()

    def update_token_display(self, current_answer_token: int) -> None:
        """更新token使用量显示，包括百分比"""
        agent = self.group_chat.get_members("agent", Agent)
        display_text = self.token_manager.get_token_display_text(
            agent, current_answer_token
        )

        token_display = self.query_one("#token-usage")
        assert isinstance(token_display, Static)
        token_display.update(display_text)

    def _trim_messages_if_needed(self) -> None:
        """如果消息数量超过阈值，修剪旧消息"""

        message_widgets = self.query_one("#chat-container").query(MessageWidget)
        if len(message_widgets) < self.MAX_MESSAGES:
            return
        for i in range(self.MAX_MESSAGES - len(message_widgets)):
            message_widgets[i].remove()

    async def on_key(self, event: events.Key) -> None:
        """处理键盘事件"""
        if self.output_watcher_task and self.output_watcher_task.done():
            await self.output_watcher_task
            raise RuntimeError("Output watcher task is dead!")
        if self.agent_task and self.agent_task.done():
            await self.agent_task
            raise RuntimeError("Agent task is dead!")

        # 处理补全相关的键盘事件
        if self.completion_manager.completion_active and self.candidate_list:
            if event.key in ["up", "down", "tab", "enter", "escape"]:
                if self.completion_manager.handle_key_event(
                    event.key, cast(TextArea, self.query_one("#input"))
                ):
                    event.stop()
                    return

        # 处理ctrl+enter发送消息
        if event.key == "ctrl+enter":
            await self._handle_message_submission()
            event.stop()
            return

        if event.key == "ctrl+c":
            # 先关闭所有终端，然后退出应用
            from linhai.tool.tools.terminal import close_all_terminals
            from linhai.tool.mcp_connector import MCPConnector

            close_all_terminals()
            await self.group_chat.get_members(
                "mcp_connector", MCPConnector
            ).disconnect_all_mcp_servers()
            self.app.exit()

    async def confirm_tool_request(self, tool_call: ToolCallMessage):
        """向用户确认是否需要调用工具"""
        self.current_tool_confirmation = None
        self.current_tool_call = tool_call
        # 显示确认提示
        self.query_one("#input").placeholder = (  # type: ignore
            f"确认执行工具 {tool_call.function_name} 吗？(y/n)"
        )
        # 等待用户输入（通过 on_input_submitted 处理）
        while self.current_tool_confirmation is None:
            await asyncio.sleep(0.01)
        return self.current_tool_confirmation

    def should_auto_scroll(self):
        container = self.query_one("#chat-container")
        return (
            self.is_user_scroll_to_end
            and container.scroll_y >= container.max_scroll_y - 5
        )

    def on_mouse_scroll_down(self, _event: events.MouseScrollDown) -> None:
        container = self.query_one("#chat-container")

        self.is_user_scroll_to_end = container.is_vertical_scroll_end

    def on_mouse_scroll_up(self, _event: events.MouseScrollUp) -> None:
        self.is_user_scroll_to_end = False

    async def _handle_message_submission(self) -> None:
        """处理消息提交"""
        text_area = cast(TextArea, self.query_one("#input"))
        message_text = text_area.text.strip()

        # 如果补全列表处于激活状态，不处理提交事件
        if self.completion_manager.completion_active:
            return

        # 如果刚刚完成候选选择，忽略此次提交事件并清除标志
        if self.completion_manager.just_completed_candidate:
            self.completion_manager.just_completed_candidate = False
            return

        if self.current_tool_call:
            # 处理工具确认响应
            user_input = message_text.strip().lower()
            if user_input in ["y", "yes", "是"]:
                confirmed = True
            elif user_input in ["n", "no", "否"]:
                confirmed = False
            else:
                # 无效输入，提示重新输入
                text_area.text = ""
                text_area.placeholder = "请输入 'y' 或 'n' 来确认工具调用"
                return

            # 发送确认消息
            self.current_tool_confirmation = ToolConfirmationMessage(
                tool_call=self.current_tool_call, confirmed=confirmed
            )

            # 重置当前工具请求
            self.current_tool_call = None
            text_area.text = ""
            text_area.placeholder = "输入消息..."
            return

        if message_text:
            # 隐藏欢迎消息
            container = self.query_one("#chat-container")
            welcome_widgets = container.query(".welcome-message")
            for widget in welcome_widgets:
                widget.remove()

            # 添加用户消息
            user_msg = ChatMessage(role="user", message=message_text)
            self.messages.append(
                MessageWidget(
                    role="user",
                    content=message_text,
                    sender_name="user",
                    is_reasoning=False,
                )
            )
            await self.group_chat.send("user_message", user_msg)
            text_area.text = ""
            # 更新UI
            widget = MessageWidget(user_msg.role, user_msg.message, sender_name="user")
            container.mount(widget)
            widget.update_display()
            self.is_user_scroll_to_end = True
            container.scroll_end(animate=False)
