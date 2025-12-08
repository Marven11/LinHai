"""Command handler for CLI commands that should not be sent to agent."""

from linhai.group_chat import GroupChat
from linhai.tool.general import TodolistManager
from linhai.cli.components import TodolistWidget, RuntimeMessageWidget
from linhai.utils import CliRuntimeNotice


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
