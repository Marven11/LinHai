"""Tests for config writer module."""

import tempfile
from pathlib import Path
import unittest

import tomllib

from unittest.mock import patch

from linhai.init.config_writer import write_llm_config


class TestWriteLLMConfig(unittest.TestCase):
    """Tests for write_llm_config function."""

    def test_write_new_config(self):
        """Test writing a new config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            write_llm_config(
                name="test-llm",
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
                config_path=config_path,
            )

            self.assertTrue(config_path.exists())

            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            self.assertIn("llm", config)
            self.assertEqual(len(config["llm"]), 1)
            self.assertEqual(config["llm"][0]["name"], "test-llm")
            self.assertEqual(config["llm"][0]["base_url"], "https://api.test.com/v1")
            self.assertEqual(config["llm"][0]["api_key"], "test-key")
            self.assertEqual(config["llm"][0]["model"], "test-model")

    def test_overwrite_existing_config(self):
        """Test overwriting existing config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            # Write initial config
            write_llm_config(
                name="initial",
                base_url="https://initial.com",
                api_key="initial-key",
                model="initial-model",
                config_path=config_path,
            )

            # Overwrite with new config
            write_llm_config(
                name="updated",
                base_url="https://updated.com",
                api_key="updated-key",
                model="updated-model",
                config_path=config_path,
                overwrite=True,
            )

            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            self.assertEqual(config["llm"][0]["name"], "updated")


class TestConfigLoadable(unittest.TestCase):
    """Test that generated config can be loaded by Config class."""

    def test_generated_config_is_loadable(self):
        """Test that config written by write_llm_config can be loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            write_llm_config(
                name="test-llm",
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
                config_path=config_path,
            )

            from linhai.config import load_config

            loaded_config = load_config(config_path)

            self.assertEqual(len(loaded_config.llm), 1)
            self.assertEqual(loaded_config.llm[0].name, "test-llm")
            self.assertEqual(loaded_config.llm[0].base_url, "https://api.test.com/v1")
            self.assertEqual(loaded_config.llm[0].api_key, "test-key")
            self.assertEqual(loaded_config.llm[0].model, "test-model")


class TestSandboxInit(unittest.TestCase):

    def test_write_config_contains_agent_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            write_llm_config(
                name="test-llm",
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
                config_path=config_path,
            )
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            self.assertIn("agent", config)
            self.assertEqual(config["agent"][0]["name"], "default")

    @patch("linhai.init.config_writer.platform.system", return_value="Linux")
    @patch("linhai.init.config_writer.shutil.which", return_value=None)
    def test_no_sandbox_when_no_bwrap(self, mock_which, mock_sys):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            write_llm_config(
                name="test-llm",
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
                config_path=config_path,
            )
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            self.assertNotIn("process_sandbox", config["agent"][0])

    @patch("linhai.init.config_writer.platform.system", return_value="Linux")
    @patch("linhai.init.config_writer.shutil.which", return_value="/usr/bin/bwrap")
    @patch("linhai.init.config_writer.Path.exists", return_value=True)
    def test_nixos_bwrap_config_generated(self, mock_exists, mock_which, mock_sys):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            write_llm_config(
                name="test-llm",
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
                config_path=config_path,
                overwrite=True,
            )
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            argv = config["agent"][0]["process_sandbox"]["bubblewrap"]["argv"]
            self.assertEqual(argv[0], "bwrap")
            self.assertIn("/nix", argv)

    @patch("linhai.init.config_writer.platform.system", return_value="Linux")
    @patch("linhai.init.config_writer.shutil.which", return_value="/usr/bin/bwrap")
    @patch("linhai.init.config_writer.Path.exists", return_value=False)
    def test_fhs_bwrap_config_generated(self, mock_exists, mock_which, mock_sys):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            write_llm_config(
                name="test-llm",
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
                config_path=config_path,
            )
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            argv = config["agent"][0]["process_sandbox"]["bubblewrap"]["argv"]
            self.assertEqual(argv[0], "bwrap")
            self.assertIn("/usr", argv)
            self.assertNotIn("/nix", argv)

    @patch("linhai.init.config_writer.platform.system", return_value="Darwin")
    @patch("os.getcwd", return_value="/workdir")
    def test_macos_sandbox_profile_generated(self, mock_cwd, mock_sys):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            write_llm_config(
                name="test-llm",
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
                config_path=config_path,
            )
            profile_path = Path(tmpdir) / "sandbox_profile.sb"
            self.assertTrue(profile_path.exists())
            content = profile_path.read_text()
            self.assertIn("/workdir", content)
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            sandbox = config["agent"][0]["process_sandbox"]["macos_sandbox"]
            self.assertEqual(sandbox["sandbox_profile"], str(profile_path))


if __name__ == "__main__":
    unittest.main()
