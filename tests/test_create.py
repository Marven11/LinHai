"""测试Agent创建模块"""

import unittest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from linhai.agent.create import (
    create_agent,
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

    @patch('linhai.agent.create.load_config')
    @patch('linhai.agent.create._create_llm_instances')
    @patch('linhai.agent.create._create_agent_context')
    @patch('linhai.agent.create._create_tool_manager')
    @patch('linhai.agent.create._create_init_messages')
    @patch('linhai.agent.main.Agent')
    def test_create_agent_success(self, mock_agent, mock_init_messages, mock_tool_manager, 
                                      mock_agent_context, mock_llm_instances, mock_load_config):
        """测试成功创建Agent"""
        # 模拟配置
        mock_config = Mock()
        mock_config.llm = [Mock(name='test_llm')]
        mock_config.agent = Mock()
        mock_config.agent.tool_confirmation = {'test_tool': True}
        mock_config.tools = Mock()
        mock_config.memory = Mock()
        mock_config.memory.file_path = 'memory.md'
        mock_load_config.return_value = mock_config

        # 模拟返回值
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
            'tool_confirmation': {'test_tool': True},
            'enable_directory_change_detection': False,
        }
        mock_tool_manager.return_value = Mock()
        mock_init_messages.return_value = [Mock()]
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance

        # 调用函数
        import asyncio
        result = asyncio.run(create_agent(self.group_chat, self.config_path))

        # 验证调用
        mock_load_config.assert_called_once_with(self.config_path)
        mock_llm_instances.assert_called_once_with(mock_config.llm)
        mock_agent_context.assert_called_once()
        mock_tool_manager.assert_called_once()
        mock_init_messages.assert_called_once()
        mock_agent.assert_called_once()
        self.assertEqual(result, mock_agent_instance)

    @patch('linhai.agent.create.load_config')
    def test_create_agent_with_llm_name(self, mock_load_config):
        """测试指定LLM名称创建Agent"""
        mock_config = Mock()
        mock_config.llm = [Mock(name='llm1'), Mock(name='llm2')]
        mock_config.agent = Mock()
        mock_config.agent.tool_confirmation = {}
        mock_config.tools = Mock()
        mock_config.memory = Mock()
        mock_config.memory.file_path = 'memory.md'
        mock_load_config.return_value = mock_config

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
                'tool_confirmation': {},
                'enable_directory_change_detection': False,
            }
            mock_tool_manager.return_value = Mock()
            mock_init_messages.return_value = [Mock()]
            mock_agent.return_value = Mock()

            # 调用函数指定LLM名称
            import asyncio
            asyncio.run(create_agent(self.group_chat, self.config_path, 'llm2'))

            # 验证agent_context调用包含正确的llm_name
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
        result = asyncio.run(_create_llm_instances(llm_configs))

        self.assertEqual(len(result), 1)
        llm = result[0]
        # 检查OpenAI实例的属性
        self.assertEqual(llm.model, 'test-model')  # type: ignore
        self.assertEqual(llm.token_limit, 1000)  # type: ignore
        self.assertEqual(llm.compatibility, 'openai')  # type: ignore


class TestCreateAgentContext(unittest.TestCase):
    """测试Agent上下文创建功能"""

    def test_create_agent_context_default(self):
        """测试创建默认Agent上下文"""
        llms = [Mock()]
        llm_names = ['test_llm']
        tool_confirmation_config = {'test_tool': True}
        agent_config = AgentConfig()

        import asyncio
        result = asyncio.run(_create_agent_context(
            llms=llms,  # type: ignore
            llm_names=llm_names,
            llm_name=None,
            tool_confirmation_config=tool_confirmation_config,
            agent_config=agent_config,
        ))

        self.assertEqual(result['llms'], llms)
        self.assertEqual(result['llm_names'], llm_names)
        self.assertEqual(result['current_llm_index'], 0)
        # 检查tool_confirmation配置
        self.assertEqual(result.get('tool_confirmation'), tool_confirmation_config)
        self.assertEqual(result['compress_threshold_hard'], 0.8)
        self.assertEqual(result['compress_threshold_soft'], 0.5)

    def test_create_agent_context_with_llm_name(self):
        """测试指定LLM名称创建Agent上下文"""
        llms = [Mock(), Mock()]
        llm_names = ['llm1', 'llm2']
        tool_confirmation_config = {}
        agent_config = AgentConfig()

        import asyncio
        result = asyncio.run(_create_agent_context(
            llms=llms,  # type: ignore
            llm_names=llm_names,
            llm_name='llm2',
            tool_confirmation_config=tool_confirmation_config,
            agent_config=agent_config,
        ))

        self.assertEqual(result['current_llm_index'], 1)

    def test_create_agent_context_invalid_llm_name(self):
        """测试无效LLM名称抛出异常"""
        llms = [Mock()]
        llm_names = ['llm1']
        tool_confirmation_config = {}
        agent_config = AgentConfig()

        import asyncio
        with self.assertRaises(ValueError):
            asyncio.run(_create_agent_context(
                llms=llms,  # type: ignore
                llm_names=llm_names,
                llm_name='invalid_llm',
                tool_confirmation_config=tool_confirmation_config,
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

        # 模拟文件存在
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