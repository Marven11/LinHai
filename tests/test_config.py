"""Unit tests for the config module."""

import unittest
import tempfile
import os

from linhai.config import ConfigValidationError, load_config, Config


def create_temp_config(config_content: str) -> str:
    """创建临时配置文件并返回路径"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        return f.name


class TestConfig(unittest.TestCase):
    """Test cases for the config module."""

    def test_load_config_valid(self):
        """Test loading a valid config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""[[llm]]
name = "primary"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
""")
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
            os.unlink(temp_file)

    def test_load_config_invalid_url(self):
        """Test loading a config with invalid URL."""
        config_content = """[[llm]]
name = "primary"
base_url = "invalid_url"
api_key = "test_key"
model = "test_model"
"""
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(ConfigValidationError):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_empty_api_key(self):
        """Test loading a config with empty API key."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = ""
model = "test_model"
"""
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(Exception):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_empty_model(self):
        """Test loading a config with empty model."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = ""
"""
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(Exception):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_optional_fields(self):
        """Test loading a config with optional fields."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
compress_threshold = 60000

[user_prompt]
file_path = "./test_prompt.md"
reminder_file_path = "./test_reminder.md"

[tools]
max_toolcall_token_in_round = 2000
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(config.llm[0].base_url, "https://api.example.com")
            self.assertIsNotNone(config.agent)
            self.assertEqual(len(config.agent), 1)
            self.assertEqual(config.agent[0].compress_threshold, 60000)
            self.assertIsNotNone(config.user_prompt)
            assert config.user_prompt is not None
            self.assertEqual(config.user_prompt.file_path, "./test_prompt.md")
            self.assertIsNotNone(config.tools)
            assert config.tools is not None
            self.assertEqual(config.tools.max_toolcall_token_in_round, 2000)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_int_values(self):
        """Test loading a config with integer values for compress thresholds."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
compress_threshold = 60000
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertIsNotNone(config.agent)
            self.assertEqual(len(config.agent), 1)
            self.assertEqual(config.agent[0].compress_threshold, 60000)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_float_values(self):
        """Test loading a config with float values for compress thresholds."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
compress_threshold = 0.8
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertIsNotNone(config.agent)
            self.assertEqual(len(config.agent), 1)
            self.assertEqual(config.agent[0].compress_threshold, 0.8)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_defaults(self):
        """Test loading a config with default values."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[user_prompt]
file_path = "./test_prompt.md"
reminder_file_path = "./test_reminder.md"
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertIsNotNone(config.agent)
            self.assertEqual(config.agent, [])
            # user_prompt现在有默认值，检查默认值
            self.assertIsNotNone(config.user_prompt)
            self.assertEqual(config.user_prompt.file_path, "./test_prompt.md")
            self.assertEqual(
                config.user_prompt.reminder_file_path, "./test_reminder.md"
            )
            # tools现在有默认值，不再是None
            self.assertIsNotNone(config.tools)
            self.assertEqual(config.tools.max_toolcall_token_in_round, 0.3)
        finally:
            os.unlink(temp_file)

    def test_load_config_multiple_llms(self):
        """Test loading a config with multiple LLMs."""
        config_content = """[[llm]]
name = "primary"
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"

[[llm]]
name = "secondary"
base_url = "https://api.example.org"
api_key = "test_key_2"
model = "test_model_2"
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 2)

            self.assertEqual(config.llm[0].name, "primary")
            self.assertEqual(config.llm[0].base_url, "https://api.example.com")
            self.assertEqual(config.llm[0].api_key, "test_key_1")
            self.assertEqual(config.llm[0].model, "test_model_1")

            self.assertEqual(config.llm[1].name, "secondary")
            self.assertEqual(config.llm[1].base_url, "https://api.example.org")
            self.assertEqual(config.llm[1].api_key, "test_key_2")
            self.assertEqual(config.llm[1].model, "test_model_2")
        finally:
            os.unlink(temp_file)

    def test_load_config_multiple_llms_with_optional_fields(self):
        """Test loading a config with multiple LLMs and optional fields."""
        config_content = """[[llm]]
name = "main"
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"

[[llm]]
name = "backup"
base_url = "https://api.example.org"
api_key = "test_key_2"
model = "test_model_2"

[[agent]]
compress_threshold = 0.8

[user_prompt]
file_path = "./test_prompt.md"
reminder_file_path = "./test_reminder.md"

[tools]
max_toolcall_token_in_round = 2000
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 2)

            self.assertEqual(config.llm[0].name, "main")
            self.assertEqual(config.llm[1].name, "backup")

            self.assertIsNotNone(config.agent)
            self.assertEqual(len(config.agent), 1)
            self.assertEqual(config.agent[0].compress_threshold, 0.8)
            self.assertIsNotNone(config.user_prompt)
            assert config.user_prompt is not None
            self.assertEqual(config.user_prompt.file_path, "./test_prompt.md")
            self.assertIsNotNone(config.tools)
            assert config.tools is not None
            self.assertEqual(config.tools.max_toolcall_token_in_round, 2000)
        finally:
            os.unlink(temp_file)

    def test_load_config_multiple_llms_invalid_name(self):
        """Test loading a config with multiple LLMs with empty name."""
        config_content = """[[llm]]
