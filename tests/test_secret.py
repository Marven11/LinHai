"""Secret模块的单元测试"""

import unittest
import tempfile
import os
from pathlib import Path

from linhai.secret import (
    load_secrets_from_config,
    replace_secrets_in_object,
    mask_secrets_in_object,
    get_available_secrets_message,
    SecretInfo,
)


class TestSecretFunctions(unittest.TestCase):
    """测试secret辅助函数"""
    
    def setUp(self):
        # 创建临时TOML文件用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.secret_file = Path(self.temp_dir) / "test_secret.toml"
        
        secret_content = """[secrets]
OPENAI_API_TOKEN = { value = "sk-test-123456", description = "OpenAI API token for testing" }
DEEPSEEK_API_KEY = { value = "sk-deepseek-test", description = "DeepSeek API key" }
SSH_PASSWORD = { value = "testpassword", description = "SSH私钥密码" }
"""
        self.secret_file.write_text(secret_content)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_load_secrets_from_config(self):
        """测试加载secret配置"""
        secrets_dict = load_secrets_from_config(str(self.secret_file))
        
        self.assertIn("OPENAI_API_TOKEN", secrets_dict)
        self.assertIn("DEEPSEEK_API_KEY", secrets_dict)
        self.assertIn("SSH_PASSWORD", secrets_dict)
        
        self.assertEqual(secrets_dict["OPENAI_API_TOKEN"]["value"], "sk-test-123456")
        self.assertEqual(secrets_dict["OPENAI_API_TOKEN"]["description"], "OpenAI API token for testing")
    
    def test_load_secrets_file_not_found(self):
        """测试文件不存在时直接崩溃"""
        with self.assertRaises(FileNotFoundError):
            load_secrets_from_config("/nonexistent/path")
    
    def test_load_secrets_invalid_toml(self):
        """测试无效TOML格式时直接崩溃"""
        invalid_file = Path(self.temp_dir) / "invalid.toml"
        invalid_file.write_text("invalid toml content")
        
        with self.assertRaises(Exception):  # 可能是TOMLDecodeError
            load_secrets_from_config(str(invalid_file))
    
    def test_load_secrets_missing_section(self):
        """测试缺少secrets部分时直接崩溃"""
        no_secrets_file = Path(self.temp_dir) / "no_secrets.toml"
        no_secrets_file.write_text("[other_section]\nkey = \"value\"")
        
        with self.assertRaises(Exception):
            load_secrets_from_config(str(no_secrets_file))
    
    def test_replace_secrets_in_string(self):
        """测试替换字符串中的secret键"""
        secrets_dict: dict[str, SecretInfo] = {
            "OPENAI_API_TOKEN": {"value": "sk-real-key", "description": ""},
            "DEEPSEEK_API_KEY": {"value": "sk-deepseek", "description": ""},
        }
        
        # 测试基本替换
        input_str = "API_KEY = <$OPENAI_API_TOKEN$>"
        secret_keys = ["OPENAI_API_TOKEN"]
        result = replace_secrets_in_object(input_str, secrets_dict, secret_keys)
        self.assertEqual(result, "API_KEY = sk-real-key")
        
        # 测试多个secret键
        input_str = "keys: <$OPENAI_API_TOKEN$>, <$DEEPSEEK_API_KEY$>"
        secret_keys = ["OPENAI_API_TOKEN", "DEEPSEEK_API_KEY"]
        result = replace_secrets_in_object(input_str, secrets_dict, secret_keys)
        self.assertEqual(result, "keys: sk-real-key, sk-deepseek")
        
        # 测试未在with_secret中指定的键不替换
        input_str = "keys: <$OPENAI_API_TOKEN$>, <$DEEPSEEK_API_KEY$>"
        secret_keys = ["OPENAI_API_TOKEN"]  # 只指定一个
        result = replace_secrets_in_object(input_str, secrets_dict, secret_keys)
        self.assertEqual(result, "keys: sk-real-key, <$DEEPSEEK_API_KEY$>")
        
        # 测试不存在的键（在with_secret中）会怎样？实际上应该在before_tool_call中被拦截
        # 这里函数会尝试替换，但key不在secrets_dict中，所以保持原样
        input_str = "keys: <$NONEXISTENT$>"
        secret_keys = ["NONEXISTENT"]
        result = replace_secrets_in_object(input_str, secrets_dict, secret_keys)
        self.assertEqual(result, "keys: <$NONEXISTENT$>")
    
    def test_replace_secrets_in_dict(self):
        """测试替换字典中的secret键"""
        secrets_dict: dict[str, SecretInfo] = {
            "API_KEY": {"value": "sk-123", "description": ""},
        }
        
        input_dict = {
            "key1": "value1",
            "key2": "API key is <$API_KEY$>",
            "key3": {
                "nested": "nested key: <$API_KEY$>",
            },
        }
        secret_keys = ["API_KEY"]
        
        result = replace_secrets_in_object(input_dict, secrets_dict, secret_keys)
        
        self.assertEqual(result["key1"], "value1")
        self.assertEqual(result["key2"], "API key is sk-123")
        self.assertEqual(result["key3"]["nested"], "nested key: sk-123")
    
    def test_replace_secrets_in_list(self):
        """测试替换列表中的secret键"""
        secrets_dict: dict[str, SecretInfo] = {
            "KEY": {"value": "secret-value", "description": ""},
        }
        
        input_list = [
            "item1",
            "item2 with <$KEY$>",
            ["nested", "with <$KEY$>"],
        ]
        secret_keys = ["KEY"]
        
        result = replace_secrets_in_object(input_list, secrets_dict, secret_keys)
        
        self.assertEqual(result[0], "item1")
        self.assertEqual(result[1], "item2 with secret-value")
        self.assertEqual(result[2][0], "nested")
        self.assertEqual(result[2][1], "with secret-value")
    
    def test_mask_secrets_in_string(self):
        """测试掩码字符串中的secret值"""
        secrets_dict: dict[str, SecretInfo] = {
            "API_KEY": {"value": "sk-123", "description": ""},
            "PASSWORD": {"value": "pass123", "description": ""},
        }
        
        # 测试基本掩码
        input_str = "key is sk-123 and password is pass123"
        result = mask_secrets_in_object(input_str, secrets_dict, ["API_KEY", "PASSWORD"])
        self.assertEqual(result, "key is <$API_KEY$> and password is <$PASSWORD$>")
        
        # 测试长值优先替换（避免子串问题）
        secrets_dict2: dict[str, SecretInfo] = {
            "SHORT": {"value": "abc", "description": ""},
            "LONG": {"value": "abcdef", "description": ""},
        }
        input_str = "value: abcdef"
        result = mask_secrets_in_object(input_str, secrets_dict2, ["SHORT", "LONG"])
        # 应该替换长的值
        self.assertEqual(result, "value: <$LONG$>")
    
    def test_mask_secrets_in_nested_structures(self):
        """测试掩码嵌套结构中的secret值"""
        secrets_dict: dict[str, SecretInfo] = {
            "SECRET": {"value": "secret123", "description": ""},
        }
        
        input_dict = {
            "key1": "value with secret123",
            "key2": ["list item", "another with secret123"],
            "key3": {
                "nested": "nested with secret123",
            },
        }
        
        result = mask_secrets_in_object(input_dict, secrets_dict, ["SECRET"])
        
        self.assertEqual(result["key1"], "value with <$SECRET$>")
        self.assertEqual(result["key2"][0], "list item")
        self.assertEqual(result["key2"][1], "another with <$SECRET$>")
        self.assertEqual(result["key3"]["nested"], "nested with <$SECRET$>")
    
    def test_get_available_secrets_message(self):
        """测试生成可用secret消息"""
        secrets_dict: dict[str, SecretInfo] = {
            "OPENAI_API_TOKEN": {"value": "sk-123", "description": "OpenAI API token"},
            "SSH_PASSWORD": {"value": "pass123", "description": "SSH私钥密码"},
        }
        
        message = get_available_secrets_message(secrets_dict)
        expected = "当前可用secret键: <$OPENAI_API_TOKEN$> - OpenAI API token; <$SSH_PASSWORD$> - SSH私钥密码"
        self.assertEqual(message, expected)
        
        # 测试空字典
        self.assertEqual(get_available_secrets_message({}), "无可用secret键")


