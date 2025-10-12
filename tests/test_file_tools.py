"""文件操作工具的单元测试"""

import unittest
import tempfile
import os
from pathlib import Path

# 导入要测试的工具
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

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
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_read_file(self):
        """测试读取文件"""
        result = read_file(str(self.test_file))
        self.assertIn("文件路径为:", result)
        self.assertIn("第一行内容", result)

    def test_read_file_with_line_numbers(self):
        """测试带行号的读取文件"""
        result = read_file(str(self.test_file), show_line_numbers=True)
        self.assertIn("1: 第一行内容", result)
        self.assertIn("2: 第二行内容", result)

    def test_write_file(self):
        """测试写入文件"""
        new_content = "新的文件内容"
        result = write_file(str(self.test_file), new_content)
        self.assertIn("成功写入文件", result)
        
        # 验证内容确实被写入
        content = self.test_file.read_text(encoding="utf-8")
        self.assertEqual(content, new_content)

    def test_append_file(self):
        """测试追加文件"""
        append_content = "\n追加的内容"
        result = append_file(str(self.test_file), append_content)
        self.assertIn("成功写入文件", result)
        
        # 验证内容被追加
        content = self.test_file.read_text(encoding="utf-8")
        self.assertIn("追加的内容", content)
        self.assertTrue(content.endswith("追加的内容"))

    def test_replace_file_content_default_behavior(self):
        """测试替换文件内容默认行为（只替换第一次出现）"""
        # 测试默认只替换第一次出现
        result = replace_file_content(
            str(self.test_file), 
            "重复内容", 
            "替换后的内容"
        )
        
        # 应该返回错误，因为有多处匹配但未设置replace_all
        self.assertIn("找到3次匹配", result)
        self.assertIn("默认只替换第一次出现", result)

    def test_replace_file_content_single_match(self):
        """测试替换文件内容（单次匹配）"""
        # 修改文件内容为只有一次匹配
        single_match_content = "第一行\n第二行\n第三行\n重复内容\n第五行"
        self.test_file.write_text(single_match_content, encoding="utf-8")
        
        result = replace_file_content(
            str(self.test_file), 
            "重复内容", 
            "替换后的内容"
        )
        
        self.assertIn("已替换", result)
        
        # 验证内容被替换
        content = self.test_file.read_text(encoding="utf-8")
        self.assertIn("替换后的内容", content)
        self.assertEqual(content.count("替换后的内容"), 1)

    def test_replace_file_content_replace_all(self):
        """测试替换文件内容（替换所有匹配）"""
        result = replace_file_content(
            str(self.test_file), 
            "重复内容", 
            "替换后的内容",
            replace_all=True
        )
        
        self.assertIn("已替换", result)
        self.assertIn("替换次数: 3", result)
        
        # 验证所有匹配都被替换
        content = self.test_file.read_text(encoding="utf-8")
        self.assertEqual(content.count("替换后的内容"), 3)
        self.assertNotIn("重复内容", content)

    def test_replace_file_content_not_found(self):
        """测试替换不存在的文件内容"""
        result = replace_file_content(
            str(self.test_file), 
            "不存在的字符串", 
            "新内容"
        )
        
        self.assertIn("未找到", result)

    def test_list_files(self):
        """测试列出文件"""
        # 在临时目录中创建一些测试文件和文件夹
        (Path(self.temp_dir) / "test1.txt").write_text("test1")
        (Path(self.temp_dir) / "test2.txt").write_text("test2")
        (Path(self.temp_dir) / "subdir").mkdir()
        
        result = list_files(self.temp_dir)
        self.assertIn("test1.txt", result)
        self.assertIn("test2.txt", result)
        self.assertIn("subdir", result)

    def test_get_absolute_path(self):
        """测试获取绝对路径"""
        result = get_absolute_path(".")
        self.assertIn("绝对路径:", result)
        self.assertIn(os.path.abspath("."), result)

    def test_insert_at_line(self):
        """测试在指定行插入内容"""
        result = insert_at_line(
            str(self.test_file),
            line_number=3,
            content="插入的新行",
            expected_line_content="第三行内容"
        )
        
        self.assertIn("成功在文件", result)
        
        # 验证内容被正确插入
        content = self.test_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        self.assertEqual(lines[2], "插入的新行")  # 第3行应该是插入的内容
        self.assertEqual(lines[3], "第三行内容")  # 原来的第3行现在应该是第4行


if __name__ == "__main__":
    unittest.main()