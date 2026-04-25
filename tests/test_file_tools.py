"""文件操作工具的单元测试"""

import unittest
import tempfile
import os
import shutil
from pathlib import Path

from linhai.machine_control.master_host.file import (
    read_file,
    write_file,
    replace_file_content,
    list_files,
    get_absolute_path,
    find_most_similar_in_files,
)


class TestFileTools(unittest.TestCase):
    """文件操作工具测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"

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
        self.assertEqual(result.content, self.test_content)

    def test_read_file_with_line_numbers(self):
        """测试带行号的读取文件"""
        result = read_file(str(self.test_file), show_line_numbers=True)
        # content属性应该是原始内容，不带行号
        self.assertEqual(result.content, self.test_content)
        # 验证show_line_numbers属性正确设置
        self.assertTrue(result.show_line_numbers)

    def test_write_file(self):
        """测试写入文件"""
        new_content = "新的文件内容"
        result = write_file(str(self.test_file), new_content, override=True)
        self.assertIn("成功写入文件", result.content)

        content = self.test_file.read_text(encoding="utf-8")
        self.assertEqual(content, new_content)

    def test_replace_file_content_default_behavior(self):
        """测试替换文件内容默认行为（不提供replace_times时验证只出现一次）"""
        result = replace_file_content(str(self.test_file), "重复内容", "替换后的内容")

        self.assertIn("找到3次匹配", result.content)
        self.assertIn("默认只替换一次匹配", result.content)

    def test_replace_file_content_single_match(self):
        """测试替换文件内容（单次匹配）"""
        single_match_content = "第一行\n第二行\n第三行\n重复内容\n第五行"
        self.test_file.write_text(single_match_content, encoding="utf-8")

        result = replace_file_content(str(self.test_file), "重复内容", "替换后的内容")

        self.assertIn("已替换", result.content)

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

        content = self.test_file.read_text(encoding="utf-8")
        self.assertEqual(content.count("替换后的内容"), 3)
        self.assertNotIn("重复内容", content)

    def test_replace_file_content_not_found(self):
        """测试替换不存在的文件内容"""
        result = replace_file_content(str(self.test_file), "不存在的字符串", "新内容")

        self.assertIn("未找到", result.content)

    def test_list_files(self):
        """测试列出文件"""
        (Path(self.temp_dir) / "test1.txt").write_text("test1")
        (Path(self.temp_dir) / "test2.txt").write_text("test2")
        (Path(self.temp_dir) / "subdir").mkdir()

        result = list_files(self.temp_dir)
        self.assertIn("test1.txt", result.content)
        self.assertIn("test2.txt", result.content)
        self.assertIn("subdir", result.content)

    def test_list_files_sorted_by_filename(self):
        """测试list_files按文件名排序"""
        test_files = [
            "z_last.txt",
            "a_first.txt",
            "m_middle.txt",
        ]
        for filename in test_files:
            (Path(self.temp_dir) / filename).write_text("test")

        result = list_files(self.temp_dir)
        lines = result.content.split("\n")
        file_lines = [
            line for line in lines if any(filename in line for filename in test_files)
        ]
        file_names = [line.split()[-1] for line in file_lines]
        expected_order = sorted(test_files)
        self.assertEqual(file_names, expected_order)

    def test_get_absolute_path(self):
        """测试获取绝对路径"""
        result = get_absolute_path(".")
        self.assertIn("绝对路径:", result.content)
        self.assertIn(os.path.abspath("."), result.content)

    def test_find_most_similar_in_files_short_content(self):
        """测试find_most_similar_in_files：短内容返回完整块"""
        content = "line1\nline2\nline3\nline4\nline5"
        search = "line2\nline3"
        result = find_most_similar_in_files(search, content, top_n=1)
        self.assertIn("line2", result)
        self.assertIn("line3", result)
        self.assertIn("相似度:", result)
        self.assertIn("行号:", result)

    def test_find_most_similar_in_files_long_content(self):
        """测试find_most_similar_in_files：长内容仅返回位置"""
        long_line = (
            "this is a very long line with many words to increase token count substantially "
            * 10
        )
        content = "\n".join([f"line{i}: {long_line}" for i in range(10)])
        search = "line2:\nline3:\nline4:"
        result = find_most_similar_in_files(search, content, top_n=1)
        self.assertIn("相似度:", result)
        self.assertIn("行号:", result)
        self.assertIn("内容超过300 token已省略", result)

    def test_find_most_similar_in_files_multiple_results(self):
        """测试find_most_similar_in_files：返回多个结果"""
        content = "target\nline2\nline3\ntarget\nline5"
        search = "target"
        result = find_most_similar_in_files(search, content, top_n=2)
        self.assertEqual(result.count("<<alternative>>"), 4)


if __name__ == "__main__":
    unittest.main()

    def test_replace_file_content_replace_times_positive(self):
        """测试替换文件内容（指定替换次数）"""
        result = replace_file_content(
            str(self.test_file), "重复内容", "替换后的内容", replace_times=2
        )

        self.assertIn("已替换", result.content)
        self.assertIn("替换次数: 2", result.content)

        content = self.test_file.read_text(encoding="utf-8")
        self.assertEqual(content.count("替换后的内容"), 2)
        self.assertEqual(content.count("重复内容"), 1)

    def test_replace_file_content_replace_times_insufficient_matches(self):
        """测试替换文件内容（要求替换次数超过实际匹配次数）"""
        two_matches_content = "第一行\n重复内容\n第三行\n重复内容\n第五行"
        self.test_file.write_text(two_matches_content, encoding="utf-8")

        result = replace_file_content(
            str(self.test_file), "重复内容", "替换后的内容", replace_times=3
        )

        self.assertIn("只找到2次匹配", result.content)
        self.assertIn("但要求替换3次", result.content)

    def test_replace_file_content_replace_all_insufficient_matches(self):
        """测试替换文件内容（要求替换所有但只有一次匹配）"""
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