class TestSecretInterceptorPlugin(unittest.TestCase):
    """测试SecretInterceptorPlugin"""
    
    def setUp(self):
        # 创建mock对象
        self.mock_group_chat = MockGroupChat()
        # 创建并注册mock agent
        class MockAgent:
            def __init__(self):
                self.message_processor = MockMessageProcessor()
        class MockMessageProcessor:
            def __init__(self):
                self.messages = []
            def add_new_message(self, msg):
                self.messages.append(msg)
        mock_agent = MockAgent()
        self.mock_group_chat.register_member("agent", mock_agent)
        self.secrets_dict: dict[str, SecretInfo] = {
            "OPENAI_API_TOKEN": {"value": "sk-real-key", "description": ""},
            "DEEPSEEK_API_KEY": {"value": "sk-deepseek", "description": ""},
        }
        
    def test_before_tool_call_with_valid_secrets(self):
        """测试before_tool_call有效secret替换"""
        from linhai.secret import SecretInterceptorPlugin
        from linhai.llm import ToolCallMessage
        
        plugin = SecretInterceptorPlugin(self.mock_group_chat, self.secrets_dict)
        
        # 创建工具调用
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={
                "api_key": "<$OPENAI_API_TOKEN$>",
                "other": "value",
            },
            with_secret=["OPENAI_API_TOKEN", "DEEPSEEK_API_KEY"],
            assert_success=True,
        )
        
        # 调用before_tool_call
        import asyncio
        result = asyncio.run(plugin.before_tool_call(tool_call))
        
        self.assertFalse(result)  # 不应该拦截
        self.assertEqual(tool_call.function_arguments["api_key"], "sk-real-key")
        self.assertEqual(tool_call.function_arguments["other"], "value")
    
    def test_before_tool_call_with_missing_secrets(self):
        """测试before_tool_call缺失secret键时拦截"""
        from linhai.secret import SecretInterceptorPlugin
        from linhai.llm import ToolCallMessage
        
        plugin = SecretInterceptorPlugin(self.mock_group_chat, self.secrets_dict)
        
        # 创建工具调用，包含不存在的secret键
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={"key": "value"},
            with_secret=["NONEXISTENT", "OPENAI_API_TOKEN"],
            assert_success=True,
        )
        
        import asyncio
        result = asyncio.run(plugin.before_tool_call(tool_call))
        
        self.assertTrue(result)  # 应该拦截


