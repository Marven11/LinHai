"""测试Agent创建模块"""

import unittest

from pathlib import Path
from unittest.mock import Mock, patch

from linhai.agent.create import (
    create_agent_from_config,
    _create_llm_instances,
    _create_agent_context,
    _create_tool_manager,
    _create_init_messages,
)
from linhai.group_chat import GroupChat
from linhai.config import AgentConfig


class TestCreateAgent(unittest.TestCase):
    """测试Agent创建功能"""

    def setUp(self):
        """测试前置设置"""
        self.group_chat = Mock(spec=GroupChat)
        self.config_path = Path("test_config.toml")

    @patch('linhai.agent.create._create_llm_instances')
    @patch('linhai.agent.create._create_agent_context')
    @patch('linhai.agent.create._create_tool_manager')
    @patch('linhai.agent.create._create_init_messages')
    @patch('linhai.agent.main.Agent')
    def test_create_agent_success(self, mock_agent, mock_init_messages, mock_tool_manager, 
                                      mock_agent_context, mock_llm_instances):
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
            "compatibility": "openai"
        }
        
        mock_config.llm = [mock_llm_config]
        mock_config.agent = Mock()
        mock_config.tools = Mock()
        mock_config.memory = Mock()
        mock_config.memory.file_path = "memory.md"
        mock_config.subagent = Mock()
        mock_config.cli = Mock()

        from linhai.llm import OpenAi
        mock_llm = Mock(spec=OpenAi)
        mock_llm.model = 'test-model'
        mock_llm.token_limit = 1000
        mock_llm.compatibility = 'openai'
        mock_llm_instances.return_value = [mock_llm]  # type: ignore
        mock_agent_context.return_value = {
            'system_prompt': 'test_prompt',
            'llms': [Mock()],
            'llm_names': ['test_llm'],
            'current_llm_index': 0,
            'compress_threshold_hard': 0.8,
            'compress_threshold_soft': 0.5,
            'enable_directory_change_detection': False,
        }
        mock_tool_manager.return_value = Mock()
        mock_init_messages.return_value = [Mock()]
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance

        import asyncio
        result = asyncio.run(create_agent_from_config(self.group_chat, mock_config))

        mock_llm_instances.assert_called_once()
        mock_agent_context.assert_called_once()
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
            "compatibility": "openai"
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
            "compatibility": "openai"
        }
        
        mock_config.llm = [mock_llm_config1, mock_llm_config2]
        mock_config.agent = Mock()
        mock_config.tools = Mock()
        mock_config.memory = Mock()
        mock_config.memory.file_path = "memory.md"
        mock_config.subagent = Mock()
        mock_config.cli = Mock()

        with patch('linhai.agent.create._create_llm_instances') as mock_llm_instances, \
             patch('linhai.agent.create._create_agent_context') as mock_agent_context, \
             patch('linhai.agent.create._create_tool_manager') as mock_tool_manager, \
             patch('linhai.agent.create._create_init_messages') as mock_init_messages, \
             patch('linhai.agent.main.Agent') as mock_agent:

            from linhai.llm import OpenAi
            mock_llm = Mock(spec=OpenAi)
            mock_llm.model = 'test-model'
            mock_llm.token_limit = 1000
            mock_llm.compatibility = 'openai'
            mock_llm_instances.return_value = [mock_llm, mock_llm]  # type: ignore
            mock_agent_context.return_value = {
                'system_prompt': 'test_prompt',
                'llms': [Mock(), Mock()],
                'llm_names': ['llm1', 'llm2'],
                'current_llm_index': 1,
                'compress_threshold_hard': 0.8,
                'compress_threshold_soft': 0.5,
                'enable_directory_change_detection': False,
            }
            mock_tool_manager.return_value = Mock()
            mock_init_messages.return_value = [Mock()]
            mock_agent.return_value = Mock()

            import asyncio
            asyncio.run(create_agent_from_config(self.group_chat, mock_config, 'llm2'))

            call_args = mock_agent_context.call_args
            self.assertEqual(call_args[1]['llm_name'], 'llm2')


