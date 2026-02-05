import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import asyncio

from linhai.agent.create import create_agent_build_context
from linhai.agent.planning import PlanningPromptMessage


class TestPlanningIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_group_chat = MagicMock()
        self.mock_config = MagicMock()
        # 模拟LLM配置对象列表
        mock_llm_config = MagicMock()
        mock_llm_config.name = "test_llm"
        self.mock_config.llm = [mock_llm_config]
        self.mock_config_basedir = Path("/tmp/test_config")
        self.mock_cli_args = MagicMock()
        self.mock_cli_args.planning = False
        self.mock_cli_args.llm = None
        self.mock_cli_args.checklist = None
        
    async def test_planning_parameter_default_false(self):
        # 注意：create_agent_build_context需要llm_name参数，我们通过cli_args.llm传递
        self.mock_cli_args.llm = None
        context = create_agent_build_context(
            group_chat=self.mock_group_chat,
            config=self.mock_config,
            config_basedir=self.mock_config_basedir,
            cli_args=self.mock_cli_args,
            planning=False,
        )
        
        self.assertFalse(context["planning"])
        
    async def test_planning_parameter_true(self):
        self.mock_cli_args.llm = None
        context = create_agent_build_context(
            group_chat=self.mock_group_chat,
            config=self.mock_config,
            config_basedir=self.mock_config_basedir,
            cli_args=self.mock_cli_args,
            planning=True,
        )
        
        self.assertTrue(context["planning"])
        
    async def test_create_pinned_messages_with_planning(self):
        from linhai.agent.create import _create_pinned_messages
        from linhai.agent.base import RuntimeMessage, GlobalMemory
        from linhai.llm import SystemMessage
        from linhai.llm import UserMessage, AssistantMessage
        
        # 模拟对话文件夹
        mock_conversation_folder = Path("/tmp/test_conversation")
        self.mock_group_chat.get_members = MagicMock(
            side_effect=lambda name, cls=None: {
                "conversation_folder": mock_conversation_folder
            }.get(name)
        )
        
        # 模拟消息列表
        mock_messages = [
            SystemMessage(group_chat=self.mock_group_chat),
            GlobalMemory(filepath=Path("/tmp/test_global_memory.md")),
            RuntimeMessage("User message 1"),
            AssistantMessage(message="Assistant response 1"),
        ]
        
        context = {
            "planning": True,
            "group_chat": self.mock_group_chat,
            "cli_args": self.mock_cli_args,
            "config": self.mock_config,
            "config_basedir": self.mock_config_basedir,
            "checklist_path": None,
        }
        
        # 模拟agent.message_processor.messages
        mock_agent = MagicMock()
        mock_agent.message_processor.messages = mock_messages
        
        with patch('linhai.agent.create.Agent', return_value=mock_agent):
            pinned_messages = await _create_pinned_messages(context)
        
        # 检查是否包含PlanningPromptMessage
        planning_messages = [
            msg for msg in pinned_messages 
            if isinstance(msg, PlanningPromptMessage)
        ]
        
        self.assertEqual(len(planning_messages), 1)
        planning_msg = planning_messages[0]
        
        # 检查文件夹是否正确
        expected_folder = mock_conversation_folder / "planning"
        self.assertEqual(planning_msg.planning_folder, expected_folder)
        
        # 检查文件路径
        file_paths = planning_msg.get_file_paths()
        self.assertEqual(file_paths["status"], expected_folder / "STATUS.md")
        self.assertEqual(file_paths["todolist"], expected_folder / "TODOLIST.md")
        self.assertEqual(file_paths["design"], expected_folder / "DESIGN.md")
        
        # 检查内容是否包含路径
        content = planning_msg.message
        self.assertIn(str(expected_folder), content)
        self.assertIn("STATUS.md", content)
        self.assertIn("TODOLIST.md", content)
        self.assertIn("DESIGN.md", content)
        
    async def test_create_pinned_messages_without_planning(self):
        from linhai.agent.create import _create_pinned_messages
        
        context = {
            "planning": False,
            "group_chat": self.mock_group_chat,
            "cli_args": self.mock_cli_args,
            "config": self.mock_config,
            "config_basedir": self.mock_config_basedir,
            "checklist_path": None,
        }
        
        pinned_messages = await _create_pinned_messages(context)
        
        # 检查是否不包含PlanningPromptMessage
        planning_messages = [
            msg for msg in pinned_messages 
            if isinstance(msg, PlanningPromptMessage)
        ]
        
        self.assertEqual(len(planning_messages), 0)
        

if __name__ == "__main__":
    unittest.main()