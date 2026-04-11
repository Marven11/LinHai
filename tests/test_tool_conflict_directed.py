"""测试有向工具冲突逻辑。"""

import unittest
from unittest.mock import AsyncMock, MagicMock

from linhai.agent.toolcall import AgentToolcall
from linhai.base import ToolCallMessage


class TestDirectedToolConflict(unittest.TestCase):
    """测试有向工具冲突逻辑。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.lifecycle = MagicMock()
        self.agent.lifecycle.after_toolcall.trigger = AsyncMock(return_value=None)
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()

        self.tool_manager = MagicMock()
        self.tool_manager.toolsets = []
        self.tool_manager.process_tool_call = AsyncMock()

        self.mock_llm_manager = MagicMock()
        mock_llm = MagicMock()
        mock_llm.get_name = MagicMock(return_value="test_llm")
        mock_llm.get_token_limit = MagicMock(return_value=65536)
        self.mock_llm_manager.llms = [mock_llm]
        self.mock_llm_manager.get_current_llm = MagicMock(return_value=mock_llm)

        def get_member_typechecked_side_effect(name, t):
            members = {
                "tool_manager": self.tool_manager,
                "llm_manager": self.mock_llm_manager,
            }
            return members[name]

        self.mock_registry = MagicMock()
        self.mock_registry.get_member_typechecked = MagicMock(
            side_effect=get_member_typechecked_side_effect
        )

        self.toolcall = AgentToolcall(self.mock_registry)

        # 设置模拟工具定义
        self.read_file_tool = {
            "name": "read_file",
            "conflict_with": [],  # read_file不与其他工具冲突
        }
        self.write_file_tool = {
            "name": "write_file",
            "conflict_with": [
                "read_file",
                "read_file_with_sed",
            ],  # write_file不能在read_file之后调用
        }

        self.replace_file_content_tool = {
            "name": "replace_file_content",
            "conflict_with": [
                "read_file",
                "read_file_with_sed",
            ],  # replace_file_content不能在read_file之后调用
        }

    def test_read_file_can_follow_write_file(self):
        """测试read_file可以在write_file之后调用（无冲突）。"""
        # 模拟工具定义
        mock_toolset = MagicMock()
        mock_toolset.has_tool = MagicMock(side_effect=lambda name: name == "read_file")
        mock_toolset.get_tools = MagicMock(
            return_value={"read_file": self.read_file_tool}
        )
        self.tool_manager.toolsets = [mock_toolset]

        # 先调用write_file
        self.toolcall.called_tools_in_round = ["write_file"]

        # 检查read_file是否与write_file冲突
        conflict = self.toolcall._check_tool_conflict("read_file")

        # read_file的conflict_with为空，所以应该没有冲突
        self.assertIsNone(conflict, "read_file应该可以在write_file之后调用")

    def test_write_file_cannot_follow_read_file(self):
        """测试write_file不能在read_file之后调用（有冲突）。"""
        # 模拟工具定义
        mock_toolset = MagicMock()
        mock_toolset.has_tool = MagicMock(side_effect=lambda name: name == "write_file")
        mock_toolset.get_tools = MagicMock(
            return_value={"write_file": self.write_file_tool}
        )
        self.tool_manager.toolsets = [mock_toolset]

        # 先调用read_file
        self.toolcall.called_tools_in_round = ["read_file"]

        # 检查write_file是否与read_file冲突
        conflict = self.toolcall._check_tool_conflict("write_file")

        # write_file的conflict_with包含read_file，所以应该有冲突
        self.assertEqual(conflict, "read_file", "write_file不能在read_file之后调用")

    def test_replace_file_content_cannot_follow_read_file(self):
        """测试replace_file_content不能在read_file之后调用（有冲突）。"""
        # 模拟工具定义
        mock_toolset = MagicMock()
        mock_toolset.has_tool = MagicMock(
            side_effect=lambda name: name == "replace_file_content"
        )
        mock_toolset.get_tools = MagicMock(
            return_value={"replace_file_content": self.replace_file_content_tool}
        )
        self.tool_manager.toolsets = [mock_toolset]

        # 先调用read_file
        self.toolcall.called_tools_in_round = ["read_file"]

        # 检查replace_file_content是否与read_file冲突
        conflict = self.toolcall._check_tool_conflict("replace_file_content")

        # replace_file_content的conflict_with包含read_file，所以应该有冲突
        self.assertEqual(
            conflict, "read_file", "replace_file_content不能在read_file之后调用"
        )

    def test_modify_tools_can_follow_each_other(self):
        """测试修改工具之间可以互相调用（如果未在conflict_with中定义）。"""
        # 模拟工具定义
        mock_toolset = MagicMock()

        def has_tool_side_effect(name):
            return name in ["write_file", "replace_file_content"]

        mock_toolset.has_tool = MagicMock(side_effect=has_tool_side_effect)
        mock_toolset.get_tools = MagicMock(
            return_value={
                "write_file": self.write_file_tool,
                "replace_file_content": self.replace_file_content_tool,
            }
        )
        self.tool_manager.toolsets = [mock_toolset]

        # 先调用write_file
        self.toolcall.called_tools_in_round = ["write_file"]

        # 检查replace_file_content是否与write_file冲突
        # replace_file_content的conflict_with只包含read_file和read_file_with_sed，不包含write_file
        conflict = self.toolcall._check_tool_conflict("replace_file_content")

        # 应该没有冲突
        self.assertIsNone(conflict, "replace_file_content应该可以在write_file之后调用")

    def test_read_file_with_sed_same_as_read_file(self):
        """测试read_file_with_sed与read_file具有相同的冲突行为。"""
        # 模拟工具定义
        mock_toolset = MagicMock()
        mock_toolset.has_tool = MagicMock(side_effect=lambda name: name == "write_file")
        mock_toolset.get_tools = MagicMock(
            return_value={"write_file": self.write_file_tool}
        )
        self.tool_manager.toolsets = [mock_toolset]

        # 先调用read_file_with_sed
        self.toolcall.called_tools_in_round = ["read_file_with_sed"]

        # 检查write_file是否与read_file_with_sed冲突
        # write_file的conflict_with包含read_file_with_sed，所以应该有冲突
        conflict = self.toolcall._check_tool_conflict("write_file")

        self.assertEqual(
            conflict, "read_file_with_sed", "write_file不能在read_file_with_sed之后调用"
        )

    def test_no_conflict_when_tool_not_in_conflict_list(self):
        """测试当工具不在conflict_with列表中时无冲突。"""
        # 模拟工具定义
        mock_toolset = MagicMock()
        mock_toolset.has_tool = MagicMock(side_effect=lambda name: name == "list_files")
        # list_files没有定义conflict_with
        list_files_tool = {
            "name": "list_files",
            "conflict_with": None,  # None表示没有冲突
        }
        mock_toolset.get_tools = MagicMock(return_value={"list_files": list_files_tool})
        self.tool_manager.toolsets = [mock_toolset]

        # 先调用read_file
        self.toolcall.called_tools_in_round = ["read_file"]

        # 检查list_files是否与read_file冲突
        conflict = self.toolcall._check_tool_conflict("list_files")

        self.assertIsNone(conflict, "list_files应该可以在任何工具之后调用")
