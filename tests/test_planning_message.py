import unittest
from pathlib import Path

from linhai.agent.planning import PlanningPromptMessage
from linhai.agent.messages.runtime import RuntimeMessage


class TestPlanningPromptMessageContent(unittest.TestCase):
    def test_content_includes_all_file_paths(self):
        folder = Path("/tmp/my_planning_test")
        msg = PlanningPromptMessage(folder)
        content = msg.message
        self.assertIn(str(folder / "STATUS.md"), content)
        self.assertIn(str(folder / "TODOLIST.md"), content)
        self.assertIn(str(folder / "DESIGN.md"), content)

    def test_inherits_runtime_message(self):
        msg = PlanningPromptMessage(Path("/tmp/test"))
        self.assertIsInstance(msg, RuntimeMessage)

    def test_get_file_paths(self):
        folder = Path("/tmp/planning_abc")
        msg = PlanningPromptMessage(folder)
        paths = msg.get_file_paths()
        self.assertEqual(paths["status"], folder / "STATUS.md")
        self.assertEqual(paths["todolist"], folder / "TODOLIST.md")
        self.assertEqual(paths["design"], folder / "DESIGN.md")

    def test_different_folders_produce_different_content(self):
        msg1 = PlanningPromptMessage(Path("/tmp/planning_one"))
        msg2 = PlanningPromptMessage(Path("/tmp/planning_two"))
        self.assertNotEqual(msg1.message, msg2.message)

    def test_serialization_preserves_content(self):
        folder = Path("/tmp/test_planning_serial")
        msg = PlanningPromptMessage(folder)
        json_str = msg.to_json()
        restored = RuntimeMessage.from_json(json_str, None)
        self.assertEqual(restored.message, msg.message)
