"""Unit tests for the config module."""

import unittest
import tempfile
import os

from linhai.config import ConfigValidationError, load_config, Config


def create_temp_config(config_content: str) -> str:
    """创建临时配置文件并返回路径"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(config_content)
        return f.name


class TestConfig(unittest.TestCase):
    """Test cases for the config module."""

    def test_load_config_valid(self):
        """Test loading a valid config."""
        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write('''[[llm]]
name = "primary"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
''')
            temp_file = f.name

        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 1)
            self.assertEqual(config.llm[0].name, "primary")
            self.assertEqual(config.llm[0].base_url, "https://api.example.com")
            self.assertEqual(config.llm[0].api_key, "test_key")
            self.assertEqual(config.llm[0].model, "test_model")
        finally:
            # 清理临时文件
            os.unlink(temp_file)

    def test_load_config_invalid_url(self):
        """Test loading a config with invalid URL."""
        config_content = '''[[llm]]
name = "primary"
base_url = "invalid_url"
api_key = "test_key"
model = "test_model"
'''
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(ConfigValidationError):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_empty_api_key(self):
        """Test loading a config with empty API key."""
        config_content = '''[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = ""
model = "test_model"
'''
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(ConfigValidationError):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_empty_model(self):
        """Test loading a config with empty model."""
        config_content = '''[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = ""
'''
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(ConfigValidationError):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_optional_fields(self):
        """Test loading a config with optional fields."""
        config_content = '''[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[agent]
compress_threshold_soft = 30000
compress_threshold_hard = 60000

[memory]
file_path = "./test_memory.md"

[tools]
max_output_length = 2000
'''
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(config.llm[0].base_url, "https://api.example.com")
            self.assertIsNotNone(config.agent)
            assert config.agent is not None
            self.assertEqual(config.agent.compress_threshold_soft, 30000.0)
            self.assertEqual(config.agent.compress_threshold_hard, 60000.0)
            self.assertIsNotNone(config.memory)
            assert config.memory is not None
            self.assertEqual(config.memory.file_path, "./test_memory.md")
            self.assertIsNotNone(config.tools)
            assert config.tools is not None
            self.assertEqual(config.tools.max_output_length, 2000)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_int_values(self):
        """Test loading a config with integer values for compress thresholds."""
        config_content = '''[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[agent]
compress_threshold_soft = 30000
compress_threshold_hard = 60000
'''
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertIsNotNone(config.agent)
            assert config.agent is not None
            self.assertEqual(config.agent.compress_threshold_soft, 30000)
            self.assertEqual(config.agent.compress_threshold_hard, 60000)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_float_values(self):
        """Test loading a config with float values for compress thresholds."""
        config_content = '''[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[agent]
compress_threshold_soft = 0.5
compress_threshold_hard = 0.8
'''
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertIsNotNone(config.agent)
            assert config.agent is not None
            self.assertEqual(config.agent.compress_threshold_soft, 0.5)
            self.assertEqual(config.agent.compress_threshold_hard, 0.8)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_defaults(self):
        """Test loading a config with default values."""
        config_content = '''[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
'''
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            # 检查默认值
            self.assertIsNone(config.agent)
            self.assertIsNone(config.memory)
            self.assertIsNone(config.tools)
        finally:
            os.unlink(temp_file)

    def test_load_config_multiple_llms(self):
        """Test loading a config with multiple LLMs."""
        config_content = '''[[llm]]
name = "primary"
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"

[[llm]]
name = "secondary"
base_url = "https://api.example.org"
api_key = "test_key_2"
model = "test_model_2"
'''
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 2)

            # 验证第一个LLM
            self.assertEqual(config.llm[0].name, "primary")
            self.assertEqual(config.llm[0].base_url, "https://api.example.com")
            self.assertEqual(config.llm[0].api_key, "test_key_1")
            self.assertEqual(config.llm[0].model, "test_model_1")

            # 验证第二个LLM
            self.assertEqual(config.llm[1].name, "secondary")
            self.assertEqual(config.llm[1].base_url, "https://api.example.org")
            self.assertEqual(config.llm[1].api_key, "test_key_2")
            self.assertEqual(config.llm[1].model, "test_model_2")
        finally:
            os.unlink(temp_file)

    def test_load_config_multiple_llms_with_optional_fields(self):
        """Test loading a config with multiple LLMs and optional fields."""
        config_content = '''[[llm]]
name = "main"
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"

[[llm]]
name = "backup"
base_url = "https://api.example.org"
api_key = "test_key_2"
model = "test_model_2"

[agent]
compress_threshold_soft = 0.5
compress_threshold_hard = 0.8

[memory]
file_path = "./test_memory.md"

[tools]
max_output_length = 2000
'''
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 2)

            # 验证LLMs
            self.assertEqual(config.llm[0].name, "main")
            self.assertEqual(config.llm[1].name, "backup")

            # 验证可选字段
            self.assertIsNotNone(config.agent)
            assert config.agent is not None
            self.assertEqual(config.agent.compress_threshold_soft, 0.5)
            self.assertEqual(config.agent.compress_threshold_hard, 0.8)
            self.assertIsNotNone(config.memory)
            assert config.memory is not None
            self.assertEqual(config.memory.file_path, "./test_memory.md")
            self.assertIsNotNone(config.tools)
            assert config.tools is not None
            self.assertEqual(config.tools.max_output_length, 2000)
        finally:
            os.unlink(temp_file)

    def test_load_config_multiple_llms_invalid_name(self):
        """Test loading a config with multiple LLMs with empty name."""
        config_content = '''[[llm]]
name = ""
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"
'''
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(ConfigValidationError):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_openai_kwargs(self):
        """Test loading a config with client_options and completion_options."""
        config_content = '''[[llm]]
name = "qwen"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key = "test_key"
model = "qwen-plus"

[llm.client_options]
timeout = 30

[llm.completion_options.stream_options]
include_usage = true
'''
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 1)
            self.assertEqual(config.llm[0].name, "qwen")
            self.assertEqual(
                config.llm[0].base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            self.assertEqual(config.llm[0].api_key, "test_key")
            self.assertEqual(config.llm[0].model, "qwen-plus")
            self.assertEqual(config.llm[0].client_options, {"timeout": 30})
            self.assertEqual(
                config.llm[0].completion_options,
                {"stream_options": {"include_usage": True}},
            )
        finally:
            os.unlink(temp_file)

    def test_load_config_with_type_and_compatibility(self):
        """Test loading a config with type and compatibility fields."""
        config_content = '''[[llm]]
name = "minimax"
type = "openai"
compatibility = "minimax"
base_url = "https://api.minimaxi.com/v1"
api_key = "test_key"
model = "MiniMax-M2"

[[llm]]
name = "openai"
type = "openai"
base_url = "https://api.openai.com"
api_key = "test_key_2"
model = "gpt-4"
'''
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 2)
            
            # 验证第一个LLM (minimax)
            self.assertEqual(config.llm[0].name, "minimax")
            self.assertEqual(config.llm[0].type, "openai")
            self.assertEqual(config.llm[0].compatibility, "minimax")
            self.assertEqual(config.llm[0].base_url, "https://api.minimaxi.com/v1")
            self.assertEqual(config.llm[0].model, "MiniMax-M2")
            
            # 验证第二个LLM (openai)
            self.assertEqual(config.llm[1].name, "openai")
            self.assertEqual(config.llm[1].type, "openai")
            self.assertIsNone(config.llm[1].compatibility)
            self.assertEqual(config.llm[1].base_url, "https://api.openai.com")
            self.assertEqual(config.llm[1].model, "gpt-4")
        finally:
            os.unlink(temp_file)

    def test_load_config_default_type_and_compatibility(self):
        """Test loading a config with default values for type and compatibility."""
        config_content = '''[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
'''
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 1)
            # 检查默认值
            self.assertEqual(config.llm[0].type, "openai")
            self.assertIsNone(config.llm[0].compatibility)
        finally:
            os.unlink(temp_file)


if __name__ == "__main__":
    unittest.main()
