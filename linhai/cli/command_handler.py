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
        if message_text.startswith("/todolist_list"):
            return await self._handle_todolist_list()

        if message_text.startswith("/todolist_add"):
            return await self._handle_todolist_add(message_text)

        if message_text.startswith("/todolist_delete"):
            return await self._handle_todolist_delete(message_text)

        if message_text.startswith("/context_garbage_clean") or message_text.startswith(
            "/context_thanox"
        ):
            return await self._handle_context_tool_command(message_text)

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

    async def _handle_context_tool_command(self, message_text: str) -> bool:
        """处理上下文工具命令：/context_garbage_clean 和 /context_thanox。"""
        # 解析命令和参数
        parsed_input = parse_user_input(message_text)
        if not parsed_input.command:
            await self._show_error_message("错误：无法解析命令")
            return True

        # 验证命令是否受支持
        supported_commands = ["context_garbage_clean", "context_thanox"]
        if parsed_input.command not in supported_commands:
            await self._show_error_message(
                f"错误：不支持的命令 '{parsed_input.command}'，支持的命令有: {', '.join(supported_commands)}"
            )
            return True

        # 获取agent实例（需要tool_manager等组件）
        from linhai.agent import Agent
        from linhai.llm import ToolCallMessage

        agent = self.group_chat.get_members("agent", Agent)
        if agent is None:
            await self._show_error_message("无法获取agent实例")
            return True

        # 显示命令执行开始消息
        await self._show_success_message(f"正在执行命令: {parsed_input.command}")

        # 创建工具调用消息（不传递参数，因为工具定义已不带参数）
        tool_call = ToolCallMessage(
            function_name=parsed_input.command,
            function_arguments={},
            assert_success=False,  # 命令工具调用失败不中断后续流程
            with_secret=[],
        )

        # 通过agent的toolcall_processor执行工具调用，确保完整的生命周期管理
        early_return = await agent.toolcall_processor.call_tool(tool_call)

        if not early_return:
            # 添加成功执行反馈（失败情况已在call_tool中处理）
            await self._show_success_message(f"命令{parsed_input.command}执行成功")

            # 记录成功到日志
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO",
                    content=f"上下文工具命令执行成功: {parsed_input.command}",
                ),
            )

        return True
