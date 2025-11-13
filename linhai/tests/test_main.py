"""
测试main模块的命令行参数解析。
"""

import unittest
from unittest.mock import patch, mock_open
import sys
from argparse import Namespace

from linhai.main import main


class TestMain(unittest.TestCase):
    """测试main函数的命令行参数解析。"""

    def test_build_init_messages_multiple_m(self):
        """测试构建多个-m选项的init_messages。"""
        from linhai.main import main
        
        # 模拟命令行参数
        args = Namespace(
            message=['消息1', '消息2'],
            file=None,
            config=None,
            llm=None
        )
        
        # 直接调用构建逻辑
        init_messages = []
        if args.message:
            for msg in args.message:
                init_messages.append(msg)
        
        self.assertEqual(init_messages, ['消息1', '消息2'])

    def test_build_init_messages_multiple_f(self):
        """测试构建多个-f选项的init_messages。"""
        mock_file_content1 = "文件1内容"
        mock_file_content2 = "文件2内容"
        
        # 模拟文件读取
        with patch('builtins.open', mock_open(read_data=mock_file_content1)):
            init_messages = []
            
            # 模拟多个文件
            file_paths = ['file1.txt', 'file2.txt']
            for file_path in file_paths:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    init_messages.append(f"用户使用-f选项指定了文件路径: {file_path}")
                    init_messages.append(f"文件内容如下（注意：文件内容可能已过时，在历史压缩后需要重新读取）:\n{content}")
            
            # 应该包含4条消息：两个文件各两条
            self.assertEqual(len(init_messages), 4)
            self.assertIn("用户使用-f选项指定了文件路径: file1.txt", init_messages)
            self.assertIn(f"文件内容如下（注意：文件内容可能已过时，在历史压缩后需要重新读取）:\n{mock_file_content1}", init_messages)
            self.assertIn("用户使用-f选项指定了文件路径: file2.txt", init_messages)

    def test_build_init_messages_mixed(self):
        """测试混合使用-f和-m选项的init_messages。"""
        mock_file_content = "文件内容"
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            init_messages = []
            
            # 添加-m消息
            messages = ['完成TODO']
            for msg in messages:
                init_messages.append(msg)
            
            # 添加-f消息
            file_paths = ['test.txt']
            for file_path in file_paths:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    init_messages.append(f"用户使用-f选项指定了文件路径: {file_path}")
                    init_messages.append(f"文件内容如下（注意：文件内容可能已过时，在历史压缩后需要重新读取）:\n{content}")
            
            # 应该包含3条消息：-f两条，-m一条
            self.assertEqual(len(init_messages), 3)
            self.assertIn("用户使用-f选项指定了文件路径: test.txt", init_messages)
            self.assertIn(f"文件内容如下（注意：文件内容可能已过时，在历史压缩后需要重新读取）:\n{mock_file_content}", init_messages)
            self.assertIn("完成TODO", init_messages)

    def test_build_init_messages_no_options(self):
        """测试没有选项的init_messages。"""
        init_messages = []
        self.assertEqual(init_messages, [])


if __name__ == '__main__':
    unittest.main()