name = ""
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"
"""
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(Exception):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_openai_kwargs(self):
        """Test loading a config with client_options and completion_options."""
        config_content = """[[llm]]
name = "qwen"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key = "test_key"
model = "qwen-plus"

[llm.client_options]
timeout = 30

[llm.completion_options.stream_options]
include_usage = true
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 1)
            self.assertEqual(config.llm[0].name, "qwen")
            self.assertEqual(
                config.llm[0].base_url,
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
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
        config_content = """[[llm]]
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
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 2)

            self.assertEqual(config.llm[0].name, "minimax")
            self.assertEqual(config.llm[0].type, "openai")
            self.assertEqual(config.llm[0].compatibility, "minimax")
            self.assertEqual(config.llm[0].base_url, "https://api.minimaxi.com/v1")
            self.assertEqual(config.llm[0].model, "MiniMax-M2")

            self.assertEqual(config.llm[1].name, "openai")
            self.assertEqual(config.llm[1].type, "openai")
            # compatibility现在默认为空字符串
            self.assertEqual(config.llm[1].compatibility, "")
            self.assertEqual(config.llm[1].base_url, "https://api.openai.com")
            self.assertEqual(config.llm[1].model, "gpt-4")
        finally:
            os.unlink(temp_file)

    def test_load_config_default_type_and_compatibility(self):
        """Test loading a config with default values for type and compatibility."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 1)
            self.assertEqual(config.llm[0].type, "openai")
            # compatibility现在默认为空字符串
            self.assertEqual(config.llm[0].compatibility, "")
        finally:
            os.unlink(temp_file)

    def test_toolsets_default_all_enabled(self):
        from linhai.config import ToolConfig

        config = ToolConfig()
        self.assertIsNone(config.enable_toolsets)
        self.assertIsNone(config.disable_toolsets)

    def test_enable_toolsets(self):
        from linhai.config import ToolConfig

        config = ToolConfig(enable_toolsets=["utils", "sleep"])
        self.assertEqual(config.enable_toolsets, ["utils", "sleep"])

    def test_disable_toolsets(self):
        from linhai.config import ToolConfig

        config = ToolConfig(disable_toolsets=["llm"])
        self.assertEqual(config.disable_toolsets, ["llm"])

    def test_enable_toolsets_invalid(self):
        from linhai.config import ToolConfig, ConfigValidationError

        with self.assertRaises(ConfigValidationError):
            ToolConfig(enable_toolsets=["invalid_toolset"])

    def test_disable_toolsets_invalid(self):
        from linhai.config import ToolConfig, ConfigValidationError

        with self.assertRaises(ConfigValidationError):
            ToolConfig(disable_toolsets=["invalid_toolset"])

    def test_enable_and_disable_mutually_exclusive(self):
        from linhai.config import ToolConfig, ConfigValidationError

        with self.assertRaises(ConfigValidationError):
            ToolConfig(enable_toolsets=["utils"], disable_toolsets=["llm"])

    def test_available_toolsets(self):
        from linhai.config import AVAILABLE_TOOLSETS

        expected = {
            "utils",
            "sleep",
            "machine_control",
            "multimodal",
            "llm",
            "context_cleaning",
            "mcp",
            "web_search",
            "telegram",
            "problem",
        }
        self.assertEqual(set(AVAILABLE_TOOLSETS), expected)

    def test_agent_enable_toolsets_none(self):
        from linhai.config import AgentConfig

        config = AgentConfig()
        self.assertIsNone(config.enable_toolsets)
        self.assertIsNone(config.disable_toolsets)

    def test_agent_enable_toolsets_with_list(self):
        from linhai.config import AgentConfig

        config = AgentConfig(enable_toolsets=["utils", "sleep"])
        self.assertEqual(config.enable_toolsets, ["utils", "sleep"])

    def test_agent_disable_toolsets_with_list(self):
        from linhai.config import AgentConfig

        config = AgentConfig(disable_toolsets=["llm"])
        self.assertEqual(config.disable_toolsets, ["llm"])

    def test_agent_enable_and_disable_mutually_exclusive(self):
        from linhai.config import AgentConfig, ConfigValidationError

        with self.assertRaises(ConfigValidationError):
            AgentConfig(enable_toolsets=["utils"], disable_toolsets=["llm"])

    def test_agent_enable_toolsets_invalid(self):
        from linhai.config import AgentConfig, ConfigValidationError

        with self.assertRaises(ConfigValidationError):
            AgentConfig(enable_toolsets=["invalid"])

    def test_agent_disable_toolsets_invalid(self):
        from linhai.config import AgentConfig, ConfigValidationError

        with self.assertRaises(ConfigValidationError):
            AgentConfig(disable_toolsets=["invalid"])

    def test_agent_enable_toolsets_in_full_config(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
enable_toolsets = ["utils", "sleep"]
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertEqual(config.agent[0].enable_toolsets, ["utils", "sleep"])
        finally:
            os.unlink(temp_file)

    def test_agent_disable_toolsets_in_full_config(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
disable_toolsets = ["llm"]
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertEqual(config.agent[0].disable_toolsets, ["llm"])
        finally:
            os.unlink(temp_file)

    def test_load_config_with_process_sandbox_macos(self):
        """Test loading a config with macOS sandbox configuration."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
[agent.process_sandbox.macos_sandbox]
sandbox_profile = "sandbox.sb"
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsNotNone(config.agent[0].process_sandbox)
            assert config.agent[0].process_sandbox is not None
            self.assertIsNotNone(config.agent[0].process_sandbox.macos_sandbox)
            self.assertEqual(
                config.agent[0].process_sandbox.macos_sandbox.sandbox_profile,
                "sandbox.sb",
            )
            self.assertIsNone(config.agent[0].process_sandbox.bubblewrap)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_process_sandbox_bubblewrap(self):
        """Test loading a config with Linux bubblewrap configuration."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
[agent.process_sandbox.bubblewrap]
argv_template = ["bwrap", "--ro-bind", "/", "/"]
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsNotNone(config.agent[0].process_sandbox)
            assert config.agent[0].process_sandbox is not None
            self.assertIsNone(config.agent[0].process_sandbox.macos_sandbox)
            self.assertIsNotNone(config.agent[0].process_sandbox.bubblewrap)
            self.assertEqual(
                config.agent[0].process_sandbox.bubblewrap.argv_template,
                ["bwrap", "--ro-bind", "/", "/"],
            )
        finally:
            os.unlink(temp_file)

    def test_load_config_with_process_sandbox_both(self):
        """Test loading a config with both platform sandbox configurations."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
[agent.process_sandbox.macos_sandbox]
sandbox_profile = "sandbox.sb"
[agent.process_sandbox.bubblewrap]
argv_template = ["bwrap", "--ro-bind", "/", "/"]
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsNotNone(config.agent[0].process_sandbox)
            assert config.agent[0].process_sandbox is not None
            self.assertIsNotNone(config.agent[0].process_sandbox.macos_sandbox)
            self.assertIsNotNone(config.agent[0].process_sandbox.bubblewrap)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_llm_compress_threshold_float(self):
        """Test loading LLM config with float compress_threshold."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
compress_threshold = 0.6
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertEqual(config.llm[0].compress_threshold, 0.6)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_llm_compress_threshold_int(self):
        """Test loading LLM config with int compress_threshold."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
compress_threshold = 50000
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertEqual(config.llm[0].compress_threshold, 50000)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_llm_compress_threshold_default_none(self):
        """Test LLM config compress_threshold defaults to None."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsNone(config.llm[0].compress_threshold)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_llm_compress_threshold_invalid_float(self):
        """Test LLM config with invalid float compress_threshold."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
compress_threshold = 1.5
"""
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(Exception):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_llm_compress_threshold_invalid_int(self):
        """Test LLM config with invalid int compress_threshold."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
compress_threshold = 0
"""
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(Exception):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_remote_shell_control_default_python(self):
        from linhai.config import ToolConfig

        tools = ToolConfig()
        self.assertEqual(tools.remote_shell_control, "python")

    def test_remote_shell_control_accepts_python(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[tools]
remote_shell_control = "python"
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertEqual(config.tools.remote_shell_control, "python")
        finally:
            os.unlink(temp_file)

    def test_remote_shell_control_accepts_bash(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[tools]
remote_shell_control = "bash"
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertEqual(config.tools.remote_shell_control, "bash")
        finally:
            os.unlink(temp_file)

    def test_remote_shell_control_rejects_auto(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[tools]
remote_shell_control = "auto"
"""
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(ConfigValidationError):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_duplicate_llm_names(self):
        """Test that duplicate LLM names are rejected."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[llm]]
name = "test_llm"
base_url = "https://api.example.org"
api_key = "test_key_2"
model = "test_model_2"
"""
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(ConfigValidationError):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_with_process_sandbox_none(self):
        """Test loading a config without sandbox configuration."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[agent]]
compress_threshold = 0.8
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsNone(config.agent[0].process_sandbox)
        finally:
            os.unlink(temp_file)

    def test_load_config_api_key_from_env(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = {type = "env", name = "TEST_API_KEY_1703"}
model = "test_model"
"""
        os.environ["TEST_API_KEY_1703"] = "env_key_value"
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertEqual(config.llm[0].api_key, "env_key_value")
        finally:
            os.unlink(temp_file)
            del os.environ["TEST_API_KEY_1703"]

    def test_load_config_api_key_env_not_found(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = {type = "env", name = "TEST_API_KEY_MISSING_1703"}
model = "test_model"
"""
        os.environ.pop("TEST_API_KEY_MISSING_1703", None)
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(ConfigValidationError):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_api_key_env_missing_name(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = {type = "env"}
model = "test_model"
"""
        temp_file = create_temp_config(config_content)
        try:
            with self.assertRaises(ConfigValidationError):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_config_api_key_plain_still_works(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "plain_key"
model = "test_model"
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertEqual(config.llm[0].api_key, "plain_key")
        finally:
            os.unlink(temp_file)


if __name__ == "__main__":
    unittest.main()
