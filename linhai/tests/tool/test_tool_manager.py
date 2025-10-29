"""Unit tests for the ToolManager class."""

import unittest
import unittest.mock

from linhai.llm import ToolCallMessage
from linhai.tool.base import ToolArgInfo, global_tools
from linhai.tool.main import ToolManager
from linhai.group_chat import GroupChat


class TestToolManager(unittest.IsolatedAsyncioTestCase):
    """Test cases for the ToolManager class."""

    async def asyncSetUp(self):

        group_chat = GroupChat()
        self.manager = ToolManager(group_chat=group_chat, toolsets=[global_tools])

    async def test_successful_tool_call(self):
        """测试成功的工具调用"""
        mock_tool_call = ToolCallMessage(
            function_name="add_numbers", function_arguments={"a": 3, "b": 5}
        )

        # 模拟工具存在和工具调用
        with unittest.mock.patch.object(
            global_tools, "has_tool", return_value=True
        ), unittest.mock.patch(
            "linhai.tool.base.global_tools.call_tool", return_value=8
        ) as mock_call:
            result = await self.manager.process_tool_call(mock_tool_call)

            # 验证工具被正确调用
            mock_call.assert_called_once_with("add_numbers", {"a": 3, "b": 5})

            # 验证返回结果
            self.assertEqual(type(result).__name__, "ToolResultMessage")
            self.assertEqual(getattr(result, "content"), "8")

    async def test_failed_tool_call(self):
        """测试失败的工具调用"""
        mock_tool_call = ToolCallMessage(
            function_name="invalid_tool", function_arguments={}
        )

        # 模拟工具抛出异常
        with unittest.mock.patch(
            "linhai.tool.base.global_tools.call_tool",
            side_effect=ValueError("Tool not found"),
        ):
            result = await self.manager.process_tool_call(mock_tool_call)
            self.assertEqual(type(result).__name__, "ToolErrorMessage")
            self.assertEqual(getattr(result, "content"), "未找到工具: invalid_tool")

    async def test_async_tool_call(self):
        """测试异步工具调用"""

        # 创建一个模拟的异步工具
        async def mock_async_tool(arg1: int, arg2: int) -> int:
            return arg1 + arg2

        # 模拟工具存在和工具调用
        with unittest.mock.patch.object(
            global_tools, "has_tool", return_value=True
        ), unittest.mock.patch(
            "linhai.tool.base.global_tools.call_tool",
            return_value=mock_async_tool(2, 3),
        ) as mock_call:
            mock_tool_call = ToolCallMessage(
                function_name="mock_async_tool",
                function_arguments={"arg1": 2, "arg2": 3},
            )
            result = await self.manager.process_tool_call(mock_tool_call)

            # 验证工具被正确调用
            mock_call.assert_called_once_with("mock_async_tool", {"arg1": 2, "arg2": 3})

            # 验证返回结果
            self.assertEqual(type(result).__name__, "ToolResultMessage")
            self.assertEqual(getattr(result, "content"), "5")

    async def test_tool_manager_with_config(self):
        """测试ToolManager使用配置的情况"""
        from linhai.config import (
            Config,
            LLMConfig,
            MemoryConfig,
            AgentConfig,
            ToolConfig,
        )

        # 创建带配置的ToolManager，使用Pydantic模型
        config = Config(
            llm=[
                LLMConfig(
                    name="test_llm",
                    base_url="https://api.example.com",
                    api_key="test_key",
                    model="test_model",
                )
            ],
            memory=MemoryConfig(file_path="./memory.md"),
            agent=AgentConfig(
                compress_threshold_soft=30000,
                compress_threshold_hard=60000,
            ),
            tools=ToolConfig(max_output_length=1000),
        )
        from linhai.group_chat import GroupChat

        group_chat = GroupChat()
        manager_with_config = ToolManager(
            group_chat=group_chat, toolsets=[global_tools], config=config
        )

        # 模拟工具调用返回长内容
        long_content = "A" * 1001  # 超过配置的1000字符限制
        mock_tool_call = ToolCallMessage(
            function_name="test_tool", function_arguments={}
        )

        # 模拟工具存在和工具调用
        with unittest.mock.patch.object(
            global_tools, "has_tool", return_value=True
        ), unittest.mock.patch(
            "linhai.tool.base.global_tools.call_tool", return_value=long_content
        ) as mock_call:
            result = await manager_with_config.process_tool_call(mock_tool_call)

            # 验证工具被正确调用
            mock_call.assert_called_once_with("test_tool", {})

            # 验证返回的是ToolResultMessage且内容包含文件信息（因为超过了1000字符限制）
            self.assertEqual(type(result).__name__, "ToolResultMessage")
            self.assertIn("已保存到临时文件", getattr(result, "content"))

    async def test_tool_manager_with_config_no_tools(self):
        """测试ToolManager使用配置但没有tools配置的情况"""
        from linhai.config import Config, LLMConfig, MemoryConfig, AgentConfig

        # 创建带配置的ToolManager，但没有tools配置
        config = Config(
            llm=[
                LLMConfig(
                    name="test_llm",
                    base_url="https://api.example.com",
                    api_key="test_key",
                    model="test_model",
                )
            ],
            memory=MemoryConfig(file_path="./memory.md"),
            agent=AgentConfig(
                compress_threshold_soft=30000,
                compress_threshold_hard=60000,
            ),
            # 不设置tools配置
        )
        from linhai.group_chat import GroupChat

        group_chat = GroupChat()
        manager_with_config = ToolManager(
            group_chat=group_chat, toolsets=[global_tools], config=config
        )

        # 模拟工具调用返回长内容
        long_content = "A" * 50001  # 超过默认的50000字符限制
        mock_tool_call = ToolCallMessage(
            function_name="test_tool", function_arguments={}
        )

        # 模拟工具存在和工具调用
        with unittest.mock.patch.object(
            global_tools, "has_tool", return_value=True
        ), unittest.mock.patch(
            "linhai.tool.base.global_tools.call_tool", return_value=long_content
        ) as mock_call:
            result = await manager_with_config.process_tool_call(mock_tool_call)

            # 验证工具被正确调用
            mock_call.assert_called_once_with("test_tool", {})

            # 验证返回的是ToolResultMessage且内容包含文件信息（因为超过了默认50000字符限制）
            self.assertEqual(type(result).__name__, "ToolResultMessage")
            self.assertIn("已保存到临时文件", getattr(result, "content"))

    async def test_tool_manager_without_config(self):
        """测试ToolManager不使用配置的情况（使用默认值）"""
        # 使用默认配置的ToolManager
        from linhai.group_chat import GroupChat

        group_chat = GroupChat()
        manager_without_config = ToolManager(
            group_chat=group_chat, toolsets=[global_tools]
        )

        # 模拟工具调用返回刚好超过默认限制的内容
        long_content = "A" * 50001  # 超过默认的50000字符限制
        mock_tool_call = ToolCallMessage(
            function_name="test_tool", function_arguments={}
        )

        # 模拟工具存在和工具调用
        with unittest.mock.patch.object(
            global_tools, "has_tool", return_value=True
        ), unittest.mock.patch(
            "linhai.tool.base.global_tools.call_tool", return_value=long_content
        ) as mock_call:
            result = await manager_without_config.process_tool_call(mock_tool_call)

            # 验证工具被正确调用
            mock_call.assert_called_once_with("test_tool", {})

            # 验证返回的是ToolResultMessage且内容包含文件信息（因为超过了50000字符限制）
            self.assertEqual(type(result).__name__, "ToolResultMessage")
            self.assertIn("已保存到临时文件", getattr(result, "content"))

    # 移除manager_run_loop测试，因为ToolManager不再有run方法