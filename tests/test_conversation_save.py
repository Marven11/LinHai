import json
import tempfile
import shutil
from pathlib import Path
import unittest
from unittest import mock

from linhai.registry import Registry
from linhai.agent.savable_state import SavableState
from linhai.agent.conversation_save import (
    save_conversation,
    restore_conversation,
    _get_savable_members,
    CONVERSATION_VERSION,
)


class MockSavableMember:
    def __init__(self, data=None):
        self._data = data or {"key": "value"}

    def serialize(self):
        return dict(self._data)

    def restore_from(self, data):
        self._data = dict(data)


class MockNonSavableMember:
    pass


class TestSavableStateProtocol(unittest.TestCase):
    def test_savable_member_isinstance(self):
        self.assertIsInstance(MockSavableMember(), SavableState)

    def test_non_savable_member_not_isinstance(self):
        self.assertNotIsInstance(MockNonSavableMember(), SavableState)


class TestGetSavableMembers(unittest.TestCase):
    def test_filters_savable_members(self):
        registry = Registry()
        registry.register_member("savable", MockSavableMember())
        registry.register_member("non_savable", MockNonSavableMember())
        result = _get_savable_members(registry)
        self.assertIn("savable", result)
        self.assertNotIn("non_savable", result)


class TestSaveConversation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.registry = Registry()
        self.registry.register_member("savable", MockSavableMember({"x": 1}))
        self.registry.register_member("plain", MockNonSavableMember())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    async def test_save_creates_json(self):
        filepath = Path(self.temp_dir) / "test.json"
        await save_conversation(self.registry, filepath)
        self.assertTrue(filepath.exists())
        data = json.loads(filepath.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], CONVERSATION_VERSION)
        self.assertIn("savable", data["members"])
        self.assertNotIn("plain", data["members"])
        self.assertEqual(data["members"]["savable"], {"x": 1})


class TestRestoreConversation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    async def test_restore_success(self):
        filepath = Path(self.temp_dir) / "test.json"
        data = {
            "version": CONVERSATION_VERSION,
            "members": {"member_a": {"key": "restored"}},
        }
        filepath.write_text(json.dumps(data), encoding="utf-8")
        registry = Registry()
        member = MockSavableMember()
        from linhai.agent.lifecycle import Lifecycle

        lifecycle = Lifecycle(registry)
        registry.register_member("member_a", member)
        await restore_conversation(registry, filepath)
        self.assertEqual(member._data, {"key": "restored"})

    async def test_restore_version_mismatch(self):
        filepath = Path(self.temp_dir) / "test.json"
        filepath.write_text(
            json.dumps({"version": "999", "members": {}}), encoding="utf-8"
        )
        registry = Registry()
        registry.register_member("lifecycle", mock.Mock())
        with self.assertRaises(RuntimeError) as ctx:
            await restore_conversation(registry, filepath)
        self.assertIn("version", str(ctx.exception).lower())

    async def test_restore_missing_member(self):
        filepath = Path(self.temp_dir) / "test.json"
        filepath.write_text(
            json.dumps({"version": CONVERSATION_VERSION, "members": {}}),
            encoding="utf-8",
        )
        registry = Registry()
        registry.register_member("member_a", MockSavableMember())
        registry.register_member("lifecycle", mock.Mock())
        with self.assertRaises(RuntimeError) as ctx:
            await restore_conversation(registry, filepath)
        self.assertIn("missing", str(ctx.exception).lower())

    async def test_restore_extra_member(self):
        filepath = Path(self.temp_dir) / "test.json"
        filepath.write_text(
            json.dumps({"version": CONVERSATION_VERSION, "members": {"unknown": {}}}),
            encoding="utf-8",
        )
        registry = Registry()
        registry.register_member("lifecycle", mock.Mock())
        with self.assertRaises(RuntimeError) as ctx:
            await restore_conversation(registry, filepath)
        self.assertIn("extra", str(ctx.exception).lower())
