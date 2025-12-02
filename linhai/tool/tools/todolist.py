"""Todolist管理工具模块。"""

from typing import List, Dict, Optional, TypedDict

from linhai.group_chat import GroupChat
from linhai.tool.base import ToolArgInfo, ToolSet
from linhai.utils import generate_id


class TodolistItem(TypedDict):
    """Todolist项的类型定义。"""

    id: str
    content: str


class TodolistManager:

    def __init__(self, group_chat: GroupChat):
        self.todolists: Dict[str, str] = {}
        group_chat.register_member("todolist_manager", self)

    def add_todolist(self, content: str) -> str:
        if not content or not content.strip():
            raise ValueError("todolist内容不能为空")

        todolist_id = generate_id("todolist")
        self.todolists[todolist_id] = content.strip()
        return todolist_id

    def list_todolists(self) -> List[TodolistItem]:
        return [
            {"id": todolist_id, "content": content}
            for todolist_id, content in self.todolists.items()
        ]

    def get_todolist_by_id(self, todolist_id: str) -> Optional[TodolistItem]:
        if todolist_id not in self.todolists:
            return None
        return {"id": todolist_id, "content": self.todolists[todolist_id]}

    def delete_todolist(self, todolist_id: str) -> str:
        """删除todolist，返回删除结果。"""
        if todolist_id not in self.todolists:
            return f"错误：Todolist ID {todolist_id} 不存在"
        content = self.todolists[todolist_id]
        del self.todolists[todolist_id]
        return f"成功删除todolist: {todolist_id} ({content})"


def create_agent_todolist_toolset(
    todolist_manager: TodolistManager,
) -> ToolSet:
    """创建todolist管理工具集（只有添加和列出功能，供Agent使用）。"""
    toolset = ToolSet()

    @toolset.register_tool(
        name="todolist_add",
        desc="添加todolist",
        args={
            "content": ToolArgInfo(desc="todolist内容", type="str"),
        },
        required_args=["content"],
    )
    def todolist_add(content: str) -> str:
        """添加todolist。"""
        todolist_id = todolist_manager.add_todolist(content)
        return f"成功添加todolist，ID: {todolist_id}"

    @toolset.register_tool(
        name="todolist_list",
        desc="列出所有todolist",
        args={},
        required_args=[],
    )
    def todolist_list() -> str:
        """列出所有todolist。"""
        todolists = todolist_manager.list_todolists()
        if not todolists:
            return "当前没有todolist。"
        return "\n".join(f"{item['id']}: {item['content']}" for item in todolists)

    return toolset
