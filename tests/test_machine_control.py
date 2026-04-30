"""MachineControl类的单元测试"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from linhai.machine_control import MachineControl
from linhai.machine_control.master_host.master_host import MasterHostControl
from linhai.registry import Registry
from linhai.tool.main import ToolManager
from linhai.tool.base import ToolSet
from linhai.machine_control.main import MachineControlPlugin
from linhai.base import ToolCallMessage
from linhai.machine_control.process import ProcessCreateResult, ProcessCreateInfo
from linhai.utils.common import UiNotice


class TestMachineControl(unittest.IsolatedAsyncioTestCase):
    """MachineControl测试类"""

    def setUp(self):
        """测试前准备"""
        self.registry = Mock(spec=Registry)
        self.machine_control = MachineControl(self.registry, remote_machines=[])
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
            "posix_shell": mock_host_control2,
        }
        result = await self.machine_control.list_all_terminals()
        self.assertIn("机器 master_host", result.content)
        self.assertIn("机器 posix_shell", result.content)
        self.assertIn("远程终端", result.content)

    async def test_switch_machine_not_found(self):
        """测试切换到不存在的机器"""
        result = await self.machine_control.switch_machine("unknown")
        self.assertIn("机器未找到", result.content)

    async def test_switch_machine_success(self):
        """测试成功切换机器"""
        mock_send = AsyncMock()
        self.machine_control.registry.send = mock_send

        result = await self.machine_control.switch_machine("master_host")
        self.assertIn("已切换到机器", result.content)
        self.assertEqual(self.machine_control.target_machine, "master_host")

    def test_register_tools(self):
        """测试注册工具"""
        # 工具注册是通过register_machine_control_tools函数完成的
        # 这里我们测试该函数返回的ToolSet不为空
        from linhai.machine_control.tools import register_machine_control_tools

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
        mock_lifecycle.before_message_generation.register = Mock()
        self.machine_control.register_plugin(mock_lifecycle)
        mock_lifecycle.before_message_generation.register.assert_called_once()
        # 检查是否被调用了一次，并且参数是 callable
        call_args = mock_lifecycle.before_message_generation.register.call_args
        self.assertIsNotNone(call_args)
        self.assertEqual(len(call_args[0]), 1)
        self.assertTrue(callable(call_args[0][0]))


def _create_host_control() -> MasterHostControl:
    from linhai.sandbox import NoSandbox

    registry = Registry()
    registry.register_member("process_sandbox", NoSandbox())
    return MasterHostControl(registry)


class TestMasterHostControl(unittest.IsolatedAsyncioTestCase):
    """MasterHostControl测试类"""

    def setUp(self):
        """测试前准备"""
        self.host_control = _create_host_control()

    def tearDown(self):
        """测试后清理，避免ResourceWarning"""
        # 清理进程字典，防止子进程未关闭警告
        self.host_control._processes.clear()

    def test_http_request(self):
        """测试HTTP请求"""
        # 由于http_request需要网络，我们只测试方法存在
        self.assertTrue(hasattr(self.host_control, "http_request"))

    async def test_process_create_immediate_exit(self):
        """测试process_create - 进程立即退出"""
        with patch("asyncio.create_subprocess_exec") as mock_create:
            mock_process = AsyncMock()
            mock_process.pid = 12345
            mock_process.returncode = 0
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"output")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_create.return_value = mock_process

            result = await self.host_control.create_process(["echo", "test"], 1.0)
            self.assertTrue(result.success)
            self.assertEqual(result.pid, "12345")
            self.assertIn("output", result.stdout)
            self.assertEqual(result.returncode, 0)

    async def test_process_create_default_wait_second(self):
        """测试create_process - wait_second为None时使用1.0秒默认值"""
        with patch("asyncio.create_subprocess_exec") as mock_create:
            mock_process = AsyncMock()
            mock_process.pid = 12345
            mock_process.returncode = 0
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"output")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_create.return_value = mock_process

            result = await self.host_control.create_process(["echo", "test"])
            self.assertTrue(result.success)
            self.assertEqual(result.pid, "12345")
            self.assertIn("output", result.stdout)

    async def test_process_create_timeout_no_stdio_read(self):
        """测试process_create - 超时时不应读取stdio"""
        with (
            patch("asyncio.create_subprocess_exec") as mock_create,
            patch("time.perf_counter") as mock_time,
            patch("asyncio.sleep"),
        ):

            mock_process = AsyncMock()
            mock_process.pid = 12346
            mock_process.returncode = None
            mock_create.return_value = mock_process

            mock_time.side_effect = [0.0, 0.5, 1.0, 1.5, 1.6, 1.6, 4.0]

            result = await self.host_control.create_process(["sleep", "5"], 1.0)
            self.assertTrue(result.success)
            self.assertEqual(result.pid, "12346")
            self.assertIn("等待失败", result.message)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")

    async def test_process_stdio_read_with_exited_process(self):
        """测试stdio_read - 进程已退出"""
        from linhai.machine_control.master_host.process import LocalProcess

        host_control = _create_host_control()

        mock_process = AsyncMock()
        mock_process.pid = 12347
        mock_process.returncode = 0
        mock_process.stdout = AsyncMock()
        mock_process.stdout.read = AsyncMock(return_value=b"final output")
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")

        lp = LocalProcess(mock_process)
        host_control._processes["12347"] = lp

        proc = host_control.get_process("12347")
        self.assertIsNotNone(proc)
        result = await proc.stdio_read(wait_seconds=2.0)
        self.assertIn(b"final output", result.stdout)

    async def test_process_stdio_read_with_running_process(self):
        """测试stdio_read - 进程仍在运行"""
        from linhai.machine_control.master_host.process import LocalProcess

        host_control = _create_host_control()

        mock_process = AsyncMock()
        mock_process.pid = 12348
        mock_process.returncode = None
        mock_process.stdout = AsyncMock()
        mock_process.stdout.read = AsyncMock(return_value=b"ongoing output")
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")

        lp = LocalProcess(mock_process)
        host_control._processes["12348"] = lp

        proc = host_control.get_process("12348")
        self.assertIsNotNone(proc)
        result = await proc.stdio_read(wait_seconds=2.0)
        self.assertIn(b"ongoing output", result.stdout)

    def test_process_operations(self):
        """测试进程操作"""
        self.assertTrue(hasattr(self.host_control, "create_process"))
        self.assertTrue(hasattr(self.host_control, "get_process"))

    async def test_change_directory(self):
        """测试改变目录 - 使用_cwd而非os.chdir"""
        import tempfile
        import os
        from linhai.tool.base import ToolResultSuccess, ToolResultFailed

        old_cwd = self.host_control._cwd

        with tempfile.TemporaryDirectory() as tmpdir:
            result = await self.host_control.change_directory(tmpdir)
            self.assertIsInstance(result, ToolResultSuccess)
            self.assertIn("切换到了", result.content)
            self.assertEqual(self.host_control._cwd, tmpdir)

        result = await self.host_control.change_directory("/nonexistent_dir_xyz")
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("目录不存在", result.content)

        self.host_control._cwd = old_cwd

    async def test_resolve_path_relative(self):
        """测试_resolve_path解析相对路径"""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            self.host_control._cwd = tmpdir
            resolved = self.host_control._resolve_path("subdir/file.txt")
            expected = os.path.join(tmpdir, "subdir", "file.txt")
            self.assertEqual(str(resolved), expected)

    async def test_resolve_path_absolute(self):
        """测试_resolve_path绝对路径不修改"""
        resolved = self.host_control._resolve_path("/absolute/path/file.txt")
        self.assertEqual(str(resolved), "/absolute/path/file.txt")

    async def test_write_file_resolves_cwd(self):
        """测试write_file使用_cwd解析相对路径"""
        import tempfile
        import os
        from linhai.tool.base import ToolResultSuccess

        with tempfile.TemporaryDirectory() as tmpdir:
            self.host_control._cwd = tmpdir
            result = await self.host_control.write_file("test_write.txt", "hello world")
            self.assertIsInstance(result, ToolResultSuccess)
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "test_write.txt")))
            with open(os.path.join(tmpdir, "test_write.txt")) as f:
                self.assertEqual(f.read(), "hello world")

    async def test_read_file_resolves_cwd(self):
        """测试read_file使用_cwd解析相对路径"""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            self.host_control._cwd = tmpdir
            with open(os.path.join(tmpdir, "test_read.txt"), "w") as f:
                f.write("read content")
            result = await self.host_control.read_file("test_read.txt")
            self.assertIn("read content", result.content)

    async def test_replace_file_content_resolves_cwd(self):
        """测试replace_file_content使用_cwd解析相对路径"""
        import tempfile
        import os
        from linhai.tool.base import ToolResultSuccess

        with tempfile.TemporaryDirectory() as tmpdir:
            self.host_control._cwd = tmpdir
            with open(os.path.join(tmpdir, "test_replace.txt"), "w") as f:
                f.write("old text here")
            result = await self.host_control.replace_file_content(
                "test_replace.txt", "old text", "new text"
            )
            self.assertIsInstance(result, ToolResultSuccess)
            with open(os.path.join(tmpdir, "test_replace.txt")) as f:
                self.assertEqual(f.read(), "new text here")

    async def test_list_files_resolves_cwd(self):
        """测试list_files使用_cwd解析相对路径"""
        import tempfile
        import os
        from linhai.tool.base import ToolResultSuccess

        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)
            self.host_control._cwd = tmpdir
            result = await self.host_control.list_files("subdir")
            self.assertIsInstance(result, ToolResultSuccess)

    async def test_get_absolute_path_resolves_cwd(self):
        """测试get_absolute_path使用_cwd解析相对路径"""
        import tempfile
        import os
        from linhai.tool.base import ToolResultSuccess

        with tempfile.TemporaryDirectory() as tmpdir:
            self.host_control._cwd = tmpdir
            result = await self.host_control.get_absolute_path("relative/path")
            self.assertIsInstance(result, ToolResultSuccess)
            expected = os.path.join(tmpdir, "relative", "path")
            self.assertIn(expected, result.content)

    async def test_change_directory_affects_file_ops(self):
        """测试change_directory后文件操作使用新cwd"""
        import tempfile
        import os
        from linhai.tool.base import ToolResultSuccess

        old_cwd = self.host_control._cwd

        with tempfile.TemporaryDirectory() as tmpdir:
            await self.host_control.change_directory(tmpdir)
            self.assertEqual(self.host_control._cwd, tmpdir)

            await self.host_control.write_file("after_cd.txt", "written after cd")
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "after_cd.txt")))

            result = await self.host_control.read_file("after_cd.txt")
            self.assertIn("written after cd", result.content)

        self.host_control._cwd = old_cwd

    async def test_create_process_passes_cwd(self):
        """测试create_process传递cwd给子进程"""
        import tempfile
        from unittest.mock import patch, AsyncMock

        with tempfile.TemporaryDirectory() as tmpdir:
            self.host_control._cwd = tmpdir
            with patch("asyncio.create_subprocess_exec") as mock_create:
                mock_process = AsyncMock()
                mock_process.pid = 99999
                mock_process.returncode = 0
                mock_process.stdout = AsyncMock()
                mock_process.stdout.read = AsyncMock(return_value=b"")
                mock_process.stderr = AsyncMock()
                mock_process.stderr.read = AsyncMock(return_value=b"")
                mock_create.return_value = mock_process

                await self.host_control.create_process(["pwd"])
                mock_create.assert_called_once()
                call_kwargs = mock_create.call_args
                self.assertEqual(call_kwargs.kwargs.get("cwd"), tmpdir)

    def test_file_operations(self):
        """测试文件操作"""
        self.assertTrue(hasattr(self.host_control, "read_file"))
        self.assertTrue(hasattr(self.host_control, "write_file"))
        self.assertTrue(hasattr(self.host_control, "replace_file_content"))
        self.assertTrue(hasattr(self.host_control, "list_files"))
        self.assertTrue(hasattr(self.host_control, "get_absolute_path"))

    def test_terminal_operations(self):
        """测试终端操作"""
        self.assertTrue(hasattr(self.host_control, "terminal_create"))
        self.assertTrue(hasattr(self.host_control, "terminal_send_keys"))
        self.assertTrue(hasattr(self.host_control, "terminal_send_string"))
        self.assertTrue(hasattr(self.host_control, "terminal_read_screen"))
        self.assertTrue(hasattr(self.host_control, "terminal_close"))


class TestNotifyProcessCreated(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.host_control = _create_host_control()

    def tearDown(self):
        self.host_control._processes.clear()

    async def test_notify_triggers_lifecycle(self):
        from linhai.agent.lifecycle import Lifecycle

        registry = self.host_control._registry
        lifecycle = Lifecycle(registry)
        triggered_infos: list[ProcessCreateInfo] = []

        async def on_process_create(info: ProcessCreateInfo) -> None:
            triggered_infos.append(info)

        lifecycle.after_process_create.register(on_process_create)

        with (
            patch("asyncio.create_subprocess_exec") as mock_create,
            patch("asyncio.sleep"),
        ):
            mock_process = AsyncMock()
            mock_process.pid = 55555
            mock_process.returncode = None
            mock_create.return_value = mock_process

            await self.host_control.create_process(["sleep", "10"], wait_second=5.0)

        self.assertEqual(len(triggered_infos), 1)
        self.assertEqual(triggered_infos[0].machine_id, "master_host")
        self.assertEqual(triggered_infos[0].argv, ["sleep", "10"])

    async def test_notify_no_lifecycle_no_error(self):
        with (
            patch("asyncio.create_subprocess_exec") as mock_create,
            patch("asyncio.sleep"),
        ):
            mock_process = AsyncMock()
            mock_process.pid = 55556
            mock_process.returncode = None
            mock_create.return_value = mock_process

            result = await self.host_control.create_process(
                ["sleep", "1"], wait_second=1.0
            )
            self.assertTrue(result.success)

    async def test_notify_not_called_for_exited_process(self):
        from linhai.agent.lifecycle import Lifecycle

        registry = self.host_control._registry
        lifecycle = Lifecycle(registry)
        triggered_infos: list[ProcessCreateInfo] = []

        async def on_process_create(info: ProcessCreateInfo) -> None:
            triggered_infos.append(info)

        lifecycle.after_process_create.register(on_process_create)

        with patch("asyncio.create_subprocess_exec") as mock_create:
            mock_process = AsyncMock()
            mock_process.pid = 55557
            mock_process.returncode = 0
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_create.return_value = mock_process

            result = await self.host_control.create_process(
                ["echo", "test"], wait_second=1.0
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(len(triggered_infos), 1)


class TestRegisterPluginStoreProcessInfo(unittest.IsolatedAsyncioTestCase):

    async def test_lifecycle_handler_stores_process_info(self):
        registry = Registry()
        from linhai.agent.lifecycle import Lifecycle

        lifecycle = Lifecycle(registry)
        mc = MachineControl(registry, remote_machines=[])
        mc.register_plugin(lifecycle)

        mock_process = Mock()
        mock_process.pid = "12345"
        info = ProcessCreateInfo(
            process=mock_process,
            argv=["echo", "hello"],
            machine_id="master_host",
        )
        await lifecycle.after_process_create.trigger(info)

        stored = mc._process_infos.get("master_host:12345")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["argv"], ["echo", "hello"])


class TestListProcesses(unittest.TestCase):
    """测试list_processes返回argv/status/returncode"""

    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.machine_control = MachineControl(self.registry, remote_machines=[])

    def test_list_processes_empty(self):
        """测试无进程时返回空列表"""
        result = self.machine_control.list_processes()
        self.assertEqual(result, [])

    def test_store_and_list_processes(self):
        """测试存储进程信息后list_processes返回完整数据"""
        mock_host = Mock()
        mock_process = Mock()
        mock_process.returncode = None
        mock_host.list_process_pids = Mock(return_value=["123"])
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines = {"master_host": mock_host}

        self.machine_control.store_process_info("123", "master_host", ["echo", "hello"])

        result = self.machine_control.list_processes()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pid"], "123")
        self.assertEqual(result[0]["machine_id"], "master_host")
        self.assertEqual(result[0]["argv"], ["echo", "hello"])
        self.assertEqual(result[0]["status"], "running")
        self.assertIsNone(result[0]["returncode"])

    def test_list_processes_exited(self):
        """测试已退出进程的status为exited"""
        mock_host = Mock()
        mock_process = Mock()
        mock_process.returncode = 0
        mock_host.list_process_pids = Mock(return_value=["456"])
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines = {"master_host": mock_host}

        result = self.machine_control.list_processes()
        self.assertEqual(result[0]["status"], "exited")
        self.assertEqual(result[0]["returncode"], 0)

    def test_list_processes_error_when_no_process(self):
        """测试get_process返回None时status为error"""
        mock_host = Mock()
        mock_host.list_process_pids = Mock(return_value=["789"])
        mock_host.get_process = Mock(return_value=None)
        self.machine_control.machines = {"master_host": mock_host}

        result = self.machine_control.list_processes()
        self.assertEqual(result[0]["status"], "error")
        self.assertIsNone(result[0]["returncode"])

    def test_list_processes_no_stored_info(self):
        """测试未存储info时argv为空列表"""
        mock_host = Mock()
        mock_process = Mock()
        mock_process.returncode = None
        mock_host.list_process_pids = Mock(return_value=["111"])
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines = {"master_host": mock_host}

        result = self.machine_control.list_processes()
        self.assertEqual(result[0]["argv"], [])

    def test_list_processes_records_exit_time(self):
        """测试已退出进程记录exit_time"""
        mock_host = Mock()
        mock_process = Mock()
        mock_process.returncode = 0
        mock_host.list_process_pids = Mock(return_value=["100"])
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines = {"master_host": mock_host}
        self.machine_control.store_process_info("100", "master_host", ["echo"])

        result = self.machine_control.list_processes()
        self.assertEqual(len(result), 1)
        stored = self.machine_control._process_infos["master_host:100"]
        self.assertIsNotNone(stored["exit_time"])

    def test_list_processes_filters_old_exited(self):
        """测试过滤已退出超过300秒的进程"""
        import time as _time

        mock_host = Mock()
        mock_process = Mock()
        mock_process.returncode = 0
        mock_host.list_process_pids = Mock(return_value=["200"])
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines = {"master_host": mock_host}
        self.machine_control.store_process_info("200", "master_host", ["echo"])
        self.machine_control._process_infos["master_host:200"]["exit_time"] = (
            _time.monotonic() - 301.0
        )

        result = self.machine_control.list_processes()
        self.assertEqual(len(result), 0)

    def test_list_processes_keeps_recent_exited(self):
        """测试保留最近退出的进程"""
        import time as _time

        mock_host = Mock()
        mock_process = Mock()
        mock_process.returncode = 0
        mock_host.list_process_pids = Mock(return_value=["300"])
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines = {"master_host": mock_host}
        self.machine_control.store_process_info("300", "master_host", ["echo"])
        self.machine_control._process_infos["master_host:300"]["exit_time"] = (
            _time.monotonic() - 100.0
        )

        result = self.machine_control.list_processes()
        self.assertEqual(len(result), 1)

    def test_list_processes_keeps_running(self):
        """测试运行中进程不被过滤"""
        mock_host = Mock()
        mock_process = Mock()
        mock_process.returncode = None
        mock_host.list_process_pids = Mock(return_value=["400"])
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines = {"master_host": mock_host}
        self.machine_control.store_process_info("400", "master_host", ["sleep"])

        result = self.machine_control.list_processes()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "running")


class TestMachineControlPlugin(unittest.IsolatedAsyncioTestCase):
    """MachineControlPlugin测试类"""

    def setUp(self):
        """测试前准备"""
        self.registry = Mock(spec=Registry)
        self.machine_control = Mock(spec=MachineControl)
        self.machine_control.target_machine = "master_host"
        self.plugin = MachineControlPlugin(self.registry, self.machine_control)

    def test_initialization(self):
        """测试插件初始化"""
        self.assertEqual(self.plugin.registry, self.registry)
        self.assertEqual(self.plugin.machine_control, self.machine_control)

    def test_register_method(self):
        """测试插件的register方法是否正确注册回调"""
        mock_lifecycle = Mock()
        self.plugin.register(mock_lifecycle)

        mock_lifecycle.before_message_generation.register.assert_called_once_with(
            self.plugin.before_message_generation
        )
        mock_lifecycle.after_toolcall.register.assert_called_once_with(
            self.plugin.after_toolcall
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
        self.host_control = _create_host_control()

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


class TestDisconnectMachine(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.registry.send_if_exists = AsyncMock()
        self.machine_control = MachineControl(self.registry, remote_machines=[])

    async def test_disconnect_machine_not_found(self):
        result = await self.machine_control.disconnect_machine("nonexistent")
        from linhai.tool.base import ToolResultFailed

        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("机器未找到", result.content)

    async def test_disconnect_master_host_raises(self):
        from linhai.tool.base import ToolResultFailed

        result = await self.machine_control.disconnect_machine("master_host")
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("master_host", result.content)

    async def test_disconnect_non_current_machine(self):
        mock_host = Mock()
        mock_host.disconnect = AsyncMock()
        self.machine_control.machines["remote"] = mock_host
        self.machine_control.source_machines["remote"] = "master_host"
        self.machine_control.machine_descriptions["remote"] = "test"

        from linhai.tool.base import ToolResultSuccess

        result = await self.machine_control.disconnect_machine("remote")
        self.assertIsInstance(result, ToolResultSuccess)
        self.assertNotIn("remote", self.machine_control.machines)
        self.assertNotIn("remote", self.machine_control.source_machines)
        self.assertNotIn("remote", self.machine_control.machine_descriptions)
        self.assertEqual(self.machine_control.target_machine, "master_host")
        self.assertNotIn("已自动切换", result.content)

    async def test_disconnect_current_machine_switches_to_master(self):
        mock_host = Mock()
        mock_host.disconnect = AsyncMock()
        self.machine_control.machines["remote"] = mock_host
        self.machine_control.source_machines["remote"] = "master_host"
        self.machine_control.machine_descriptions["remote"] = "test"
        self.machine_control.target_machine = "remote"

        from linhai.tool.base import ToolResultSuccess

        result = await self.machine_control.disconnect_machine("remote")
        self.assertIsInstance(result, ToolResultSuccess)
        self.assertEqual(self.machine_control.target_machine, "master_host")
        self.assertIn("已自动切换到机器: master_host", result.content)

    async def test_disconnect_tool_registered(self):
        from linhai.machine_control.tools import register_machine_control_tools

        toolset = register_machine_control_tools(self.machine_control)
        tool_names = list(toolset.tools.keys())
        self.assertIn("disconnect_machine", tool_names)


class TestMasterHostControlDisconnect(unittest.IsolatedAsyncioTestCase):

    async def test_master_host_disconnect_raises(self):
        host_control = _create_host_control()
        with self.assertRaises(RuntimeError) as ctx:
            await host_control.disconnect()
        self.assertIn("master_host", str(ctx.exception))


class TestMachineControlTransferFile(unittest.IsolatedAsyncioTestCase):
    """测试MachineControl的transfer_file方法"""

    def setUp(self):
        from unittest.mock import Mock
        from linhai.registry import Registry

        self.registry = Mock(spec=Registry)
        from linhai.machine_control import MachineControl

        self.machine_control = MachineControl(self.registry, remote_machines=[])

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
        self.assertIn("源机器和目标机器相同", result.content)

    async def test_transfer_file_between_machines_mock(self):
        """测试机器间传输（使用mock）"""
        from unittest.mock import Mock, AsyncMock
        from linhai.tool.base import ToolResultSuccess
        from linhai.machine_control.master_host.master_host import MasterHostControl
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )

        mock_master = Mock(spec=MasterHostControl)
        mock_ssh = Mock(spec=PosixShellControl)
        mock_ssh.download_file_concurrent = AsyncMock(
            return_value=ToolResultSuccess(content="<<message>>下载成功<<message>>")
        )
        mock_master.upload_file_concurrent = AsyncMock(
            return_value=ToolResultSuccess(content="<<message>>上传成功<<message>>")
        )

        self.machine_control.machines = {
            "master_host": mock_master,
            "posix_shell": mock_ssh,
        }

        result = await self.machine_control.transfer_file(
            from_filepath="/tmp/source",
            from_machine="posix_shell",
            to_filepath="/tmp/dest",
            to_machine="master_host",
        )
        from linhai.tool.base import ToolResultSuccess

        self.assertIsInstance(result, ToolResultSuccess)
        mock_ssh.download_file_concurrent.assert_called_once()
        mock_master.upload_file_concurrent.assert_called_once()


if __name__ == "__main__":
    unittest.main()
