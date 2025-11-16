"""Command-line interface for LinHai agent."""

from typing import List, Optional, cast
import asyncio
import time

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, Input
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
    #chat-container {
        min-height: 60%;
        background: #2E3440;
    }
    #input {
        height: 3;
        background: #2E3440;
        border: solid yellow;
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
        self.messages: List[MessageWidget] = []
        self.group_chat = group_chat
        self.group_chat.register_queue("cli_agent_output")
        self.group_chat.register_queue("cli_runtime_output")
        self.group_chat.register_queue("cli_exit")
        group_chat.register_member("cli_app", self)

        self.init_messages = init_messages

        self.current_response_buffer = ""
        self.output_watcher_task: Optional[asyncio.Task] = None
        self.agent_task: Optional[asyncio.Task] = None
        self.current_tool_call: Optional[ToolCallMessage] = None
        self.current_tool_confirmation: Optional[ToolConfirmationMessage] = None
        self.current_token_usage: AnswerTokenUsage | None = None
        self.cumulative_token_usage: dict[str, int] | None = None

        # 补全相关状态
        self.candidate_list: Optional[CandidateList] = None
        self.completion_prefix: str = ""  # @或/
        self.completion_candidates: list[str] = []
        self.completion_active: bool = False
        self.just_completed_candidate: bool = False  # 标记是否刚刚完成候选选择

        # 自动滚动状态
        self.is_user_scroll_to_end = False

    def compose(self) -> ComposeResult:
        """组合UI组件"""
        with VerticalScroll(id="chat-container"):
            for msg in self.messages:
                yield msg

        # 候选列表初始隐藏，根据需要显示（放在输入框上方）
        yield Static("", id="candidate-list-container")
        yield Input(placeholder="输入消息...", id="input")
        yield Static("", id="token-usage")

    def get_completion_candidates(self, prefix: str, current_text: str) -> list[str]:
        """获取补全候选项"""
        if prefix == "@":
            # 获取配置的LLM名称列表
            agent = self.group_chat.get_members("agent", Agent)
            return agent.context.get("llm_names", [])
        elif prefix == "/":
            # 获取可用的命令列表
            return ["queue", "quit", "exit"]
        return []

    def show_completion_list(self, prefix: str, candidates: list[str]) -> None:
        """显示候选列表"""
        if not candidates:
            self.hide_completion_list()
            return

        self.completion_prefix = prefix
        self.completion_candidates = candidates
        self.completion_active = True

        # 创建或更新候选列表组件
        container = self.query_one("#candidate-list-container")
        if self.candidate_list:
            self.candidate_list.candidates = candidates
            self.candidate_list.prefix = prefix
            self.candidate_list.selected_index = 0
            self.candidate_list.update_display()
        else:
            self.candidate_list = CandidateList(candidates, prefix)
            container.mount(self.candidate_list)

    def hide_completion_list(self) -> None:
        """隐藏候选列表"""
        self.completion_active = False
        if self.candidate_list:
            self.candidate_list.remove()
            self.candidate_list = None

    def on_input_changed(self, event: Input.Changed) -> None:
        """处理输入框内容变化"""
        value = event.value
        if not value:
            self.hide_completion_list()
            return

        # 检查是否以@或/开头
        if value.startswith("@"):
            # 提取@后面的文本，处理@后面是空格的情况
            parts = value[1:].split()
            after_at = parts[0] if parts else ""
            candidates = self.get_completion_candidates("@", after_at)
            # 过滤匹配的候选项
            if after_at:
                candidates = [c for c in candidates if c.startswith(after_at)]
            # 如果输入中包含空格，说明LLM名称已输入完毕，隐藏候选列表
            if " " in value:
                self.hide_completion_list()
            else:
                self.show_completion_list("@", candidates)
        elif value.startswith("/"):
            # 提取/后面的文本，处理/后面是空格的情况
            parts = value[1:].split()
            after_slash = parts[0] if parts else ""
            candidates = self.get_completion_candidates("/", after_slash)
            # 过滤匹配的候选项
            if after_slash:
                candidates = [c for c in candidates if c.startswith(after_slash)]
            # 如果输入中包含空格，说明命令已输入完毕，隐藏候选列表
            if " " in value:
                self.hide_completion_list()
            else:
                self.show_completion_list("/", candidates)
        else:
            self.hide_completion_list()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理用户输入"""
        # 如果补全列表处于激活状态，不处理提交事件
        if self.completion_active:
            return

        # 如果刚刚完成候选选择，忽略此次提交事件并清除标志
        if self.just_completed_candidate:
            self.just_completed_candidate = False
            return

        if self.current_tool_call:
            # 处理工具确认响应
            user_input = event.value.strip().lower()
            if user_input in ["y", "yes", "是"]:
                confirmed = True
            elif user_input in ["n", "no", "否"]:
                confirmed = False
            else:
                # 无效输入，提示重新输入
                event.input.value = ""
                cast(Input, self.query_one("#input")).placeholder = (  # type: ignore
                    "请输入 'y' 或 'n' 来确认工具调用"
                )
                return

            # 发送确认消息
            self.current_tool_confirmation = ToolConfirmationMessage(
                tool_call=self.current_tool_call, confirmed=confirmed
            )

            # 重置当前工具请求
            self.current_tool_call = None
            event.input.value = ""
            cast(Input, self.query_one("#input")).placeholder = "输入消息..."  # type: ignore
            return

        if event.value:
            # 隐藏欢迎消息
            container = self.query_one("#chat-container")
            welcome_widgets = container.query(".welcome-message")
            for widget in welcome_widgets:
                widget.remove()

            # 添加用户消息
            user_msg = ChatMessage(role="user", message=event.value)
            self.messages.append(
                MessageWidget(
                    role="user",
                    content=event.value,
                    sender_name="user",
                    is_reasoning=False,
                )
            )
            await self.group_chat.send("agent_user_input", user_msg)
            event.input.value = ""
            # 更新UI
            _ = self.group_chat.get_members(
                "agent", Agent
            )  # pylint: disable=unused-variable
            widget = MessageWidget(user_msg.role, user_msg.message, sender_name="user")
            container.mount(widget)
            widget.update_display()
            self.is_user_scroll_to_end = True
            container.scroll_end(animate=False)

    async def watch_output_queue(self):
        """监听输出队列并更新UI"""
        current_message = None
        while True:
            # 同时监听三个队列
            agent_output_task = asyncio.create_task(
                self.group_chat.receive("cli_agent_output")
            )
            runtime_output_task = asyncio.create_task(
                self.group_chat.receive("cli_runtime_output")
            )
            exit_task = asyncio.create_task(self.group_chat.receive("cli_exit"))

            done, pending = await asyncio.wait(
                [agent_output_task, runtime_output_task, exit_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # 取消未完成的任务
            for task in pending:
                task.cancel()

            # 处理完成的任务
            for task in done:
                output = task.result()

                # 检查是否是退出任务
                if task == exit_task:
                    if isinstance(output, dict) and "return_code" in output:
                        return_code = output["return_code"]
                        self.exit(return_code=return_code)
                        return  # 立即返回，不再处理其他消息
                    continue  # 跳过其他处理

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
                elif isinstance(output, AnswerToken):
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
                    self.current_token_usage = output
                elif isinstance(output, dict) and "return_code" in output:
                    # 处理退出信号
                    return_code = output["return_code"]
                    self.exit(return_code=return_code)
                    return
                elif isinstance(output, Answer):

                    # 获取并累加token使用量
                    token_usage = output.get_token_usage()
                    if token_usage is not None:
                        if self.cumulative_token_usage is None:
                            self.cumulative_token_usage = token_usage.model_dump()
                        else:
                            self.cumulative_token_usage[
                                "input_tokens"
                            ] += token_usage.input_tokens
                            self.cumulative_token_usage[
                                "output_tokens"
                            ] += token_usage.output_tokens
                            self.cumulative_token_usage[
                                "total_tokens"
                            ] += token_usage.total_tokens
                        self.current_token_usage = None
                        # 传入当前回答的token长度
                        self.update_token_display(token_usage.total_tokens)

                    if current_message:
                        current_message.update_display()
                    current_message = None
                else:
                    raise RuntimeError(f"Unknown Type: {type(output)=} {output=}")

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
                await self.group_chat.send("agent_user_input", user_msg)
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
        if self.cumulative_token_usage is None:
            display_text = "Token usage: Not available"
            token_display = self.query_one("#token-usage")
            assert isinstance(token_display, Static)
            token_display.update(display_text)
        else:
            input_tokens = self.cumulative_token_usage["input_tokens"]
            output_tokens = self.cumulative_token_usage["output_tokens"]
            if self.current_token_usage is not None:
                input_tokens += self.current_token_usage.input_tokens
                output_tokens += self.current_token_usage.output_tokens

            # 获取当前LLM的token限制
            agent = self.group_chat.get_members("agent", Agent)
            llm_name, llm_instance = agent.get_current_llm_info()
            token_limit = llm_instance.get_token_limit()

            message_count = len(agent.message_processor.messages)
            display_text_pieces = [
                llm_name,
                f"{message_count} msgs",
                f"in {input_tokens:,}",
                f"out {output_tokens:,}",
            ]
            if token_limit and token_limit > 0:
                percentage = (current_answer_token / token_limit) * 100
                # 使用进度条样式显示百分比
                filled_bars = int(percentage / 10)  # 每10%一个实心方块
                empty_bars = 10 - filled_bars
                progress_bar = "█" * filled_bars + "▒" * empty_bars
                display_text_pieces.append(
                    f"{progress_bar} {percentage:.0f}% of {token_limit:,}"
                )

            token_display = self.query_one("#token-usage")
            assert isinstance(token_display, Static)
            token_display.update(" | ".join(display_text_pieces))

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
        if self.completion_active and self.candidate_list:
            if event.key == "up":
                # 上箭头：向上移动（索引增加）
                self.candidate_list.update_selection(1)
                event.stop()
                return
            elif event.key == "down":
                # 下箭头：向下移动（索引减少）
                self.candidate_list.update_selection(-1)
                event.stop()
                return
            elif event.key in ["tab", "enter"]:
                # 选择当前候选项
                selected = self.candidate_list.get_selected()
                input_widget = cast(Input, self.query_one("#input"))
                current_value = input_widget.value

                # 替换@或/后面的文本
                if current_value.startswith("@"):
                    input_widget.value = f"@{selected} "
                elif current_value.startswith("/"):
                    input_widget.value = f"/{selected} "

                # 同步光标位置到末尾
                input_widget.cursor_position = len(input_widget.value)

                # 标记刚刚完成候选选择，忽略接下来的提交事件
                self.just_completed_candidate = True
                event.stop()
                self.hide_completion_list()
                return
            elif event.key == "escape":
                # 取消补全
                self.hide_completion_list()
                event.stop()
                return

        if event.key == "ctrl+c":
            # 先关闭所有终端，然后退出应用
            from linhai.tool.tools.terminal import close_all_terminals

            close_all_terminals()
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
        return self.is_user_scroll_to_end and container.scroll_y >= container.max_scroll_y - 2

    def on_mouse_scroll_down(self, _event: events.MouseScrollDown) -> None:
        container = self.query_one("#chat-container")
        
        self.is_user_scroll_to_end = container.is_vertical_scroll_end

    def on_mouse_scroll_up(self, _event: events.MouseScrollUp) -> None:
        container = self.query_one("#chat-container")
        
        self.is_user_scroll_to_end = False

