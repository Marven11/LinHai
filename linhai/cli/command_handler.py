"""Command handler for CLI commands that should not be sent to agent."""

from linhai.group_chat import GroupChat
from linhai.tool.general import TodolistManager
from linhai.cli.components import TodolistWidget, RuntimeMessageWidget
from linhai.utils import CliRuntimeNotice
from linhai.input_parser import parse_user_input


class CommandHandler:
    """处理CLI命令，这些命令不会发送给agent。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    async def handle_command(self, message_text: str) -> bool:
        """处理命令，返回True表示已处理，False表示不是命令。"""
        parsed_input = parse_user_input(message_text)

        if parsed_input.switch_model:
            return await self._handle_switch_model(parsed_input.switch_model)

        if parsed_input.command:
            if parsed_input.command == "todolist_list":
                return await self._handle_todolist_list()
            elif parsed_input.command == "todolist_add":
                return await self._handle_todolist_add(message_text)
            elif parsed_input.command == "todolist_delete":
                return await self._handle_todolist_delete(message_text)
            elif (
                parsed_input.command == "context_garbage_clean"
                or parsed_input.command == "context_thanox"
            ):
                return await self._handle_context_tool_command(message_text)
            elif parsed_input.command == "queue":
                return await self._handle_queue_command(message_text)
            elif parsed_input.command == "subagent_start":
                return await self._handle_subagent_start_command()
            elif parsed_input.command == "quit" or parsed_input.command == "exit":
                return await self._handle_quit_command()
            elif parsed_input.command == "help":
                return await self._handle_help_command()
            elif parsed_input.command == "status":
                return await self._handle_status_command()

        return False

    async def _handle_todolist_list(self) -> bool:
        todolist_manager = self.group_chat.get_members(
            "todolist_manager", TodolistManager
        )
        assert todolist_manager is not None

        todolists = todolist_manager.list_todolists()
        widget = TodolistWidget(todolists)

        await self._mount_widget(widget)
        return True

    async def _handle_todolist_add(self, message_text: str) -> bool:
        arguments = message_text[len("/todolist_add") :].strip().split()
        if not arguments:
            await self._show_error_message("用法: /todolist_add <内容>")
            return True

        content = " ".join(arguments)
        todolist_manager = self.group_chat.get_members(
            "todolist_manager", TodolistManager
        )
        assert todolist_manager is not None

        todolist_id = todolist_manager.add_todolist(content)
        await self._show_success_message(f"成功添加todolist，ID: {todolist_id}")
        return True

    async def _handle_todolist_delete(self, message_text: str) -> bool:
        arguments = message_text[len("/todolist_delete") :].strip().split()
        if not arguments:
            await self._show_error_message("用法: /todolist_delete <todolist_id>")
            return True

        todolist_id = arguments[0]
        todolist_manager = self.group_chat.get_members(
            "todolist_manager", TodolistManager
        )
        assert todolist_manager is not None

        result = todolist_manager.delete_todolist(todolist_id)
        await self._show_success_message(result)
        return True

    async def _mount_widget(self, widget) -> None:
        from linhai.cli.app import CLIApp

        cli_app = self.group_chat.get_members("cli_app", CLIApp)
        assert cli_app is not None

        container = cli_app.query_one("#chat-container")
        container.mount(widget)

        if cli_app.should_auto_scroll():
            container.scroll_end(animate=False)

    async def _show_error_message(self, content: str) -> None:
        await self._show_runtime_message("ERROR", content)

    async def _show_success_message(self, content: str) -> None:
        await self._show_runtime_message("INFO", content)

    async def _show_runtime_message(self, level: str, content: str) -> None:
        from linhai.cli.app import CLIApp

        cli_app = self.group_chat.get_members("cli_app", CLIApp)
        assert cli_app is not None

        container = cli_app.query_one("#chat-container")
        widget = RuntimeMessageWidget(level=level, content=content)
        container.mount(widget)

        if cli_app.should_auto_scroll():
            container.scroll_end(animate=False)

    async def _handle_queue_command(self, message_text: str) -> bool:
        """处理/queue命令，将消息加入排队列表。"""
        from linhai.agent import Agent
        from linhai.llm import UserMessage

        agent = self.group_chat.get_members("agent", Agent)
        if agent is None:
            await self._show_error_message("无法获取agent实例")
            return True

        queue_content = message_text.removeprefix("/queue").strip()
        if not queue_content:
            await self._show_error_message("用法: /queue <消息内容>")
            return True

        queued_msg = UserMessage(message=queue_content)
        agent.queued_messages.append(queued_msg)

        await self._show_success_message("消息已加入排队列表，将在下次回答后处理")
        return True

    async def _handle_subagent_start_command(self) -> bool:
        """处理/subagent_start命令，手动启动git diff reviewer。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)
        if agent is None:
            await self._show_error_message("无法获取agent实例")
            return True

        await agent.handle_subagent_start_command()
        return True

    async def _handle_quit_command(self) -> bool:
        """处理/quit和/exit命令，发送退出信号。"""
        await self.group_chat.send("exit_signal", {"return_code": 0})
        return True

    async def _handle_help_command(self) -> bool:
        """处理/help命令，显示帮助信息。"""
        help_text = """可用命令:
/queue <消息> - 将消息加入排队列表，在下次回答后处理
/todolist_list - 显示所有待办事项
/todolist_add <内容> - 添加待办事项
/todolist_delete <id> - 删除待办事项
/subagent_start - 手动启动git diff reviewer
/status - 显示当前状态信息
/help - 显示此帮助信息
/quit, /exit - 退出程序
@<模型名> - 切换底层LLM模型

上下文工具:
/context_garbage_clean - 清理大消息
/context_thanox - 随机删除一半消息"""

        await self._show_runtime_message("INFO", help_text)
        return True

    async def _handle_status_command(self) -> bool:
        """处理/status命令，显示状态信息。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)
        if agent is None:
            await self._show_error_message("无法获取agent实例")
            return True

        llm_name, _llm = agent.get_current_llm_info()
        threshold_info = agent.get_threshold_info()

        status_lines = [f"当前LLM: {llm_name}", f"当前状态: {agent.state}"]

        if threshold_info:
            usage_percent = threshold_info["usage_ratio"] * 100
            status_lines.append(
                f"Token使用: {threshold_info['used_tokens']}/{threshold_info['hard_limit']} ({usage_percent:.1f}%)"
            )

        await self._show_runtime_message("INFO", "\n".join(status_lines))
        return True

    async def _handle_switch_model(self, model_name: str) -> bool:
        """处理@切换模型命令。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)
        if agent is None:
            await self._show_error_message("无法获取agent实例")
            return True

        if model_name in agent.llm_names:
            agent.current_llm_index = agent.llm_names.index(model_name)
            await self._show_success_message(f"已将底层LLM切换为 {model_name!r}")
        else:
            await self._show_error_message(
                f"错误：LLM名称 {model_name!r} 不存在。可用的LLM包括: {', '.join(agent.llm_names)}"
            )

        return True

    async def _handle_context_tool_command(self, message_text: str) -> bool:
        """处理上下文工具命令：/context_garbage_clean 和 /context_thanox。"""
        parsed_input = parse_user_input(message_text)
        if not parsed_input.command:
            await self._show_error_message("错误：无法解析命令")
            return True

        supported_commands = ["context_garbage_clean", "context_thanox"]
        if parsed_input.command not in supported_commands:
            await self._show_error_message(
                f"错误：不支持的命令 '{parsed_input.command}'，支持的命令有: {', '.join(supported_commands)}"
            )
            return True

        from linhai.agent import Agent
        from linhai.llm import ToolCallMessage

        agent = self.group_chat.get_members("agent", Agent)
        if agent is None:
            await self._show_error_message("无法获取agent实例")
            return True

        await self._show_success_message(f"正在执行命令: {parsed_input.command}")

        tool_call = ToolCallMessage(
            function_name=parsed_input.command,
            function_arguments={},
            assert_success=False,  
            with_secret=[],
        )

        early_return = await agent.toolcall_processor.call_tool(tool_call, tool_index=1)

        if not early_return:
            await self._show_success_message(f"命令{parsed_input.command}执行成功")

            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO",
                    content=f"上下文工具命令执行成功: {parsed_input.command}",
                ),
            )

        return True
