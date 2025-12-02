"""Todolist系统测试。"""

import unittest
from unittest.mock import Mock
from linhai.tool.tools.todolist import TodolistManager
from linhai.tool.base import ToolSet, ToolArgInfo


class TestTodolistManager(unittest.TestCase):
    """测试TodolistManager类。"""

    def setUp(self):
        """设置测试环境。"""
        self.mock_group_chat = Mock()
        self.manager = TodolistManager(self.mock_group_chat)

    def test_add_todolist(self):
        """测试添加todolist。"""
        content = "测试todolist内容"
        todolist_id = self.manager.add_todolist(content)
        
        self.assertIsNotNone(todolist_id)
        self.assertIn(todolist_id, self.manager.todolists)
        self.assertEqual(self.manager.todolists[todolist_id], content)

    def test_list_todolists_empty(self):
        """测试空todolist列表。"""
        todolists = self.manager.list_todolists()
        self.assertEqual(todolists, [])

    def test_list_todolists_with_items(self):
        """测试有内容的todolist列表。"""
        content1 = "测试内容1"
        content2 = "测试内容2"
        
        id1 = self.manager.add_todolist(content1)
        id2 = self.manager.add_todolist(content2)
        
        todolists = self.manager.list_todolists()
        
        self.assertEqual(len(todolists), 2)
        expected_dict1 = {"id": id1, "content": content1}
        expected_dict2 = {"id": id2, "content": content2}
        self.assertIn(expected_dict1, todolists)
        self.assertIn(expected_dict2, todolists)

    def test_delete_todolist_success(self):
        """测试成功删除todolist。"""
        content = "要删除的内容"
        todolist_id = self.manager.add_todolist(content)
        
        self.manager.delete_todolist(todolist_id)
        self.assertNotIn(todolist_id, self.manager.todolists)

    def test_delete_todolist_failure(self):
        """测试删除不存在的todolist。"""
        result = self.manager.delete_todolist("不存在的ID")
        self.assertIn("错误：Todolist ID 不存在的ID 不存在", result)




class TestAgentTodolistToolset(unittest.TestCase):
    """测试Agent的todolist工具集。"""

    def setUp(self):
        """设置测试环境。"""
        self.mock_group_chat = Mock()
        self.manager = TodolistManager(self.mock_group_chat)
        self.toolset = ToolSet()
        
        @self.toolset.register_tool(
            name="todolist_add",
            desc="添加todolist",
            args={
                "content": ToolArgInfo(desc="todolist内容", type="str"),
            },
            required_args=["content"],
        )
        def todolist_add(content: str) -> str:
            """添加todolist。"""
            todolist_id = self.manager.add_todolist(content)
            return f"成功添加todolist，ID: {todolist_id}"

        @self.toolset.register_tool(
            name="todolist_list",
            desc="列出所有todolist",
            args={},
            required_args=[],
        )
        def todolist_list() -> str:
            """列出所有todolist。"""
            todolists = self.manager.list_todolists()
            if not todolists:
                return "当前没有todolist。"
            return "\n".join(f"{item['id']}: {item['content']}" for item in todolists)

    def test_todolist_add_tool(self):
        """测试agent的todolist_add工具。"""
        content = "测试内容"
        result = self.toolset.get_tool("todolist_add")(content)
        
        self.assertIn("成功添加todolist，ID:", result)
        self.assertEqual(len(self.manager.todolists), 1)

    def test_todolist_list_tool_empty(self):
        """测试agent的todolist_list工具（空列表）。"""
        result = self.toolset.get_tool("todolist_list")()
        self.assertEqual(result, "当前没有todolist。")

    def test_todolist_list_tool_with_items(self):
        """测试agent的todolist_list工具（有内容）。"""
        content = "测试内容"
        todolist_id = self.manager.add_todolist(content)
        
        result = self.toolset.get_tool("todolist_list")()
        
        self.assertIn(f"{todolist_id}: {content}", result)
        self.assertNotIn("当前todolist:", result)

    def test_agent_toolset_has_no_delete_tool(self):
        """测试agent工具集没有删除工具。"""
        with self.assertRaises(ValueError):
            self.toolset.get_tool("todolist_delete")


class TestSubagentTodolistToolset(unittest.TestCase):
    """测试SubAgent的todolist工具集。"""

    def setUp(self):
        """设置测试环境。"""
        self.mock_group_chat = Mock()
        self.manager = TodolistManager(self.mock_group_chat)
        self.toolset = ToolSet()
        
        @self.toolset.register_tool(
            name="todolist_add",
            desc="添加todolist",
            args={
                "content": ToolArgInfo(desc="todolist内容", type="str"),
            },
            required_args=["content"],
        )
        def todolist_add(content: str) -> str:
            """添加todolist。"""
            todolist_id = self.manager.add_todolist(content)
            return f"成功添加todolist，ID: {todolist_id}"

        @self.toolset.register_tool(
            name="todolist_list",
            desc="列出所有todolist",
            args={},
            required_args=[],
        )
        def todolist_list() -> str:
            """列出所有todolist。"""
            todolists = self.manager.list_todolists()
            if not todolists:
                return "当前没有todolist。"
            return "\n".join(f"{item['id']}: {item['content']}" for item in todolists)

        @self.toolset.register_tool(
            name="todolist_delete",
            desc="根据ID删除todolist",
            args={
                "todolist_id": ToolArgInfo(desc="要删除的todolist ID", type="str"),
            },
            required_args=["todolist_id"],
        )
        def todolist_delete(todolist_id: str) -> str:
            """根据ID删除todolist。"""
            result = self.manager.delete_todolist(todolist_id)
            return result



    def test_todolist_add_tool(self):
        """测试subagent的todolist_add工具。"""
        content = "测试内容"
        result = self.toolset.get_tool("todolist_add")(content)
        
        self.assertIn("成功添加todolist，ID:", result)
        self.assertEqual(len(self.manager.todolists), 1)

    def test_todolist_list_tool_empty(self):
        """测试subagent的todolist_list工具（空列表）。"""
        result = self.toolset.get_tool("todolist_list")()
        self.assertEqual(result, "当前没有todolist。")

    def test_todolist_list_tool_with_items(self):
        """测试subagent的todolist_list工具（有内容）。"""
        content = "测试内容"
        todolist_id = self.manager.add_todolist(content)
        
        result = self.toolset.get_tool("todolist_list")()
        
        self.assertIn(f"{todolist_id}: {content}", result)
        self.assertNotIn("当前todolist:", result)

    def test_todolist_delete_tool_success(self):
        """测试subagent的todolist_delete工具（成功删除）。"""
        content = "要删除的内容"
        todolist_id = self.manager.add_todolist(content)
        
        result = self.toolset.get_tool("todolist_delete")(todolist_id)
        
        self.assertIn("成功删除todolist:", result)
        self.assertEqual(len(self.manager.todolists), 0)

    def test_todolist_delete_tool_failure(self):
        """测试subagent的todolist_delete工具（删除失败）。"""
        result = self.toolset.get_tool("todolist_delete")("不存在的ID")
        self.assertIn("错误：Todolist ID 不存在的ID 不存在", result)


if __name__ == "__main__":
    unittest.main()