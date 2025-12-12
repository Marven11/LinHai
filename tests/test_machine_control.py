"""MachineControl类的单元测试"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from linhai.machine_control import MachineControl
from linhai.machine_control.master_host.master_host import MasterHostControl
from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager
from linhai.tool.base import ToolSet


class TestMachineControl(unittest.TestCase):
    """MachineControl测试类"""

    def setUp(self):
        """测试前准备"""
        self.group_chat = Mock(spec=GroupChat)
        self.machine_control = MachineControl(self.group_chat)
        self.tool_manager = Mock(spec=ToolManager)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.machine_control.target_machine, "master_host")
        self.assertIn("master_host", self.machine_control.machines)
        self.assertIsInstance(
            self.machine_control.machines["master_host"], MasterHostControl
        )

    def test_list_machines(self):
        """测试列出机器"""

        async def test():
            result = await self.machine_control.list_machines()
            self.assertIn("可用机器", result.content)
            self.assertIn("master_host", result.content)
            self.assertIn("本地主机", result.content)

        asyncio.run(test())

    def test_switch_machine_not_found(self):
        """测试切换到不存在的机器"""

        async def test():
            result = await self.machine_control.switch_machine("unknown")
            self.assertIn("机器未找到", result.content)

        asyncio.run(test())

    def test_switch_machine_success(self):
        """测试成功切换机器"""
        mock_send = AsyncMock()
        self.machine_control.group_chat.send = mock_send

        async def test():
            result = await self.machine_control.switch_machine("master_host")
            self.assertIn("已切换到机器", result.content)
            self.assertEqual(self.machine_control.target_machine, "master_host")

        asyncio.run(test())

    def test_register_tools(self):
        """测试注册工具"""
        # 工具注册是通过register_machine_control_tools函数完成的
        # 这里我们测试该函数返回的ToolSet不为空
        from linhai.machine_control.main import register_machine_control_tools

        toolset = register_machine_control_tools(self.machine_control)
        self.assertIsInstance(toolset, ToolSet)
        # 检查是否包含一些基本工具
        # ToolSet.tools是一个字典，键是工具名，值是Tool字典
        tool_names = list(toolset.tools.keys())
        self.assertIn("list_machines", tool_names)
        self.assertIn("switch_machine", tool_names)

    def test_register_plugin(self):
        """测试注册插件"""
        mock_lifecycle = Mock()
        mock_lifecycle.register_before_message_generation = Mock()
        self.machine_control.register_plugin(mock_lifecycle)
        mock_lifecycle.register_before_message_generation.assert_called_once()
        # 检查是否被调用了一次，并且参数是 callable
        call_args = mock_lifecycle.register_before_message_generation.call_args
        self.assertIsNotNone(call_args)
        self.assertEqual(len(call_args[0]), 1)
        self.assertTrue(callable(call_args[0][0]))


class TestMasterHostControl(unittest.TestCase):
    """MasterHostControl测试类"""

    def setUp(self):
        """测试前准备"""
        self.host_control = MasterHostControl()

    def test_http_request(self):
        """测试HTTP请求"""
        # 由于http_request需要网络，我们只测试方法存在
        self.assertTrue(hasattr(self.host_control, "http_request"))

    def test_run_command(self):
        """测试运行命令"""
        self.assertTrue(hasattr(self.host_control, "run_command"))

    def test_change_directory(self):
        """测试改变目录"""
        self.assertTrue(hasattr(self.host_control, "change_directory"))

    def test_file_operations(self):
        """测试文件操作"""
        self.assertTrue(hasattr(self.host_control, "read_file"))
        self.assertTrue(hasattr(self.host_control, "write_file"))
        self.assertTrue(hasattr(self.host_control, "append_file"))
        self.assertTrue(hasattr(self.host_control, "replace_file_content"))
        self.assertTrue(hasattr(self.host_control, "list_files"))
        self.assertTrue(hasattr(self.host_control, "get_absolute_path"))

        self.assertTrue(hasattr(self.host_control, "modify_file_with_sed"))
        self.assertTrue(hasattr(self.host_control, "insert_at_line"))

    def test_terminal_operations(self):
        """测试终端操作"""
        self.assertTrue(hasattr(self.host_control, "create_terminal"))
        self.assertTrue(hasattr(self.host_control, "send_keys_to_terminal"))
        self.assertTrue(hasattr(self.host_control, "send_string_to_terminal"))
        self.assertTrue(hasattr(self.host_control, "read_terminal_screen"))
        self.assertTrue(hasattr(self.host_control, "close_terminal"))


if __name__ == "__main__":
    unittest.main()
