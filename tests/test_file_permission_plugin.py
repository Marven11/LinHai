import unittest
from unittest.mock import MagicMock
from pathlib import Path
import tempfile
import shutil

from linhai.plugin import FileOperationPermissionPlugin
from linhai.registry import Registry
from linhai.tool.base import FailedToolResult
from linhai.config import ToolConfig, FileOperationRule


class TestFileOperationPermissionPlugin(unittest.IsolatedAsyncioTestCase):
    """测试文件操作权限插件"""

    def setUp(self):
        self.registry = MagicMock(spec=Registry)
        self.pwd = Path.cwd()
        self.temp_dir = tempfile.mkdtemp(dir=self.pwd)
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.write_text("测试内容\n第二行\n第三行", encoding="utf-8")
        self.tool_config = MagicMock(spec=ToolConfig)
        self.tool_config.file_operation_rules = []
        self.tool_config.file_operation_default_rule = "ALLOW"

    def _make_plugin(self, tool_config=None):
        config = tool_config or self.tool_config
        plugin = FileOperationPermissionPlugin(self.registry, config)
        plugin._get_pwd = lambda: self.pwd
        plugin._is_master_host = lambda: True
        return plugin

    def tearDown(self):
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    async def test_check_permission_allow_read(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = plugin.check_permission("read", str(self.test_file))
        self.assertTrue(result)

    async def test_check_permission_block_write(self):
        rule = FileOperationRule(operation="WRITE", pattern="**/*.txt", action="BLOCK")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = plugin.check_permission("write", str(self.test_file))
        self.assertFalse(result)

    async def test_check_permission_read_write_operation(self):
        rule = FileOperationRule(
            operation="READ_WRITE", pattern="**/*.txt", action="BLOCK"
        )
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        self.assertFalse(plugin.check_permission("read", str(self.test_file)))
        self.assertFalse(plugin.check_permission("write", str(self.test_file)))

    async def test_check_permission_with_relative_path(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        relative_path = self.test_file.relative_to(self.pwd)
        result = plugin.check_permission("read", str(relative_path))
        self.assertTrue(result)

    async def test_check_permission_default_rule_allow(self):
        self.tool_config.file_operation_rules = []
        self.tool_config.file_operation_default_rule = "ALLOW"
        plugin = self._make_plugin()
        result = plugin.check_permission("read", str(self.test_file))
        self.assertTrue(result)

    async def test_check_permission_default_rule_block(self):
        self.tool_config.file_operation_rules = []
        self.tool_config.file_operation_default_rule = "BLOCK"
        plugin = self._make_plugin()
        result = plugin.check_permission("read", str(self.test_file))
        self.assertFalse(result)

    async def test_before_tool_call_read_file_allowed(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = await plugin.before_tool_call(
            tool_name="read_file",
            toolcall_arguments={"filepath": str(self.test_file)},
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsNone(result)

    async def test_before_tool_call_write_file_blocked(self):
        rule = FileOperationRule(operation="WRITE", pattern="**/*.txt", action="BLOCK")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = await plugin.before_tool_call(
            tool_name="write_file",
            toolcall_arguments={
                "filepath": str(self.test_file),
                "content": "新内容",
                "override": True,
            },
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("用户设置禁止你写入", result.content)

    async def test_before_tool_call_unsupported_tool(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = await plugin.before_tool_call(
            tool_name="unsupported_tool",
            toolcall_arguments={},
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsNone(result)

    async def test_check_permission_absolute_path_block(self):
        rule = FileOperationRule(
            operation="READ", pattern="/tmp/fobidden/**", action="BLOCK"
        )
        self.tool_config.file_operation_rules = [rule]
        self.tool_config.file_operation_default_rule = "ALLOW"
        plugin = self._make_plugin()
        self.assertFalse(plugin.check_permission("read", "/tmp/fobidden/test.txt"))
        self.assertTrue(plugin.check_permission("read", "/tmp/other/test.txt"))

    async def test_check_permission_absolute_path_allow_only(self):
        rule = FileOperationRule(
            operation="READ", pattern="/tmp/allowed/**", action="ALLOW"
        )
        self.tool_config.file_operation_rules = [rule]
        self.tool_config.file_operation_default_rule = "BLOCK"
        plugin = self._make_plugin()
        self.assertTrue(plugin.check_permission("read", "/tmp/allowed/test.txt"))
        self.assertFalse(plugin.check_permission("read", "/tmp/other/test.txt"))

    async def test_check_permission_absolute_path_write_block(self):
        rule = FileOperationRule(
            operation="WRITE", pattern="/tmp/readonly/**", action="BLOCK"
        )
        self.tool_config.file_operation_rules = [rule]
        self.tool_config.file_operation_default_rule = "ALLOW"
        plugin = self._make_plugin()
        self.assertFalse(plugin.check_permission("write", "/tmp/readonly/test.txt"))
        self.assertTrue(plugin.check_permission("read", "/tmp/readonly/test.txt"))

    async def test_before_tool_call_skip_non_master_host(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="BLOCK")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        plugin._is_master_host = lambda: False
        result = await plugin.before_tool_call(
            tool_name="read_file",
            toolcall_arguments={"filepath": str(self.test_file)},
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
