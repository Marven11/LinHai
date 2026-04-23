"""测试 _split_and_save_large_output 函数，验证固定分割成3块的规则。"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from linhai.utils.tokenizer import get_cl100k_base_tokenizer


class TestSplitAndSaveLargeOutput(unittest.TestCase):
    """测试 _split_and_save_large_output 函数。"""

    def setUp(self):
        """设置测试环境。"""
        self.temp_dir = tempfile.mkdtemp()
        self.conversation_dir = Path(self.temp_dir)

        self.mock_registry = Mock()
        self.mock_registry.get_member_typechecked = Mock(
            return_value=self.conversation_dir
        )

    def tearDown(self):
        """清理测试环境。"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_toolcall_instance(self):
        """创建AgentToolcall实例用于测试。"""
        from linhai.agent.toolcall import AgentToolcall

        mock_llm_manager = Mock()
        mock_llm = Mock()
        mock_llm.get_name = Mock(return_value="test_llm")
        mock_llm.get_token_limit = Mock(return_value=65536)
        mock_llm_manager.llms = [mock_llm]
        mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)

        def get_member_typechecked_side_effect(name, t):
            members = {
                "conversation_folder": self.conversation_dir,
                "llm_manager": mock_llm_manager,
            }
            return members[name]

        self.mock_registry.get_member_typechecked = Mock(
            side_effect=get_member_typechecked_side_effect
        )

        toolcall = AgentToolcall(self.mock_registry)
        return toolcall

    def test_split_into_three_parts(self):
        """验证内容被固定分割成3块。"""
        toolcall = self._create_toolcall_instance()

        text = "hello world " * 1000

        result = toolcall._split_and_save_large_output(
            result_content=text,
            token_count=3000,
            tool_name="test_tool",
            single_tool_limit=10000,
        )

        long_toolcall_dir = self.conversation_dir / "long_toolcall"
        files = list(long_toolcall_dir.glob("*.txt"))
        self.assertEqual(len(files), 3, f"应该生成3个文件，实际生成了{len(files)}个")

        self.assertIn("已分割保存到 3 个文件", str(result))

    def test_split_content_distribution(self):
        """验证内容被均匀分割到3个部分。"""
        tokenizer = get_cl100k_base_tokenizer()
        toolcall = self._create_toolcall_instance()

        text = "a" * 3000
        token_count = len(tokenizer.encode(text))

        toolcall._split_and_save_large_output(
            result_content=text,
            token_count=token_count,
            tool_name="test_tool",
            single_tool_limit=5000,
        )

        long_toolcall_dir = self.conversation_dir / "long_toolcall"
        files = sorted(long_toolcall_dir.glob("*.txt"))

        total_content = ""
        for f in files:
            total_content += f.read_text(encoding="utf-8")

        self.assertEqual(total_content, text, "所有部分的内容加起来应该等于原始内容")

    def test_split_with_small_content(self):
        """验证即使内容较小，仍然分割成3块。"""
        toolcall = self._create_toolcall_instance()

        text = "small content"

        toolcall._split_and_save_large_output(
            result_content=text,
            token_count=10,
            tool_name="test_tool",
            single_tool_limit=100000,
        )

        long_toolcall_dir = self.conversation_dir / "long_toolcall"
        files = list(long_toolcall_dir.glob("*.txt"))
        self.assertEqual(len(files), 3, "即使内容较小，也应该生成3个文件")


if __name__ == "__main__":
    unittest.main()