class MockGroupChat:
    """模拟GroupChat用于测试"""
    def __init__(self):
        self.members = {}
    
    def register_member(self, name, obj):
        self.members[name] = obj
    
    def get_members(self, name, _type=None):
        if name in self.members:
            return self.members[name]
        raise RuntimeError(f"Member {name} not found")


class TestSecretIntegrationBugFix(unittest.TestCase):
    """测试secret系统集成bug修复"""
    
    def test_secret_leakage_bug(self):
        """重现secret泄漏bug：当agent读取包含secret的文件时，secret值应该被拦截或掩码"""
        from linhai.secret import SecretInterceptorPlugin
        from linhai.llm import ToolCallMessage
        
        # 模拟真实场景中的secret值
        secret_value = "sk-123456"
        secrets_dict: dict[str, SecretInfo] = {
            "DEEPSEEK_API_KEY": {"value": secret_value, "description": "DeepSeek API key"},
        }
        
        class MockGroupChat:
            def __init__(self):
                self.members = {}
            
            def register_member(self, name, obj):
                self.members[name] = obj
            
            def get_members(self, name, _type=None):
                if name in self.members:
                    return self.members[name]
                raise RuntimeError(f"Member {name} not found")
        
        plugin = SecretInterceptorPlugin(MockGroupChat(), secrets_dict)
        
        # 场景1：agent读取包含secret的文件，但没有指定with_secret
        # 这应该触发拦截
        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": ".secret.toml"},
            with_secret=None,  # 没有指定secret权限
            assert_success=True,
        )
        
        # 模拟工具返回的结果（包含secret值）
        class MockToolResult:
            def __init__(self, content):
                self._content = content
            
            def to_llm_message(self):
                return {"content": self._content}
            
            def __str__(self):
                return self._content
        
        tool_result = MockToolResult(f"api_key = {secret_value}")
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_tool_call(None, tool_call, tool_result, True)
        )
        loop.close()
        
        # 验证结果被拦截
        self.assertIsNotNone(result, "结果应该被拦截")
        result_str = str(result)
        self.assertIn("已拦截", result_str, "应该提示已拦截")
        self.assertNotIn(secret_value, result_str, "secret值不应该出现在拦截消息中")
    
    def test_secret_replacement_with_hyphen(self):
        """测试包含连字符的secret值的替换功能"""
        from linhai.secret import replace_secrets_in_object
        
        secret_value = "sk-123456"
        secrets_dict: dict[str, SecretInfo] = {
            "DEEPSEEK_API_KEY": {"value": secret_value, "description": ""},
        }
        
        # 测试在工具调用参数中替换secret键
        input_str = f"api_key = <$DEEPSEEK_API_KEY$>"
        secret_keys = ["DEEPSEEK_API_KEY"]
        
        result = replace_secrets_in_object(input_str, secrets_dict, secret_keys)
        
        self.assertEqual(result, f"api_key = {secret_value}", "secret键应该被替换为实际值")
    
    def test_mask_secret_with_hyphen(self):
        """测试包含连字符的secret值的掩码功能"""
        from linhai.secret import mask_secrets_in_object
        
        secret_value = "sk-123456"
        secrets_dict: dict[str, SecretInfo] = {
            "DEEPSEEK_API_KEY": {"value": secret_value, "description": ""},
        }
        
        # 测试在工具结果中掩码secret值
        input_str = f"api_key = {secret_value}"
        result = mask_secrets_in_object(input_str, secrets_dict, ["DEEPSEEK_API_KEY"])
        
        expected = "api_key = <$DEEPSEEK_API_KEY$>"
        self.assertEqual(result, expected, "secret值应该被掩码为<$KEY$>格式")


if __name__ == "__main__":
    unittest.main()