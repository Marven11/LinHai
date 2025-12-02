"""文件操作工具的单元测试"""

import unittest
import tempfile
import os
import shutil
from pathlib import Path

from linhai.tool.tools.file import (
    read_file,
    write_file,
    append_file,
    replace_file_content,
    list_files,
    get_absolute_path,
    insert_at_line,
)


class TestFileTools(unittest.TestCase):
    """文件操作工具测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"

        # 创建测试文件内容
        self.test_content = """第一行内容
第二行内容
第三行内容
重复内容
重复内容
重复内容
最后一行内容"""

        self.test_file.write_text(self.test_content, encoding="utf-8")

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_read_file(self):
        """测试读取文件"""
        result = read_file(str(self.test_file))
        # FileContentMessage只包含文件内容，不包含路径前缀
        self.assertEqual(result.content, self.test_content)

    def test_read_file_with_line_numbers(self):
        """测试带行号的读取文件"""
        result = read_file(str(self.test_file), show_line_numbers=True)
        # 带行号的文件内容
        expected = "1: 第一行内容\n2: 第二行内容\n3: 第三行内容\n4: 重复内容\n5: 重复内容\n6: 重复内容\n7: 最后一行内容"
        self.assertEqual(result.content, expected)

    def test_write_file(self):
        """测试写入文件"""
        new_content = "新的文件内容"
        result = write_file(str(self.test_file), new_content, override=True)
        self.assertIn("成功写入文件", result.content)

        # 验证内容确实被写入
        content = self.test_file.read_text(encoding="utf-8")
        self.assertEqual(content, new_content)

    def test_append_file(self):
        """测试追加文件"""
        append_content = "\n追加的内容"
        result = append_file(str(self.test_file), append_content)
        self.assertIn("成功写入文件", result.content)

        # 验证内容被追加
        content = self.test_file.read_text(encoding="utf-8")
        self.assertIn("追加的内容", content)
        self.assertTrue(content.endswith("追加的内容"))

    def test_replace_file_content_default_behavior(self):
        """测试替换文件内容默认行为（不提供replace_times时验证只出现一次）"""
        # 测试默认行为：不提供replace_times时，验证旧内容只出现一次
        result = replace_file_content(str(self.test_file), "重复内容", "替换后的内容")

        # 应该返回错误，因为有多处匹配但未设置replace_times
        self.assertIn("找到3次匹配", result.content)
        self.assertIn("默认只替换一次匹配", result.content)

    def test_replace_file_content_single_match(self):
        """测试替换文件内容（单次匹配）"""
        # 修改文件内容为只有一次匹配
        single_match_content = "第一行\n第二行\n第三行\n重复内容\n第五行"
        self.test_file.write_text(single_match_content, encoding="utf-8")

        result = replace_file_content(str(self.test_file), "重复内容", "替换后的内容")

        self.assertIn("已替换", result.content)

        # 验证内容被替换
        content = self.test_file.read_text(encoding="utf-8")
        self.assertIn("替换后的内容", content)
        self.assertEqual(content.count("替换后的内容"), 1)

    def test_replace_file_content_replace_all(self):
        """测试替换文件内容（替换所有匹配）"""
        result = replace_file_content(
            str(self.test_file), "重复内容", "替换后的内容", replace_times=-1
        )

        self.assertIn("已替换", result.content)
        self.assertIn("替换次数: 3", result.content)

        # 验证所有匹配都被替换
        content = self.test_file.read_text(encoding="utf-8")
        self.assertEqual(content.count("替换后的内容"), 3)
        self.assertNotIn("重复内容", content)

    def test_replace_file_content_not_found(self):
        """测试替换不存在的文件内容"""
        result = replace_file_content(str(self.test_file), "不存在的字符串", "新内容")

        self.assertIn("未找到", result.content)

    def test_list_files(self):
        """测试列出文件"""
        # 在临时目录中创建一些测试文件和文件夹
        (Path(self.temp_dir) / "test1.txt").write_text("test1")
        (Path(self.temp_dir) / "test2.txt").write_text("test2")
        (Path(self.temp_dir) / "subdir").mkdir()

        result = list_files(self.temp_dir)
        self.assertIn("test1.txt", result.content)
        self.assertIn("test2.txt", result.content)
        self.assertIn("subdir", result.content)

    def test_get_absolute_path(self):
        """测试获取绝对路径"""
        result = get_absolute_path(".")
        self.assertIn("绝对路径:", result.content)
        self.assertIn(os.path.abspath("."), result.content)

    def test_insert_at_line(self):
        """测试在指定行插入内容"""
        result = insert_at_line(
            str(self.test_file),
            line_number=3,
            content="插入的新行",
            expected_line_content="第三行内容",
        )

        self.assertIn("成功在文件", result.content)

        # 验证内容被正确插入
        content = self.test_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        self.assertEqual(lines[2], "插入的新行")  # 第3行应该是插入的内容
        self.assertEqual(lines[3], "第三行内容")  # 原来的第3行现在应该是第4行


if __name__ == "__main__":
    unittest.main()

    def test_replace_file_content_replace_times_positive(self):
        """测试替换文件内容（指定替换次数）"""
        result = replace_file_content(
            str(self.test_file), "重复内容", "替换后的内容", replace_times=2
        )

        self.assertIn("已替换", result.content)
        self.assertIn("替换次数: 2", result.content)

        # 验证只有前2次匹配被替换
        content = self.test_file.read_text(encoding="utf-8")
        self.assertEqual(content.count("替换后的内容"), 2)
        self.assertEqual(content.count("重复内容"), 1)

    def test_replace_file_content_replace_times_insufficient_matches(self):
        """测试替换文件内容（要求替换次数超过实际匹配次数）"""
        # 修改文件内容为只有2次匹配
        two_matches_content = "第一行\n重复内容\n第三行\n重复内容\n第五行"
        self.test_file.write_text(two_matches_content, encoding="utf-8")

        result = replace_file_content(
            str(self.test_file), "重复内容", "替换后的内容", replace_times=3
        )

        self.assertIn("只找到2次匹配", result.content)
        self.assertIn("但要求替换3次", result.content)

    def test_replace_file_content_replace_all_insufficient_matches(self):
        """测试替换文件内容（要求替换所有但只有一次匹配）"""
        # 修改文件内容为只有一次匹配
        single_match_content = "第一行\n第二行\n第三行\n重复内容\n第五行"
        self.test_file.write_text(single_match_content, encoding="utf-8")

        result = replace_file_content(
            str(self.test_file), "重复内容", "替换后的内容", replace_times=-1
        )

        self.assertIn("只找到1次匹配", result.content)
        self.assertIn("但要求替换所有匹配", result.content)

    def test_replace_file_content_invalid_replace_times(self):
        """测试替换文件内容（无效的replace_times参数）"""
        result = replace_file_content(
            str(self.test_file), "重复内容", "替换后的内容", replace_times=-2
        )

        self.assertIn("无效的replace_times参数值", result.content)