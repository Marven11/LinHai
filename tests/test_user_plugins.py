import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase

from linhai.agent.create import (
    _load_user_plugins,
    create_agent_build_context,
    AgentBuildArguments,
)
from linhai.config import AgentConfig, Config, LLMConfig
from linhai.registry import Registry


class TestUserPluginsConfig(TestCase):

    def test_plugins_default_none(self):
        config = AgentConfig()
        self.assertIsNone(config.plugins)

    def test_plugins_set(self):
        config = AgentConfig(plugins=["example_plugin"])
        self.assertEqual(config.plugins, ["example_plugin"])

    def test_plugins_in_full_config(self):
        config = Config(
            llm=[
                LLMConfig(
                    name="test",
                    base_url="http://localhost:11434",
                    api_key="test",
                    model="test",
                )
            ],
            agent=[AgentConfig(plugins=["my_plugin"])],
        )
        self.assertEqual(config.agent[0].plugins, ["my_plugin"])


class TestLoadUserPlugins(TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.plugins_dir = Path(self.tmpdir) / "plugins"
        self.plugins_dir.mkdir()
        plugin_dir = self.plugins_dir / "test_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text(
            "register_linhai_plugins_called = False\n\n"
            "def register_linhai_plugins(registry, lifecycle):\n"
            "    global register_linhai_plugins_called\n"
            "    register_linhai_plugins_called = True\n"
        )

    def test_load_user_plugins_basic(self):
        registry = Registry()

        class FakeLifecycle:
            pass

        fake_lifecycle = FakeLifecycle()
        _load_user_plugins(
            ["test_plugin"],
            registry,
            fake_lifecycle,
            Path(self.tmpdir),
        )
        module = sys.modules.get("test_plugin")
        assert module is not None
        self.assertTrue(module.register_linhai_plugins_called)

    def test_load_user_plugins_missing_function(self):
        bad_plugin_dir = self.plugins_dir / "bad_plugin"
        bad_plugin_dir.mkdir()
        (bad_plugin_dir / "__init__.py").write_text("pass\n")

        registry = Registry()

        class FakeLifecycle:
            pass

        with self.assertRaises(ValueError) as ctx:
            _load_user_plugins(
                ["bad_plugin"],
                registry,
                FakeLifecycle(),
                Path(self.tmpdir),
            )
        self.assertIn("register_linhai_plugins", str(ctx.exception))

    def test_load_user_plugins_no_basedir_raises(self):
        registry = Registry()

        class FakeLifecycle:
            pass

        with self.assertRaises(ValueError) as ctx:
            _load_user_plugins(
                ["any_plugin"],
                registry,
                FakeLifecycle(),
                None,
            )
        self.assertIn("config_basedir", str(ctx.exception))

    def test_plugins_in_build_context(self):
        config = Config(
            llm=[
                LLMConfig(
                    name="test",
                    base_url="http://localhost:11434",
                    api_key="test",
                    model="test",
                )
            ],
            agent=[AgentConfig(plugins=["my_plugin"])],
        )
        registry = Registry()
        build_args = AgentBuildArguments(
            rss=[],
            telegram=False,
            disable_waiting_marker=False,
            afk=False,
            claw_enabled=False,
            claw_folder=None,
            message=[],
            file=[],
            planning=False,
            llm_name=None,
            profile_name=None,
        )
        context = create_agent_build_context(registry, config, Path("/tmp"), build_args)
        self.assertEqual(context["plugins"], ["my_plugin"])

    def test_plugins_none_in_build_context(self):
        config = Config(
            llm=[
                LLMConfig(
                    name="test",
                    base_url="http://localhost:11434",
                    api_key="test",
                    model="test",
                )
            ],
            agent=[AgentConfig()],
        )
        registry = Registry()
        build_args = AgentBuildArguments(
            rss=[],
            telegram=False,
            disable_waiting_marker=False,
            afk=False,
            claw_enabled=False,
            claw_folder=None,
            message=[],
            file=[],
            planning=False,
            llm_name=None,
            profile_name=None,
        )
        context = create_agent_build_context(registry, config, Path("/tmp"), build_args)
        self.assertIsNone(context["plugins"])
