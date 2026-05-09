import tempfile
import unittest
from pathlib import Path

from linhai.base import SystemMessage
from linhai.registry import Registry
from linhai.secret import initialize_secret_system


class TestInitializeSecretSystem(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.secret_file = Path(self.temp_dir) / "test_secret.toml"
        self.secret_file.write_text(
            "[secrets]\n"
            'TEST_KEY = { value = "secret-value-123", description = "Test key" }\n'
        )

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def _run_postinit(self, registry):
        add_intro_cb = None
        for cb in registry._postinit_callbacks:
            cb_name = getattr(cb, "__name__", "")
            if "add_secret_rule" in cb_name:
                add_intro_cb = cb
                break
        self.assertIsNotNone(add_intro_cb)
        add_intro_cb()

    def test_introduction_has_formatted_secrets_not_literal_placeholder(self):
        registry = Registry()
        SystemMessage(registry)

        initialize_secret_system(
            registry=registry,
            secret_config_path=str(self.secret_file),
            config_basedir=self.temp_dir,
        )

        self._run_postinit(registry)

        content = registry.get_member_typechecked(
            "system_message", SystemMessage
        ).get_content()
        self.assertIn("SECRET SYSTEM", content)
        self.assertIn("<$TEST_KEY$>", content)
        self.assertNotIn("{secrets_list}", content)

    def test_no_introduction_when_no_secret_config(self):
        registry = Registry()
        SystemMessage(registry)

        content = registry.get_member_typechecked(
            "system_message", SystemMessage
        ).get_content()
        self.assertNotIn("SECRET SYSTEM", content)


if __name__ == "__main__":
    unittest.main()