class TestCreateLLMInstances(unittest.TestCase):
    """测试LLM实例创建功能"""

    def test_create_llm_instances(self):
        """测试创建LLM实例"""
        llm_configs = [
            Mock(
                api_key='test_key',
                base_url='http://test.com',
                model='test-model',
                model_dump=Mock(return_value={
                    'client_options': {},
                    'completion_options': {'temperature': 0.7},
                    'token_limit': 1000,
                    'compatibility': 'openai'
                })
            )
        ]

        import asyncio
        mock_group_chat = Mock()
        result = asyncio.run(_create_llm_instances(llm_configs, mock_group_chat))

        self.assertEqual(len(result), 1)
        llm = result[0]
        self.assertEqual(llm.model, 'test-model')  # type: ignore
        self.assertEqual(llm.token_limit, 1000)  # type: ignore
        self.assertEqual(llm.compatibility, 'openai')  # type: ignore


class TestCreateAgentContext(unittest.TestCase):
    """测试Agent上下文创建功能"""

    def test_create_agent_context_default(self):
        """测试创建默认Agent上下文"""
        llms = [Mock()]
        llm_names = ['test_llm']
        agent_config = AgentConfig()

        import asyncio
        result = asyncio.run(_create_agent_context(
            llms=llms,  # type: ignore
            llm_names=llm_names,
            llm_name=None,
            agent_config=agent_config,
        ))

        self.assertEqual(result['llms'], llms)
        self.assertEqual(result['llm_names'], llm_names)
        self.assertEqual(result['current_llm_index'], 0)
        self.assertEqual(result['compress_threshold_hard'], 0.8)
        self.assertEqual(result['compress_threshold_soft'], 0.5)

    def test_create_agent_context_with_llm_name(self):
        """测试指定LLM名称创建Agent上下文"""
        llms = [Mock(), Mock()]
        llm_names = ['llm1', 'llm2']
        agent_config = AgentConfig()

        import asyncio
        result = asyncio.run(_create_agent_context(
            llms=llms,  # type: ignore
            llm_names=llm_names,
            llm_name='llm2',
            agent_config=agent_config,
        ))

        self.assertEqual(result['current_llm_index'], 1)

    def test_create_agent_context_invalid_llm_name(self):
        """测试无效LLM名称抛出异常"""
        llms = [Mock()]
        llm_names = ['llm1']
        agent_config = AgentConfig()

        import asyncio
        with self.assertRaises(ValueError):
            asyncio.run(_create_agent_context(
                llms=llms,  # type: ignore
                llm_names=llm_names,
                llm_name='invalid_llm',
                agent_config=agent_config,
            ))


class TestCreateToolManager(unittest.TestCase):
    """测试ToolManager创建功能"""

    def test_create_tool_manager(self):
        """测试创建ToolManager"""
        group_chat = Mock()
        config = Mock()
        mcp_config = []
        mcp_basedir = Path('.')

        import asyncio
        result = asyncio.run(_create_tool_manager(group_chat, config, mcp_config, mcp_basedir))

        self.assertIsNotNone(result)


class TestCreateInitMessages(unittest.TestCase):
    """测试初始化消息创建功能"""

    @patch('linhai.agent.create.GlobalMemory')
    @patch('linhai.agent.create.SystemMessage')
    @patch('linhai.agent.create.Path')
    def test_create_init_messages(self, mock_path, mock_system_message, mock_global_memory):
        """测试创建初始化消息"""
        group_chat = Mock()
        system_prompt = 'test_prompt'
        memory_file_path = Path('memory.md')

        mock_path.return_value.exists.return_value = True
        mock_system_message.return_value = Mock()
        mock_global_memory.return_value = Mock()

        import asyncio
        result = asyncio.run(_create_init_messages(group_chat, system_prompt, memory_file_path))

        self.assertGreater(len(result), 0)
        mock_system_message.assert_called_once()
        mock_global_memory.assert_called()


if __name__ == '__main__':
    unittest.main()