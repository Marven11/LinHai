"""测试对话历史保存功能。"""

import unittest
import tempfile
import json
import shutil
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

from linhai.agent import Agent
from linhai.llm import UserMessage, AssistantMessage, SystemMessage
from linhai.agent.base import RuntimeMessage


class TestConversationHistory(unittest.TestCase):
    """测试对话历史保存功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.temp_dir = tempfile.mkdtemp()
        self.history_dir = (
            Path(self.temp_dir) / ".local" / "share" / "linhai" / "conversations"
        )

        mock_llm = Mock()
        mock_llm.get_name = lambda: "test_llm"
        self.config = {
            "llms": [mock_llm],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 2000,
        }

        self.group_chat = Mock()
        self.group_chat.register_queue = Mock()
        self.group_chat.register_member = Mock()

        # 为SystemMessage初始化提供tool_manager
        from linhai.tool.main import ToolManager
        from linhai.agent.lifecycle import Lifecycle

        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []

        mock_lifecycle = Mock(spec=Lifecycle)
        mock_lifecycle.register_before_message_generation = Mock()
        mock_lifecycle.register_after_message_generation = Mock()
        mock_lifecycle.register_before_tool_call = Mock()

        def get_members_side_effect(member_type, _member_class=None):
            if member_type == "tool_manager":
                return mock_tool_manager
            elif member_type == "lifecycle":
                return mock_lifecycle
            raise RuntimeError(f"{member_type!r} not exists")

        self.group_chat.get_members = Mock(side_effect=get_members_side_effect)

        self.init_messages = [
            SystemMessage(
                group_chat=self.group_chat,
            ),
            UserMessage("测试用户消息"),
        ]

        # 将llms和llm_names合并为llms

        self.agent = Agent(
            llms=self.config["llms"],
            compress_threshold=self.config["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=self.init_messages,
            llm_name=self.config["llm_names"][self.config["current_llm_index"]],
        )

    def tearDown(self):
        """清理测试环境。"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("pathlib.Path.home")
    def test_save_conversation_history(self, mock_home):
        """测试保存对话历史。"""
        mock_home.return_value = Path(self.temp_dir)

        self.agent.message_processor.add_new_message(UserMessage("你好"))
        self.agent.message_processor.add_new_message(
            AssistantMessage("你好！有什么可以帮助你的？")
        )
        self.agent.message_processor.add_new_message(RuntimeMessage("测试运行时消息"))

        asyncio.run(self.agent.save_conversation_history())

        self.assertTrue(self.history_dir.exists())

        history_files = list(self.history_dir.glob("conversation_*.json"))
        self.assertEqual(len(history_files), 1)

        with open(history_files[0], "r", encoding="utf-8") as f:
            history_data = json.load(f)

        self.assertGreater(len(history_data), 0)

        for msg in history_data:
            if "role" in msg:
                self.assertIn("message", msg)
            elif "message" in msg:
                pass  # RuntimeMessage只有message字段

    @patch("pathlib.Path.home")
    def test_save_conversation_history_directory_creation(self, mock_home):
        """测试历史目录的创建。"""
        mock_home.return_value = Path(self.temp_dir)

        if self.history_dir.exists():
            shutil.rmtree(self.history_dir)

        self.assertFalse(self.history_dir.exists())

        asyncio.run(self.agent.save_conversation_history())

        self.assertTrue(self.history_dir.exists())

    @patch("pathlib.Path.home")
    def test_save_conversation_history_error_handling(self, mock_home):
        """测试保存对话历史的错误处理。"""
        mock_home.return_value = Path(self.temp_dir)

        with patch("builtins.open", side_effect=IOError("模拟IO错误")):
            # 使用assertRaises捕获RuntimeError
            with self.assertRaises(RuntimeError) as cm:
                asyncio.run(self.agent.save_conversation_history())
            # 断言异常消息
            self.assertIn("保存对话历史失败", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
