"""Unit tests for modify_file_with_sed tool with line number warning."""

import unittest
import unittest.mock

from linhai.tool.base import ToolArgInfo


class TestModifyFileWithSedLineNumberWarning(unittest.TestCase):
    """Test cases for modify_file_with_sed tool with line number warning."""

    def setUp(self):
        from linhai.tool.base import ToolSet

        self.toolset = ToolSet()
        from linhai.machine_control.master_host.file import modify_file_with_sed

        self.toolset.register_tool(
            name="modify_file_with_sed",
            desc="使用sed表达式修改文件",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "expression": ToolArgInfo(desc="sed表达式", type="str"),
            },
            required_args=["filepath", "expression"],
        )(modify_file_with_sed)

    @unittest.mock.patch("linhai.machine_control.master_host.file.Path")
    @unittest.mock.patch("linhai.machine_control.master_host.file.platform.system")
    @unittest.mock.patch("linhai.machine_control.master_host.file.subprocess.run")
    def test_modify_file_with_sed_line_number_warning(
        self, mock_run, mock_system, mock_path
    ):
        """测试使用行号表达式时返回警告"""
        mock_system.return_value = "Darwin"

        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.as_posix.return_value = "test.txt"

        mock_run.return_value.returncode = 0

        result = self.toolset.call_tool(
            "modify_file_with_sed",
            {"filepath": "test.txt", "expression": "1s/old/new/"},
        )

        self.assertIn("警告：使用行号匹配并修改文件", result)
        self.assertIn("文件的行号已经变化", result)
        self.assertIn("使用行号匹配是不推荐的行为", result)

        mock_run.assert_called_once_with(
            ["sed", "-i", "", "1s/old/new/", "test.txt"],
            capture_output=True,
            text=True,
            check=True,
        )

    @unittest.mock.patch("linhai.machine_control.master_host.file.Path")
    @unittest.mock.patch("linhai.machine_control.master_host.file.platform.system")
    @unittest.mock.patch("linhai.machine_control.master_host.file.subprocess.run")
    def test_modify_file_with_sed_no_line_number_warning(
        self, mock_run, mock_system, mock_path
    ):
        """测试使用非行号表达式时不返回警告"""
        mock_system.return_value = "Darwin"

        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.as_posix.return_value = "test.txt"

        mock_run.return_value.returncode = 0

        result = self.toolset.call_tool(
            "modify_file_with_sed", {"filepath": "test.txt", "expression": "s/old/new/"}
        )

        self.assertNotIn("警告：使用行号匹配并修改文件", result)
        self.assertIn("已使用sed表达式修改", result)

        mock_run.assert_called_once_with(
            ["sed", "-i", "", "s/old/new/", "test.txt"],
            capture_output=True,
            text=True,
            check=True,
        )

    @unittest.mock.patch("linhai.machine_control.master_host.file.Path")
    @unittest.mock.patch("linhai.machine_control.master_host.file.platform.system")
    @unittest.mock.patch("linhai.machine_control.master_host.file.subprocess.run")
    def test_modify_file_with_sed_line_range_warning(
        self, mock_run, mock_system, mock_path
    ):
        """测试使用行号范围表达式时返回警告"""
        mock_system.return_value = "Darwin"

        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.as_posix.return_value = "test.txt"

        mock_run.return_value.returncode = 0

        result = self.toolset.call_tool(
            "modify_file_with_sed",
            {"filepath": "test.txt", "expression": "1,5s/old/new/"},
        )

        self.assertIn("警告：使用行号匹配并修改文件", result)
        self.assertIn("文件的行号已经变化", result)
        self.assertIn("使用行号匹配是不推荐的行为", result)

        mock_run.assert_called_once_with(
            ["sed", "-i", "", "1,5s/old/new/", "test.txt"],
            capture_output=True,
            text=True,
            check=True,
        )

    @unittest.mock.patch("linhai.machine_control.master_host.file.Path")
    @unittest.mock.patch("linhai.machine_control.master_host.file.platform.system")
    @unittest.mock.patch("linhai.machine_control.master_host.file.subprocess.run")
    def test_modify_file_with_sed_linux_system(self, mock_run, mock_system, mock_path):
        """测试在Linux系统上的行为"""
        mock_system.return_value = "Linux"

        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.as_posix.return_value = "test.txt"

        mock_run.return_value.returncode = 0

        result = self.toolset.call_tool(
            "modify_file_with_sed",
            {"filepath": "test.txt", "expression": "1s/old/new/"},
        )

        self.assertIn("警告：使用行号匹配并修改文件", result)

        mock_run.assert_called_once_with(
            ["sed", "-i", "1s/old/new/", "test.txt"],
            capture_output=True,
            text=True,
            check=True,
        )
