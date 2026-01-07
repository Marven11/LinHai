"""测试Agent创建模块"""

import asyncio
import unittest

from pathlib import Path
from unittest.mock import Mock, patch

from linhai.agent.create import (
    create_agent_from_config,
    _create_llm_instances,
    _create_tool_manager,
    _create_init_messages,
)
from linhai.agent.create import create_agent_build_context
from linhai.group_chat import GroupChat
from linhai.config import AgentConfig


class TestCreateAgent(unittest.TestCase):
    """测试Agent创建功能"""

    def setUp(self):
        """测试前置设置"""
        self.group_chat = Mock(spec=GroupChat)
        self.config_path = Path("test_config.toml")

    @patch("linhai.agent.create._create_llm_instances")
    @patch("linhai.agent.create._create_tool_manager")
    @patch("linhai.agent.create._create_init_messages")
    @patch("linhai.agent.main.Agent")
    def test_create_agent_success(
        self,
        mock_agent,
        mock_init_messages,
        mock_tool_manager,
        mock_llm_instances,
    ):
        """测试成功创建Agent"""
        mock_config = Mock()
        mock_llm_config = Mock()
        mock_llm_config.name = "test_llm"
        mock_llm_config.base_url = "http://test.com"
        mock_llm_config.api_key = "test_key"
        mock_llm_config.model = "test-model"
        mock_llm_config.model_dump.return_value = {
            "client_options": {},
            "completion_options": {},
            "token_limit": 1000,
            "compatibility": "openai",
        }

        mock_config.llm = [mock_llm_config]
        mock_config.agent = Mock()
        mock_config.tools = Mock()
        mock_config.tools.secret.config_path = ""
        mock_config.memory = Mock()
        mock_config.memory.file_path = "memory.md"
        mock_config.subagent = Mock()
        mock_config.cli = Mock()

        from linhai.llm import OpenAi

        mock_llm = Mock(spec=OpenAi)
        mock_llm.model = "test-model"
        mock_llm.token_limit = 1000
        mock_llm.compatibility = "openai"
        mock_llm_instances.return_value = [mock_llm]  # type: ignore

        mock_tool_manager.return_value = (Mock(), Mock())
        mock_init_messages.return_value = [Mock()]
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance

        import asyncio

        context = create_agent_build_context(
            group_chat=self.group_chat,
            config=mock_config,
            config_basedir=Path("."),
            llm_name="test_llm",
            git_diff_reviewer=False,
            violation_checker=False,
            checklist_path=None,
        )
        result = asyncio.run(create_agent_from_config(context))

        mock_llm_instances.assert_called_once()
        mock_tool_manager.assert_called_once()
        mock_init_messages.assert_called_once()
        mock_agent.assert_called_once()
        self.assertEqual(result, mock_agent_instance)

    def test_create_agent_with_llm_name(self):
        """测试指定LLM名称创建Agent"""
        mock_config = Mock()

        mock_llm_config1 = Mock()
        mock_llm_config1.name = "llm1"
        mock_llm_config1.base_url = "http://test1.com"
        mock_llm_config1.api_key = "test_key1"
        mock_llm_config1.model = "test-model1"
        mock_llm_config1.model_dump.return_value = {
            "client_options": {},
            "completion_options": {},
            "token_limit": 1000,
            "compatibility": "openai",
        }

        mock_llm_config2 = Mock()
        mock_llm_config2.name = "llm2"
        mock_llm_config2.base_url = "http://test2.com"
        mock_llm_config2.api_key = "test_key2"
        mock_llm_config2.model = "test-model2"
        mock_llm_config2.model_dump.return_value = {
            "client_options": {},
            "completion_options": {},
            "token_limit": 1000,
            "compatibility": "openai",
        }

        mock_config.llm = [mock_llm_config1, mock_llm_config2]
        mock_config.agent = Mock()
        mock_config.tools = Mock()
        mock_config.tools.secret.config_path = ""
        mock_config.memory = Mock()
        mock_config.memory.file_path = "memory.md"
        mock_config.subagent = Mock()
        mock_config.cli = Mock()

        with (
            patch("linhai.agent.create._create_llm_instances") as mock_llm_instances,
            patch("linhai.agent.create._create_tool_manager") as mock_tool_manager,
            patch("linhai.agent.create._create_init_messages") as mock_init_messages,
            patch("linhai.agent.main.Agent") as mock_agent,
        ):

            from linhai.llm import OpenAi

            mock_llm = Mock(spec=OpenAi)
            mock_llm.model = "test-model"
            mock_llm.token_limit = 1000
            mock_llm.compatibility = "openai"
            mock_llm_instances.return_value = [mock_llm, mock_llm]  # type: ignore

            mock_tool_manager.return_value = (Mock(), Mock())
            mock_init_messages.return_value = [Mock()]
            mock_agent.return_value = Mock()

            import asyncio

            context = create_agent_build_context(
                group_chat=self.group_chat,
                config=mock_config,
                config_basedir=Path("."),
                llm_name="llm1",
                git_diff_reviewer=False,
                violation_checker=False,
                checklist_path=None,
            )
            asyncio.run(create_agent_from_config(context))

            # 不再检查_create_agent_context调用，因为函数已不存在


