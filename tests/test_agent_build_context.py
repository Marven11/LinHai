"""测试create_agent_build_context - profile解析、参数映射、配置合并"""

import unittest
import tempfile
import os
from pathlib import Path

from linhai.config import Config, load_config
from linhai.agent.create import (
    create_agent_build_context,
    AgentBuildArguments,
    _resolve_agent_profile,
)
from linhai.registry import Registry


def _make_config(config_content: str) -> tuple[Config, str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        f.flush()
        path = f.name
    return load_config(path), path


class TestProfileResolution(unittest.TestCase):

    def test_default_profile_when_single_agent(self):
        config, tmpfile = _make_config("""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "key"
model = "model"

[[agent]]
name = "default"
compress_threshold = 0.8
""")
        try:
            profile = _resolve_agent_profile(config, None)
            self.assertEqual(profile.name, "default")
        finally:
            os.unlink(tmpfile)

    def test_profile_by_name(self):
        config, tmpfile = _make_config("""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "key"
model = "model"

[[agent]]
name = "dev"
compress_threshold = 0.6

[[agent]]
name = "prod"
compress_threshold = 0.8
""")
        try:
            profile = _resolve_agent_profile(config, "prod")
            self.assertEqual(profile.name, "prod")
            self.assertEqual(profile.compress_threshold, 0.8)
        finally:
            os.unlink(tmpfile)

    def test_profile_nonexistent_raises(self):
        config, tmpfile = _make_config("""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "key"
model = "model"

[[agent]]
name = "default"
compress_threshold = 0.8
""")
        try:
            with self.assertRaises(ValueError) as ctx:
                _resolve_agent_profile(config, "nonexistent")
            self.assertIn("nonexistent", str(ctx.exception))
        finally:
            os.unlink(tmpfile)

    def test_profile_no_agents_raises(self):
        config, tmpfile = _make_config("""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "key"
model = "model"
""")
        try:
            with self.assertRaises(ValueError):
                _resolve_agent_profile(config, None)
        finally:
            os.unlink(tmpfile)


class TestBuildContextParameterMapping(unittest.TestCase):

    def _base_config(self):
        return """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "key"
model = "model"

[[agent]]
name = "default"
compress_threshold = 0.8
"""

    def test_llm_name_resolution(self):
        config, tmpfile = _make_config(self._base_config())
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": False,
                "claw_folder": None,
                "message": [],
                "file": [],
                "planning": False,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertEqual(context["llm_name"], "test")
        finally:
            os.unlink(tmpfile)

    def test_llm_name_override(self):
        config, tmpfile = _make_config("""
[[llm]]
name = "llm1"
base_url = "https://example.com"
api_key = "key"
model = "model"

[[llm]]
name = "llm2"
base_url = "https://example.org"
api_key = "key2"
model = "model2"

[[agent]]
name = "default"
compress_threshold = 0.8
""")
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": False,
                "claw_folder": None,
                "message": [],
                "file": [],
                "planning": False,
                "llm_name": "llm2",
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertEqual(context["llm_name"], "llm2")
        finally:
            os.unlink(tmpfile)

    def test_planning_enabled_via_cli(self):
        config, tmpfile = _make_config(self._base_config())
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": False,
                "claw_folder": None,
                "message": [],
                "file": [],
                "planning": True,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertTrue(context["planning"])
        finally:
            os.unlink(tmpfile)

    def test_claw_enabled_via_cli(self):
        config, tmpfile = _make_config(self._base_config())
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": True,
                "claw_folder": Path("/tmp/claw"),
                "message": [],
                "file": [],
                "planning": False,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertTrue(context["claw_enabled"])
            self.assertEqual(context["claw_folder"], Path("/tmp/claw"))
        finally:
            os.unlink(tmpfile)

    def test_afk_enabled(self):
        config, tmpfile = _make_config(self._base_config())
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": True,
                "claw_enabled": False,
                "claw_folder": None,
                "message": [],
                "file": [],
                "planning": False,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertTrue(context["afk"])
        finally:
            os.unlink(tmpfile)

    def test_message_and_file_in_context(self):
        config, tmpfile = _make_config(self._base_config())
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": False,
                "claw_folder": None,
                "message": ["msg1", "msg2"],
                "file": [Path("a.txt"), Path("b.txt")],
                "planning": False,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertEqual(context["message"], ["msg1", "msg2"])
            self.assertEqual(len(context["file"]), 2)
        finally:
            os.unlink(tmpfile)

    def test_allowed_commands_in_context(self):
        config, tmpfile = _make_config("""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "key"
model = "model"

[[agent]]
name = "default"
compress_threshold = 0.8
allowed_commands = [["ls"], ["git", "status"]]
""")
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": False,
                "claw_folder": None,
                "message": [],
                "file": [],
                "planning": False,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertEqual(context["allowed_commands"], [["ls"], ["git", "status"]])
        finally:
            os.unlink(tmpfile)

    def test_empty_allowed_commands(self):
        config, tmpfile = _make_config(self._base_config())
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": False,
                "claw_folder": None,
                "message": [],
                "file": [],
                "planning": False,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertEqual(context["allowed_commands"], [])
        finally:
            os.unlink(tmpfile)

    def test_mcp_configs_in_context(self):
        config, tmpfile = _make_config("""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "key"
model = "model"

[[agent]]
name = "default"
compress_threshold = 0.8

[[agent.mcp]]
name = "server1"
command = "python server1.py"

[[agent.mcp]]
name = "server2"
command = "uv run server2.py"
""")
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": False,
                "claw_folder": None,
                "message": [],
                "file": [],
                "planning": False,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertEqual(len(context["mcp_configs"]), 2)
            self.assertEqual(context["mcp_configs"][0].name, "server1")
            self.assertEqual(context["mcp_configs"][1].name, "server2")
        finally:
            os.unlink(tmpfile)

    def test_mcp_configs_empty(self):
        config, tmpfile = _make_config(self._base_config())
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": False,
                "claw_folder": None,
                "message": [],
                "file": [],
                "planning": False,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertEqual(context["mcp_configs"], [])
        finally:
            os.unlink(tmpfile)

    def test_toolset_enable_override(self):
        config, tmpfile = _make_config("""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "key"
model = "model"

[[agent]]
name = "default"
compress_threshold = 0.8
enable_toolsets = ["utils", "sleep"]
""")
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": False,
                "claw_folder": None,
                "message": [],
                "file": [],
                "planning": False,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            self.assertEqual(context["enabled_toolsets"], ["utils", "sleep"])
        finally:
            os.unlink(tmpfile)

    def test_toolset_disable_override(self):
        config, tmpfile = _make_config("""
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "key"
model = "model"

[[agent]]
name = "default"
compress_threshold = 0.8
disable_toolsets = ["llm"]
""")
        try:
            registry = Registry()
            build_args: AgentBuildArguments = {
                "cron": [],
                "telegram": False,
                "disable_waiting_marker": False,
                "afk": False,
                "claw_enabled": False,
                "claw_folder": None,
                "message": [],
                "file": [],
                "planning": False,
                "llm_name": None,
                "profile_name": None,
            }
            context = create_agent_build_context(
                registry=registry,
                config=config,
                config_basedir=Path("."),
                build_args=build_args,
            )
            from linhai.config import AVAILABLE_TOOLSETS

            expected = [t for t in AVAILABLE_TOOLSETS if t != "llm"]
            self.assertEqual(context["enabled_toolsets"], expected)
        finally:
            os.unlink(tmpfile)


if __name__ == "__main__":
    unittest.main()
