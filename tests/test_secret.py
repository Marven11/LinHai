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
from linhai.agent.base import RuntimeMessage


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
        secrets_dict = load_secrets_from_config(
            str(self.secret_file), base_dir=Path(self.temp_dir)
        )

        self.assertIn("OPENAI_API_TOKEN", secrets_dict)
        self.assertIn("DEEPSEEK_API_KEY", secrets_dict)
        self.assertIn("SSH_PASSWORD", secrets_dict)

        self.assertEqual(secrets_dict["OPENAI_API_TOKEN"]["value"], "sk-test-123456")
        self.assertEqual(
            secrets_dict["OPENAI_API_TOKEN"]["description"],
            "OpenAI API token for testing",
        )
        # 测试disabled_in_toolcall_argument字段，默认为False
        self.assertEqual(
            secrets_dict["OPENAI_API_TOKEN"]["disabled_in_toolcall_argument"], False
        )
        self.assertEqual(
            secrets_dict["DEEPSEEK_API_KEY"]["disabled_in_toolcall_argument"], False
        )
        self.assertEqual(
            secrets_dict["SSH_PASSWORD"]["disabled_in_toolcall_argument"], False
        )

    def test_load_secrets_with_disabled_in_toolcall_argument(self):
        """测试加载包含disabled_in_toolcall_argument字段的secret配置"""
        # 创建新的TOML文件包含disabled_in_toolcall_argument字段
        secret_content = """[secrets]
SECRET1 = { value = "val1", description = "desc1", disabled_in_toolcall_argument = false }
SECRET2 = { value = "val2", description = "desc2", disabled_in_toolcall_argument = true }
"""
        secret_file2 = Path(self.temp_dir) / "test_secret2.toml"
        secret_file2.write_text(secret_content)

        secrets_dict = load_secrets_from_config(
            str(secret_file2), base_dir=Path(self.temp_dir)
        )

        self.assertIn("SECRET1", secrets_dict)
        self.assertIn("SECRET2", secrets_dict)
        self.assertEqual(
            secrets_dict["SECRET1"]["disabled_in_toolcall_argument"], False
        )
        self.assertEqual(secrets_dict["SECRET2"]["disabled_in_toolcall_argument"], True)
        # 测试缺失字段时默认为False
        secret_content3 = """[secrets]
SECRET3 = { value = "val3", description = "desc3" }
"""
        secret_file3 = Path(self.temp_dir) / "test_secret3.toml"
        secret_file3.write_text(secret_content3)
        secrets_dict3 = load_secrets_from_config(
            str(secret_file3), base_dir=Path(self.temp_dir)
        )
        self.assertEqual(
            secrets_dict3["SECRET3"]["disabled_in_toolcall_argument"], False
        )

    def test_load_secrets_from_config_with_base_dir(self):
        """测试基于base_dir加载secret配置"""
        # 创建子目录结构
        base_dir = Path(self.temp_dir) / "config"
        base_dir.mkdir()
        secret_file_in_subdir = base_dir / "secret.toml"

        # 复制secret内容到子目录文件
        secret_content = """[secrets]
TEST_KEY = { value = "test-value", description = "Test key" }
"""
        secret_file_in_subdir.write_text(secret_content)

        # 使用相对路径和base_dir加载
        secrets_dict = load_secrets_from_config("secret.toml", base_dir=base_dir)

        self.assertIn("TEST_KEY", secrets_dict)
        self.assertEqual(secrets_dict["TEST_KEY"]["value"], "test-value")
        self.assertEqual(secrets_dict["TEST_KEY"]["description"], "Test key")

        # 测试绝对路径不受base_dir影响
        secrets_dict2 = load_secrets_from_config(
            str(secret_file_in_subdir), base_dir=Path("/dummy")
        )
        self.assertIn("TEST_KEY", secrets_dict2)

        # 测试base_dir为None时相对路径基于当前目录（应失败，因为文件不在当前目录）
        with self.assertRaises(FileNotFoundError):
            load_secrets_from_config("secret.toml", base_dir=Path("/invalid/dir"))

    def test_load_secrets_file_not_found(self):
        """测试文件不存在时直接崩溃"""
        with self.assertRaises(FileNotFoundError):
            load_secrets_from_config("/nonexistent/path", base_dir=Path(self.temp_dir))

    def test_load_secrets_invalid_toml(self):
        """测试无效TOML格式时直接崩溃"""
        invalid_file = Path(self.temp_dir) / "invalid.toml"
        invalid_file.write_text("invalid toml content")

        with self.assertRaises(Exception):  # 可能是TOMLDecodeError
            load_secrets_from_config(str(invalid_file), base_dir=Path(self.temp_dir))

    def test_load_secrets_missing_section(self):
        """测试缺少secrets部分时直接崩溃"""
        no_secrets_file = Path(self.temp_dir) / "no_secrets.toml"
        no_secrets_file.write_text('[other_section]\nkey = "value"')

        with self.assertRaises(Exception):
            load_secrets_from_config(str(no_secrets_file), base_dir=Path(self.temp_dir))

    def test_replace_secrets_in_string(self):
        """测试替换字符串中的secret键"""
        secrets_dict: dict[str, SecretInfo] = {
            "OPENAI_API_TOKEN": {
                "value": "sk-real-key",
                "description": "",
                "disabled_in_toolcall_argument": False,
            },
            "DEEPSEEK_API_KEY": {
                "value": "sk-deepseek",
                "description": "",
                "disabled_in_toolcall_argument": False,
            },
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
            "API_KEY": {
                "value": "sk-123",
                "description": "",
                "disabled_in_toolcall_argument": False,
            },
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
            "KEY": {
                "value": "secret-value",
                "description": "",
                "disabled_in_toolcall_argument": False,
            },
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
            "API_KEY": {
                "value": "sk-123",
                "description": "",
                "disabled_in_toolcall_argument": False,
            },
            "PASSWORD": {
                "value": "pass123",
                "description": "",
                "disabled_in_toolcall_argument": False,
            },
        }

        # 测试基本掩码
        input_str = "key is sk-123 and password is pass123"
        result = mask_secrets_in_object(
            input_str, secrets_dict, ["API_KEY", "PASSWORD"]
        )
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
            "SECRET": {
                "value": "secret123",
                "description": "",
                "disabled_in_toolcall_argument": False,
            },
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
            "OPENAI_API_TOKEN": {
                "value": "sk-123",
                "description": "OpenAI API token",
                "disabled_in_toolcall_argument": False,
            },
            "SSH_PASSWORD": {
                "value": "pass123",
                "description": "SSH私钥密码",
                "disabled_in_toolcall_argument": False,
            },
        }
        message = get_available_secrets_message(secrets_dict)
        expected = "当前可用secret键: <$OPENAI_API_TOKEN$> - OpenAI API token (disabled_in_toolcall_argument=False); <$SSH_PASSWORD$> - SSH私钥密码 (disabled_in_toolcall_argument=False)"
        self.assertEqual(message, expected)

    def test_get_available_secrets_message_with_disabled(self):
        """测试生成可用secret消息时显示disabled_in_toolcall_argument标记"""
        secrets_dict: dict[str, SecretInfo] = {
            "SECRET1": {
                "value": "val1",
                "description": "desc1",
                "disabled_in_toolcall_argument": False,
            },
            "SECRET2": {
                "value": "val2",
                "description": "desc2",
                "disabled_in_toolcall_argument": True,
            },
        }
        message = get_available_secrets_message(secrets_dict)
        expected = "当前可用secret键: <$SECRET1$> - desc1 (disabled_in_toolcall_argument=False); <$SECRET2$> - desc2 (disabled_in_toolcall_argument=True)"
        self.assertEqual(message, expected)

    def test_get_available_secrets_message_empty(self):
        """测试生成可用secret消息时字典为空"""
        # 测试空字典
        self.assertEqual(get_available_secrets_message({}), "无可用secret键")