class TestCreateLLMInstances(unittest.TestCase):
    """测试LLM实例创建功能"""

    def test_create_llm_instances(self):
        """测试创建LLM实例"""
        llm_configs = [
            Mock(
                api_key="test_key",
                base_url="http://test.com",
                model="test-model",
                client_options={},
                completion_options={"temperature": 0.7},
                token_limit=1000,
                compatibility="openai",
                name="test-llm",
            )
        ]

        import asyncio

        mock_group_chat = Mock()
        context = {
            "config": Mock(llm=llm_configs),
            "group_chat": mock_group_chat,
            "llm_name": "test-llm",
            "config_basedir": Path("."),
            "git_diff_reviewer": False,
            "violation_checker": False,
            "checklist_path": None,
        }
        result = asyncio.run(_create_llm_instances(context))

        self.assertEqual(len(result), 1)
        llm = result[0]
        self.assertEqual(llm.model, "test-model")  # type: ignore
        self.assertEqual(llm.token_limit, 1000)  # type: ignore
        self.assertEqual(llm.compatibility, "openai")  # type: ignore

    def test_create_agent_context_default(self):
        """测试创建默认Agent上下文（函数已删除，测试跳过）"""
        pass
        llms = [Mock()]
        llm_names = ["test_llm"]
        agent_config = AgentConfig()

        import asyncio

        pass

    def test_create_agent_context_with_llm_name(self):
        """测试指定LLM名称创建Agent上下文（函数已删除，测试跳过）"""
        pass
        llms = [Mock(), Mock()]
        llm_names = ["llm1", "llm2"]
        agent_config = AgentConfig()

        import asyncio

        pass

    def test_create_agent_context_invalid_llm_name(self):
        """测试无效LLM名称抛出异常（函数已删除，测试跳过）"""
        pass
        llms = [Mock()]
        llm_names = ["llm1"]
        agent_config = AgentConfig()

        import asyncio

        pass


class TestCreateToolManager(unittest.TestCase):
    """测试ToolManager创建功能"""

    def test_create_tool_manager(self):
        """测试创建ToolManager"""
        group_chat = Mock()
        config = Mock()
        config.secret.config_path = ""
        config.agent = Mock(mcp=[])
        config.tools = config

        context = {
            "group_chat": group_chat,
            "config": config,
            "config_basedir": Path("."),
            "llm_name": "test-llm",
            "git_diff_reviewer": False,
            "violation_checker": False,
            "checklist_path": None,
            "tools_config": config,
        }

        _create_tool_manager(context)

        result = asyncio.run(_create_tool_manager(context))

        self.assertIsNotNone(result)


class TestCreateInitMessages(unittest.TestCase):
    """测试初始化消息创建功能"""

    @patch("linhai.agent.create.GlobalMemory")
    @patch("linhai.agent.create.SystemMessage")
    @patch("linhai.agent.create.Path")
    def test_create_init_messages(
        self, mock_path, mock_system_message, mock_global_memory
    ):
        """测试创建初始化消息"""
        group_chat = Mock()
        memory_file_path = Path("memory.md")

        mock_path.return_value.exists.return_value = True
        mock_system_message.return_value = Mock()
        mock_global_memory.return_value = Mock()

        import asyncio

        context = {
            "group_chat": group_chat,
            "config": Mock(memory=Mock(file_path=memory_file_path)),
            "config_basedir": Path("."),
            "llm_name": "test-llm",
            "git_diff_reviewer": False,
            "violation_checker": False,
            "checklist_path": None,
        }
        result = asyncio.run(_create_init_messages(context))

        self.assertGreater(len(result), 0)
        mock_system_message.assert_called_once()
        mock_global_memory.assert_called()


if __name__ == "__main__":
    unittest.main()
