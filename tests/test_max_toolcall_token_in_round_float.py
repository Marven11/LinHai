"""Test max_toolcall_token_in_round as float type."""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from linhai.agent.toolcall import AgentToolcall
from linhai.llm import ToolCallMessage
from linhai.tool.base import ToolCallResultMessage, ToolResultSuccess


class TestMaxToolcallTokenInRoundFloat(unittest.IsolatedAsyncioTestCase):
    """Test max_toolcall_token_in_round as float type."""

    def setUp(self):
        """Set up test environment."""
        self.mock_agent = Mock()
        self.mock_agent.registry = Mock()
        self.mock_agent.registry.send_if_exists = AsyncMock()

        self.mock_agent.message_processor = Mock()
        self.mock_agent.message_processor.get_messages.return_value = []
        self.mock_agent.lifecycle = Mock()
        self.mock_agent.lifecycle.trigger_after_toolcall = AsyncMock(return_value=None)
        self.mock_agent.lifecycle.trigger_before_tool_call = AsyncMock(
            return_value=None
        )

        self.mock_llm_manager = Mock()
        self.mock_llm = Mock()
        self.mock_llm.get_name = Mock(return_value="test_llm")
        self.mock_llm_manager.llms = [self.mock_llm]
        self.mock_llm_manager.get_current_llm = Mock(return_value=self.mock_llm)
        self.mock_agent.llm_manager = self.mock_llm_manager
        self.mock_agent.get_current_model = Mock(return_value=self.mock_llm)

        self.mock_tool_manager = Mock()
        self.mock_tool_manager.toolsets = []
        self.mock_agent.registry.get_member_typechecked.return_value = (
            self.mock_tool_manager
        )

        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_float_max_toolcall_token_in_round_small_llm(self):
        """Test float max_toolcall_token_in_round with small token_limit."""
        self.mock_llm.get_token_limit = Mock(return_value=10000)

        toolcall_processor = AgentToolcall(
            self.mock_agent, max_toolcall_token_in_round=0.3
        )

        self.assertEqual(toolcall_processor.max_token_limit, 3000)

    def test_float_max_toolcall_token_in_round_large_llm(self):
        """Test float max_toolcall_token_in_round with large token_limit."""
        self.mock_llm.get_token_limit = Mock(return_value=200000)

        toolcall_processor = AgentToolcall(
            self.mock_agent, max_toolcall_token_in_round=0.3
        )

        self.assertEqual(toolcall_processor.max_token_limit, 60000)

    def test_int_max_toolcall_token_in_round_static(self):
        """Test int max_toolcall_token_in_round with static value."""
        self.mock_llm.get_token_limit = Mock(return_value=100000)

        toolcall_processor = AgentToolcall(
            self.mock_agent, max_toolcall_token_in_round=15000
        )

        self.assertEqual(toolcall_processor.max_token_limit, 15000)

    def test_float_value_scales_with_token_limit(self):
        """Test that float max_toolcall_token_in_round scales with token_limit."""
        self.mock_llm.get_token_limit = Mock(return_value=10000)
        toolcall_processor_small = AgentToolcall(
            self.mock_agent, max_toolcall_token_in_round=0.3
        )

        self.assertEqual(toolcall_processor_small.max_token_limit, 3000)

        self.mock_llm.get_token_limit = Mock(return_value=200000)
        toolcall_processor_large = AgentToolcall(
            self.mock_agent, max_toolcall_token_in_round=0.3
        )

        self.assertEqual(toolcall_processor_large.max_token_limit, 60000)
        self.assertGreater(
            toolcall_processor_large.max_token_limit,
            toolcall_processor_small.max_token_limit,
        )

    def test_default_value_is_float(self):
        """Test that the default value is float (0.3)."""
        self.mock_llm.get_token_limit = Mock(return_value=100000)

        toolcall_processor = AgentToolcall(self.mock_agent)

        self.assertEqual(toolcall_processor.max_token_limit, 30000)

    def test_token_limit_none_uses_default(self):
        """Test that when token_limit is None, uses default 65536."""
        self.mock_llm.get_token_limit = Mock(return_value=None)

        toolcall_processor = AgentToolcall(
            self.mock_agent, max_toolcall_token_in_round=0.5
        )

        self.assertEqual(toolcall_processor.max_token_limit, 32768)


if __name__ == "__main__":
    unittest.main()