class MockRegistry:
    """模拟Registry用于测试"""

    def __init__(self):
        self.members = {}

    def register_member(self, name, obj):
        self.members[name] = obj

    def get_member_typechecked(self, name, _type=None):
        if name in self.members:
            return self.members[name]
        raise RuntimeError(f"Member {name} not found")


class TestSecretInterceptorPlugin(unittest.TestCase):
    """测试SecretInterceptorPlugin的6个场景"""

    def setUp(self):
        self.secrets_dict: dict[str, SecretInfo] = {
            "SECRET1": {
                "value": "secret-value-1",
                "description": "",
                "disabled_in_toolcall_argument": False,
            },
            "SECRET2": {
                "value": "secret-value-2",
                "description": "",
                "disabled_in_toolcall_argument": False,
            },
        }
        self.mock_registry = MockRegistry()
        from linhai.secret import SecretInterceptorPlugin

        self.plugin = SecretInterceptorPlugin(self.mock_registry, self.secrets_dict)

    def test_intercept_when_no_with_secret_and_contains_secret(self):
        """测试：如果没有指定with_secret，结果/错误信息中包含secret值，应该完全拦截"""
        import asyncio
        from pathlib import Path
        from linhai.agent.conversation import register_conversation_folder

        # 使用真实Registry并注册conversation_folder
        from linhai.registry import Registry

        real_registry = Registry()
        register_conversation_folder(real_registry)

        # 重新创建plugin使用真实registry
        from linhai.secret import SecretInterceptorPlugin

        real_plugin = SecretInterceptorPlugin(real_registry, self.secrets_dict)

        result_content = "This contains secret-value-1 and some other text"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            real_plugin.after_toolcall(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=RuntimeMessage(result_content),
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()

        self.assertIsNotNone(result, "结果应该被拦截")
        result_str = str(result)
        self.assertIn("本插件拦截", result_str)
        self.assertNotIn("secret-value-1", result_str)

    def test_no_intercept_when_no_with_secret_and_no_secret(self):
        """测试：如果没有指定with_secret，结果/错误信息中不包含secret值，应该完全不拦截"""
        import asyncio

        result_content = "This contains no secret"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.plugin.after_toolcall(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=RuntimeMessage(result_content),
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()

        self.assertIsNone(result, "结果不应该被拦截")

    def test_mask_when_with_secret_and_contains_secret(self):
        """测试：如果指定with_secret，结果/错误信息中包含secret值，应该替换为`<$KEY$>`占位符"""
        import asyncio

        result_content = "This contains secret-value-1 and secret-value-2"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.plugin.after_toolcall(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=RuntimeMessage(result_content),
                toolcall_arguments={},
                with_secret=["SECRET1", "SECRET2"],
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()

        self.assertIsNotNone(result, "结果应该被处理")
        result_str = str(result)
        self.assertIn("<<masked>>", result_str)
        self.assertIn("<$SECRET1$>", result_str)
        self.assertIn("<$SECRET2$>", result_str)
        self.assertNotIn("secret-value-1", result_str)
        self.assertNotIn("secret-value-2", result_str)

    def test_intercept_when_incomplete_with_secret_and_contains_unlisted_secret(self):
        """测试：如果指定的with_secret不完全，结果/错误信息中包含没有在with_secret中指定的secret值，应该完全拦截"""
        import asyncio
        from pathlib import Path
        from linhai.agent.conversation import register_conversation_folder
        from linhai.registry import Registry
        from linhai.secret import SecretInterceptorPlugin

        # 使用真实Registry并注册conversation_folder
        real_registry = Registry()
        register_conversation_folder(real_registry)

        # 重新创建plugin使用真实registry
        real_plugin = SecretInterceptorPlugin(real_registry, self.secrets_dict)

        result_content = "This contains secret-value-1 and secret-value-2"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            real_plugin.after_toolcall(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=RuntimeMessage(result_content),
                toolcall_arguments={},
                with_secret=["SECRET1"],  # 只指定了SECRET1，但结果包含SECRET2
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()

        self.assertIsNotNone(result, "结果应该被拦截")
        result_str = str(result)
        self.assertIn("本插件拦截", result_str)
        self.assertNotIn("secret-value-2", result_str)

    def test_mask_when_incomplete_with_secret_and_no_unlisted_secret(self):
        """测试：如果指定的with_secret不完全，结果/错误信息中不包含没有在with_secret中指定的secret值，应该替换为`<$KEY$>`占位符"""
        import asyncio

        result_content = "This contains secret-value-1"  # 只包含SECRET1，而with_secret也只指定了SECRET1

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.plugin.after_toolcall(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=RuntimeMessage(result_content),
                toolcall_arguments={},
                with_secret=["SECRET1"],
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()

        self.assertIsNotNone(result, "结果应该被处理")
        result_str = str(result)
        self.assertIn("<<masked>>", result_str)
        self.assertIn("<$SECRET1$>", result_str)
        self.assertNotIn("secret-value-1", result_str)

    def test_before_tool_call_no_with_secret(self):
        """测试：如果没有指定with_secret，参数中包含`<$KEY$>`占位符，什么都不做"""
        import asyncio

        toolcall_arguments = {"key": "API key is <$SECRET1$>"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.plugin.before_tool_call(
                tool_name="test_tool",
                toolcall_arguments=toolcall_arguments,
                with_secret=None,
            )
        )
        loop.close()

        self.assertIsNone(result, "应该返回None")

    def test_before_tool_call_with_secret_no_placeholder(self):
        """测试：如果指定了with_secret，参数中不包含`<$KEY$>`占位符，什么都不做"""
        import asyncio

        toolcall_arguments = {"key": "API key without placeholder"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.plugin.before_tool_call(
                tool_name="test_tool",
                toolcall_arguments=toolcall_arguments,
                with_secret=["SECRET1"],
            )
        )
        loop.close()

        # 应该返回相同的参数，因为没有占位符需要替换
        self.assertEqual(result, toolcall_arguments)

    def test_before_tool_call_with_secret_and_placeholder(self):
        """测试：如果指定了with_secret，参数中包含`<$KEY$>`占位符，递归替换"""
        import asyncio

        toolcall_arguments = {
            "key": "API key is <$SECRET1$>",
            "nested": {"inner": "Nested <$SECRET2$>"},
            "list": ["Item with <$SECRET1$>", "Plain item"],
        }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.plugin.before_tool_call(
                tool_name="test_tool",
                toolcall_arguments=toolcall_arguments,
                with_secret=["SECRET1", "SECRET2"],
            )
        )
        loop.close()

        expected = {
            "key": "API key is secret-value-1",
            "nested": {"inner": "Nested secret-value-2"},
            "list": ["Item with secret-value-1", "Plain item"],
        }
        self.assertEqual(result, expected)

    def test_before_tool_call_secret_not_found(self):
        """测试：如果指定了with_secret但是其中的secret没有找到，返回ToolResultFailed"""
        import asyncio
        from linhai.tool.base import ToolResultFailed

        toolcall_arguments = {"key": "API key is <$NONEXISTENT$>"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.plugin.before_tool_call(
                tool_name="test_tool",
                toolcall_arguments=toolcall_arguments,
                with_secret=["NONEXISTENT"],
            )
        )
        loop.close()

        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("NONEXISTENT", result.content)

    def test_before_tool_call_with_placeholder_in_with_secret(self):
        """测试：如果指定了with_secret，参数中包含`<$KEY$>`占位符，但是with_secret中包含的是`<$KEY$>`而不是`KEY`字符串，返回ToolResultFailed"""
        import asyncio
        from linhai.tool.base import ToolResultFailed

        toolcall_arguments = {"key": "API key is <$SECRET1$>"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.plugin.before_tool_call(
                tool_name="test_tool",
                toolcall_arguments=toolcall_arguments,
                with_secret=["<$SECRET1$>"],  # 包含占位符而不是KEY
            )
        )
        loop.close()

        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("<$SECRET1$>", result.content)

    def test_before_tool_call_placeholder_not_in_with_secret(self):
        """测试：如果指定了with_secret，参数中包含`<$KEY$>`占位符，但是`<$KEY$>`占位符没有在with_secret中指定，不替换这个占位符"""
        import asyncio

        toolcall_arguments = {
            "key1": "API key is <$SECRET1$>",
            "key2": "Another key is <$SECRET2$>",
        }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.plugin.before_tool_call(
                tool_name="test_tool",
                toolcall_arguments=toolcall_arguments,
                with_secret=["SECRET1"],  # 只指定了SECRET1，不替换SECRET2
            )
        )
        loop.close()

        expected = {
            "key1": "API key is secret-value-1",
            "key2": "Another key is <$SECRET2$>",  # 保持原样
        }
        self.assertEqual(result, expected)

    def test_before_tool_call_complex_nested_structure(self):
        """测试：如果指定了with_secret，参数非常复杂，嵌套很深，在一个很深的嵌套中有一个很长的字符串包含多个对应的`<$KEY$>`占位符，替换"""
        import asyncio

        toolcall_arguments = {
            "level1": {
                "level2": [
                    {"level3": "Deep nested <$SECRET1$> and <$SECRET2$>"},
                    "Just a string",
                    {"another": {"deep": "Very <$SECRET1$> deep"}},
                ],
                "simple": "Simple <$SECRET2$> here",
            },
            "list_of_dicts": [
                {"key": "First <$SECRET1$>"},
                {"key": "Second <$SECRET2$>"},
            ],
        }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.plugin.before_tool_call(
                tool_name="test_tool",
                toolcall_arguments=toolcall_arguments,
                with_secret=["SECRET1", "SECRET2"],
            )
        )
        loop.close()

        expected = {
            "level1": {
                "level2": [
                    {"level3": "Deep nested secret-value-1 and secret-value-2"},
                    "Just a string",
                    {"another": {"deep": "Very secret-value-1 deep"}},
                ],
                "simple": "Simple secret-value-2 here",
            },
            "list_of_dicts": [
                {"key": "First secret-value-1"},
                {"key": "Second secret-value-2"},
            ],
        }
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
