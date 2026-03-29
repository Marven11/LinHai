"""工具调用冲突系统的单元测试"""

import unittest
from unittest.mock import Mock
from linhai.agent.toolcall import AgentToolcall


class TestToolConflict(unittest.TestCase):
    """测试工具调用冲突系统"""

    def setUp(self):
        """设置测试环境"""
        self.mock_agent = Mock()
        self.mock_agent.state = "working"
        self.mock_agent.message_processor = Mock()
        self.mock_agent.message_processor.get_messages.return_value = []
        self.mock_agent.compress_tool_called_in_last_response = False

        # 模拟llm_manager
        self.mock_llm_manager = Mock()
        # 创建模拟的LLM对象
        mock_llm = Mock()
        mock_llm.get_name = Mock(return_value="test_llm")
        self.mock_llm_manager.llms = [mock_llm]
        self.mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)
        self.mock_agent.llm_manager = self.mock_llm_manager

        self.mock_tool_manager = Mock()
        self.mock_tool_manager.toolsets = []

        self.mock_registry = Mock()
        self.mock_registry.get_member_typechecked.return_value = self.mock_tool_manager

        self.mock_context = {"llms": [], "llm_names": [], "current_llm_index": 0}

        self.mock_agent.registry = self.mock_registry
        self.mock_agent.context = self.mock_context

        self.toolcall_processor = AgentToolcall(self.mock_agent)

    def test_start_new_tool_call_round(self):
        """测试开始新一轮工具调用"""
        self.toolcall_processor.called_tools_in_round = ["read_file", "write_file"]

        self.toolcall_processor.start_new_tool_call_round()

        self.assertEqual(self.toolcall_processor.called_tools_in_round, [])

    def test_check_tool_conflict_no_tools(self):
        """测试没有工具时的冲突检查"""
        result = self.toolcall_processor._check_tool_conflict("read_file")
        self.assertFalse(result)

    def test_check_tool_conflict_no_conflict_fixed(self):
        """测试无冲突的工具调用（修复版本）"""
        mock_toolset = Mock()
        mock_toolset.has_tool.return_value = True
        mock_toolset.get_tools.return_value = {
            "read_file": {"name": "read_file", "conflict_with": ["write_file"]},
            "list_files": {"name": "list_files", "conflict_with": []},
        }
        self.mock_tool_manager.toolsets = [mock_toolset]

        self.toolcall_processor.called_tools_in_round = ["list_files"]

        result = self.toolcall_processor._check_tool_conflict("read_file")
        self.assertFalse(result)

    def test_check_tool_conflict_with_conflict_fixed(self):
        """测试有冲突的工具调用（修复版本）

        注意：根据需求，读取工具可以在修改工具后调用，因此即使read_file的conflict_with包含write_file，
        在已调用write_file后调用read_file也不应该视为冲突。
        """
        mock_toolset = Mock()
        mock_toolset.has_tool.return_value = True
        mock_toolset.get_tools.return_value = {
            "read_file": {"name": "read_file", "conflict_with": []},
            "write_file": {"name": "write_file", "conflict_with": ["read_file"]},
        }
        self.mock_tool_manager.toolsets = [mock_toolset]

        self.toolcall_processor.called_tools_in_round = ["write_file"]

        result = self.toolcall_processor._check_tool_conflict("read_file")
        # 读取工具可以在修改工具后调用，所以不应该有冲突
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
