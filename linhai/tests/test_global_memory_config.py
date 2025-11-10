"""测试全局记忆配置功能"""

import os
import tempfile
import shutil
from pathlib import Path
import unittest
import asyncio

from linhai.agent.main import _create_init_messages
from linhai.group_chat import GroupChat


class TestGlobalMemoryConfig(unittest.TestCase):
    """测试全局记忆配置"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir()
        self.working_dir = Path(self.temp_dir) / "working"
        self.working_dir.mkdir()
        
        # 创建测试用的group_chat
        self.group_chat = GroupChat()

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def test_memory_file_path_absolute(self):
        """测试绝对路径的全局记忆文件"""
        # 创建全局记忆文件
        memory_file = Path(self.temp_dir) / "custom_memory.md"
        memory_file.write_text("# 自定义全局记忆\n- 测试内容")
        
        # 测试_create_init_messages
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            init_messages = loop.run_until_complete(
                _create_init_messages(
                    group_chat=self.group_chat,
                    system_prompt="测试系统提示",
                    memory_file_path=str(memory_file)
                )
            )
            
            # 检查是否包含自定义全局记忆
            memory_messages = [msg for msg in init_messages if hasattr(msg, 'filepath')]
            self.assertGreater(len(memory_messages), 0)
            
            # 检查文件路径是否正确
            custom_memory_found = False
            for msg in memory_messages:
                if hasattr(msg, 'filepath') and msg.filepath == memory_file:
                    custom_memory_found = True
                    break
            
            self.assertTrue(custom_memory_found, "未找到自定义全局记忆文件")
            
        finally:
            loop.close()

    def test_memory_file_path_relative(self):
        """测试相对路径的全局记忆文件"""
        # 在当前工作目录创建全局记忆文件
        memory_file = Path("./") / "test_relative_memory.md"
        memory_file.write_text("# 相对路径全局记忆\n- 测试内容")
        
        # 测试_create_init_messages
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            init_messages = loop.run_until_complete(
                _create_init_messages(
                    group_chat=self.group_chat,
                    system_prompt="测试系统提示",
                    memory_file_path="test_relative_memory.md"
                )
            )
            
            # 检查是否包含相对路径全局记忆
            memory_messages = [msg for msg in init_messages if hasattr(msg, 'filepath')]
            self.assertGreater(len(memory_messages), 0)
            
            # 检查文件路径是否正确
            relative_memory_found = False
            for msg in memory_messages:
                if hasattr(msg, 'filepath') and msg.filepath.name == "test_relative_memory.md":
                    relative_memory_found = True
                    # 检查文件是否存在
                    self.assertTrue(msg.filepath.exists(), "相对路径文件不存在")
                    break
            
            self.assertTrue(relative_memory_found, "未找到相对路径全局记忆文件")
            
        finally:
            loop.close()
            # 清理测试文件
            if memory_file.exists():
                memory_file.unlink()

    def test_memory_file_path_none(self):
        """测试未提供memory_file_path时使用默认路径"""
        # 测试_create_init_messages
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            init_messages = loop.run_until_complete(
                _create_init_messages(
                    group_chat=self.group_chat,
                    system_prompt="测试系统提示",
                    memory_file_path=None
                )
            )
            
            # 检查是否包含默认全局记忆
            memory_messages = [msg for msg in init_messages if hasattr(msg, 'filepath')]
            self.assertGreater(len(memory_messages), 0)
            
            # 检查是否包含默认路径
            default_memory_found = False
            default_path = Path("~/.config/linhai/LINHAI.md").expanduser()
            for msg in memory_messages:
                if hasattr(msg, 'filepath') and str(msg.filepath) == str(default_path):
                    default_memory_found = True
                    break
            
            self.assertTrue(default_memory_found, "未找到默认全局记忆文件")
            
        finally:
            loop.close()

    def test_project_memory_files(self):
        """测试项目记忆文件自动加载"""
        # 在当前目录创建项目记忆文件
        project_files = ["LINHAI.md", "AGENT.md", "CLAUDE.md"]
        created_files = []
        
        try:
            for filename in project_files:
                file_path = Path("./") / filename
                file_path.write_text(f"# {filename}\n- 测试内容")
                created_files.append(file_path)
            
            # 测试_create_init_messages
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                init_messages = loop.run_until_complete(
                    _create_init_messages(
                        group_chat=self.group_chat,
                        system_prompt="测试系统提示",
                        memory_file_path=None
                    )
                )
                
                # 检查是否包含项目记忆文件
                memory_messages = [msg for msg in init_messages if hasattr(msg, 'filepath')]
                
                # 检查每个项目文件是否都被加载
                for filename in project_files:
                    file_found = False
                    for msg in memory_messages:
                        if hasattr(msg, 'filepath') and msg.filepath.name == filename:
                            file_found = True
                            break
                    self.assertTrue(file_found, f"未找到项目记忆文件: {filename}")
                    
            finally:
                loop.close()
                
        finally:
            # 清理测试文件
            for file_path in created_files:
                if file_path.exists():
                    file_path.unlink()


if __name__ == "__main__":
    unittest.main()