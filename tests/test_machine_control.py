"""MachineControl类的单元测试"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from linhai.machine_control import MachineControl
from linhai.machine_control.master_host.master_host import MasterHostControl
from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager
from linhai.tool.base import ToolSet
from linhai.machine_control.main import MachineControlPlugin
from linhai.llm import ToolCallMessage
from linhai.utils import CliRuntimeNotice


class TestMachineControl(unittest.IsolatedAsyncioTestCase):
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

    async def test_list_machines(self):
        """测试列出机器"""
        result = await self.machine_control.list_machines()
        self.assertIn("可用机器", result.content)
        self.assertIn("master_host", result.content)
        self.assertIn("本地主机", result.content)

    async def test_list_all_terminals(self):
        """测试列出所有终端"""
        # 模拟get_terminals方法返回空终端列表
        mock_host_control = Mock()
        mock_host_control.get_terminals = AsyncMock(return_value=Mock(content=""))
        self.machine_control.machines = {"master_host": mock_host_control}

        result = await self.machine_control.list_all_terminals()
        self.assertIn("当前所有机器上都没有终端", result.content)

        # 测试有终端的情况
        mock_host_control.get_terminals = AsyncMock(
            return_value=Mock(content="终端1: 运行中\n终端2: 空闲")
        )
        result = await self.machine_control.list_all_terminals()
        self.assertIn("机器 master_host", result.content)
        self.assertIn("终端1", result.content)
        self.assertIn("终端2", result.content)

        # 测试多个机器
        mock_host_control2 = Mock()
        mock_host_control2.get_terminals = AsyncMock(
            return_value=Mock(content="远程终端: 运行中")
        )
        self.machine_control.machines = {
            "master_host": mock_host_control,
            "ssh_host": mock_host_control2,
        }
        result = await self.machine_control.list_all_terminals()
        self.assertIn("机器 master_host", result.content)
        self.assertIn("机器 ssh_host", result.content)
        self.assertIn("远程终端", result.content)

    async def test_switch_machine_not_found(self):
        """测试切换到不存在的机器"""
        result = await self.machine_control.switch_machine("unknown")
        self.assertIn("机器未找到", result.content)

    async def test_switch_machine_success(self):
        """测试成功切换机器"""
        mock_send = AsyncMock()
        self.machine_control.group_chat.send = mock_send

        result = await self.machine_control.switch_machine("master_host")
        self.assertIn("已切换到机器", result.content)
        self.assertEqual(self.machine_control.target_machine, "master_host")

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
        self.assertIn("transfer_file", tool_names)

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

    def test_process_operations(self):
        """测试进程操作"""
        self.assertTrue(hasattr(self.host_control, "process_create"))
        self.assertTrue(hasattr(self.host_control, "process_stdio_write"))
        self.assertTrue(hasattr(self.host_control, "process_stdio_read"))
        self.assertTrue(hasattr(self.host_control, "process_wait"))
        self.assertTrue(hasattr(self.host_control, "process_kill"))

    def test_change_directory(self):
        """测试改变目录"""
        self.assertTrue(hasattr(self.host_control, "change_directory"))

    def test_file_operations(self):
        """测试文件操作"""
        self.assertTrue(hasattr(self.host_control, "read_file"))
        self.assertTrue(hasattr(self.host_control, "write_file"))

        self.assertTrue(hasattr(self.host_control, "replace_file_content"))
        self.assertTrue(hasattr(self.host_control, "list_files"))
        self.assertTrue(hasattr(self.host_control, "get_absolute_path"))

        self.assertTrue(hasattr(self.host_control, "modify_file_with_sed"))
        self.assertTrue(hasattr(self.host_control, "insert_at_line"))

    def test_terminal_operations(self):
        """测试终端操作"""
        self.assertTrue(hasattr(self.host_control, "terminal_create"))
        self.assertTrue(hasattr(self.host_control, "terminal_send_keys"))
        self.assertTrue(hasattr(self.host_control, "terminal_send_string"))
        self.assertTrue(hasattr(self.host_control, "terminal_read_screen"))
        self.assertTrue(hasattr(self.host_control, "terminal_close"))


class TestMachineControlPlugin(unittest.IsolatedAsyncioTestCase):
    """MachineControlPlugin测试类"""

    def setUp(self):
        """测试前准备"""
        self.group_chat = Mock(spec=GroupChat)
        self.machine_control = Mock(spec=MachineControl)
        self.machine_control.target_machine = "master_host"
        self.plugin = MachineControlPlugin(self.group_chat, self.machine_control)

    def test_initialization(self):
        """测试插件初始化"""
        self.assertEqual(self.plugin.group_chat, self.group_chat)
        self.assertEqual(self.plugin.machine_control, self.machine_control)
        self.assertEqual(self.plugin.consecutive_same_on_machine_count, 0)
        self.assertIsNone(self.plugin.last_on_machine)

    async def test_before_tool_call_with_different_machine(self):
        """测试before_tool_call，当on_machine与当前机器不同时发送提示"""
        self.machine_control.target_machine = "master_host"
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
            on_machine="other_machine",
        )
        mock_send = AsyncMock()
        self.group_chat.send_if_exists = mock_send

        result = await self.plugin.before_tool_call(tool_call)

        self.assertFalse(result)  # 不打断工具调用
        mock_send.assert_called_once_with(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content="正在切换到机器 other_machine 执行工具 test_tool",
            ),
        )

    async def test_before_tool_call_with_same_machine(self):
        """测试before_tool_call，当on_machine与当前机器相同时不发送提示"""
        self.machine_control.target_machine = "master_host"
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
            on_machine="master_host",
        )
        mock_send = AsyncMock()
        self.group_chat.send_if_exists = mock_send

        result = await self.plugin.before_tool_call(tool_call)

        self.assertFalse(result)
        mock_send.assert_not_called()

    async def test_after_tool_call_reset_counter(self):
        """测试after_tool_call，当on_machine为None时重置计数器"""
        self.plugin.consecutive_same_on_machine_count = 2
        self.plugin.last_on_machine = "master_host"

        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
            on_machine=None,  # 没有指定on_machine
        )
        mock_send = AsyncMock()
        self.group_chat.send_if_exists = mock_send

        result = await self.plugin.after_tool_call(Mock(), tool_call, Mock(), True)

        self.assertIsNone(result)
        self.assertEqual(self.plugin.consecutive_same_on_machine_count, 0)
        self.assertIsNone(self.plugin.last_on_machine)
        mock_send.assert_not_called()

    async def test_after_tool_call_increment_counter_and_warning(self):
        """测试after_tool_call，连续相同on_machine时递增计数器并发送警告"""
        self.machine_control.target_machine = "master_host"
        self.plugin.consecutive_same_on_machine_count = 2
        self.plugin.last_on_machine = "master_host"

        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
            on_machine="master_host",  # 与当前机器相同
        )
        mock_send = AsyncMock()
        self.group_chat.send_if_exists = mock_send

        result = await self.plugin.after_tool_call(Mock(), tool_call, Mock(), True)

        self.assertIsNone(result)
        self.assertEqual(self.plugin.consecutive_same_on_machine_count, 3)
        self.assertEqual(self.plugin.last_on_machine, "master_host")
        # 检查是否发送了警告
        mock_send.assert_called_once_with(
            "ui_log",
            CliRuntimeNotice(
                level="WARNING",
                content="连续3次工具调用都指定了相同的on_machine 'master_host'，且未切换机器。请确认是否需要频繁指定。",
            ),
        )

    def test_register_method(self):
        """测试插件的register方法是否正确注册回调"""
        mock_lifecycle = Mock()
        self.plugin.register(mock_lifecycle)

        mock_lifecycle.register_before_message_generation.assert_called_once_with(
            self.plugin.before_message_generation
        )
        mock_lifecycle.register_before_tool_call.assert_called_once_with(
            self.plugin.before_tool_call
        )
        mock_lifecycle.register_after_tool_call.assert_called_once_with(
            self.plugin.after_tool_call
        )


class TestToolResultFormat(unittest.IsolatedAsyncioTestCase):
    """测试工具调用结果格式（<<>>格式）"""

    async def test_tool_result_success_format(self):
        """测试ToolResultSuccess的content格式为<<>>"""
        from linhai.tool.base import ToolResultSuccess

        # 测试简单的键值对
        content = "<<pid>>123<<pid>><<message>>test<<message>>"
        result = ToolResultSuccess(content=content)
        self.assertEqual(result.content, content)
        # 验证content包含<<>>格式
        self.assertIn("<<pid>>", result.content)
        self.assertIn("<<message>>", result.content)

        # 测试多个键值对
        content2 = "<<key1>>value1<<key1>><<key2>>value2<<key2>>"
        result2 = ToolResultSuccess(content=content2)
        self.assertEqual(result2.content, content2)

    async def test_tool_result_failed_format(self):
        """测试ToolResultFailed的content格式为<<>>"""
        from linhai.tool.base import ToolResultFailed

        content = "<<error>>something went wrong<<error>>"
        result = ToolResultFailed(content=content)
        self.assertEqual(result.content, content)
        self.assertIn("<<error>>", result.content)


class TestMasterHostControlConcurrentFiles(unittest.IsolatedAsyncioTestCase):
    """测试MasterHostControl的并发文件方法"""

    def setUp(self):
        self.host_control = MasterHostControl()

    async def test_upload_file_concurrent_success(self):
        """测试upload_file_concurrent成功"""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.bin")
            data = b"test data" * 1000
            from linhai.tool.base import ToolResultSuccess, ToolResultFailed

            result = await self.host_control.upload_file_concurrent(data, test_file)
            self.assertIsInstance(result, ToolResultSuccess)
            self.assertIn("文件已上传", result.content)
            with open(test_file, "rb") as f:
                written_data = f.read()
            self.assertEqual(written_data, data)

    async def test_upload_file_concurrent_file_exists(self):
        """测试upload_file_concurrent文件已存在"""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.bin")
            with open(test_file, "wb") as f:
                f.write(b"existing")
            from linhai.tool.base import ToolResultSuccess, ToolResultFailed

            result = await self.host_control.upload_file_concurrent(
                b"new data", test_file
            )
            self.assertIsInstance(result, ToolResultFailed)
            self.assertIn("文件已存在", result.content)

    async def test_download_file_concurrent_success(self):
        """测试download_file_concurrent成功"""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "source.bin")
            dest_file = os.path.join(tmpdir, "dest.bin")
            data = b"download test" * 500
            with open(source_file, "wb") as f:
                f.write(data)
            from linhai.tool.base import ToolResultSuccess, ToolResultFailed

            result = await self.host_control.download_file_concurrent(
                source_file, dest_file
            )
            self.assertIsInstance(result, ToolResultSuccess)
            self.assertIn("文件已下载", result.content)
            with open(dest_file, "rb") as f:
                downloaded_data = f.read()
            self.assertEqual(downloaded_data, data)

    async def test_download_file_concurrent_file_not_found(self):
        """测试download_file_concurrent文件不存在"""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_file = os.path.join(tmpdir, "dest.bin")
            from linhai.tool.base import ToolResultSuccess, ToolResultFailed

            result = await self.host_control.download_file_concurrent(
                "/nonexistent", dest_file
            )
            self.assertIsInstance(result, ToolResultFailed)
            self.assertIn("文件不存在", result.content)


class TestMachineControlTransferFile(unittest.IsolatedAsyncioTestCase):
    """测试MachineControl的transfer_file方法"""

    def setUp(self):
        from unittest.mock import Mock
        from linhai.group_chat import GroupChat

        self.group_chat = Mock(spec=GroupChat)
        from linhai.machine_control import MachineControl

        self.machine_control = MachineControl(self.group_chat)

    async def test_transfer_file_same_machine(self):
        """测试同一台机器传输应失败"""
        from linhai.tool.base import ToolResultFailed

        result = await self.machine_control.transfer_file(
            from_filepath="/tmp/source",
            from_machine="master_host",
            to_filepath="/tmp/dest",
            to_machine="master_host",
        )
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("不能在同一台机器上传输", result.content)

    async def test_transfer_file_between_machines_mock(self):
        """测试机器间传输（使用mock）"""
        from unittest.mock import Mock, AsyncMock
        from linhai.tool.base import ToolResultSuccess
        from linhai.machine_control.master_host.master_host import MasterHostControl
        from linhai.machine_control.ssh_host.ssh_host import SshMachineControl

        mock_master = Mock(spec=MasterHostControl)
        mock_ssh = Mock(spec=SshMachineControl)
        mock_master.download_file_concurrent = AsyncMock(
            return_value=ToolResultSuccess(content="<<message>>下载成功<<message>>")
        )
        mock_ssh.upload_file_concurrent = AsyncMock(
            return_value=ToolResultSuccess(content="<<message>>上传成功<<message>>")
        )

        self.machine_control.machines = {
            "master_host": mock_master,
            "ssh_host": mock_ssh,
        }

        result = await self.machine_control.transfer_file(
            from_filepath="/tmp/source",
            from_machine="ssh_host",
            to_filepath="/tmp/dest",
            to_machine="master_host",
        )
        from linhai.tool.base import ToolResultSuccess

        self.assertIsInstance(result, ToolResultSuccess)
        mock_master.download_file_concurrent.assert_called_once()
        mock_ssh.upload_file_concurrent.assert_called_once()


if __name__ == "__main__":
    unittest.main()
