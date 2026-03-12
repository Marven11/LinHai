import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from linhai.agent.planning import PlanningPromptMessage


class TestPlanningPromptMessage(unittest.TestCase):
    def setUp(self):
        self.test_folder = Path("/tmp/test_planning")

    def test_init_creates_file_paths(self):
        message = PlanningPromptMessage(self.test_folder)

        self.assertEqual(message.planning_folder, self.test_folder)
        self.assertEqual(message.status_file, self.test_folder / "STATUS.md")
        self.assertEqual(message.todolist_file, self.test_folder / "TODOLIST.md")
        self.assertEqual(message.design_file, self.test_folder / "DESIGN.md")

    def test_get_file_paths_returns_correct_dict(self):
        message = PlanningPromptMessage(self.test_folder)
        file_paths = message.get_file_paths()

        expected = {
            "status": self.test_folder / "STATUS.md",
            "todolist": self.test_folder / "TODOLIST.md",
            "design": self.test_folder / "DESIGN.md",
        }

        self.assertEqual(file_paths, expected)

    def test_content_contains_placeholders(self):
        message = PlanningPromptMessage(self.test_folder)
        content = message.message  # 访问父类的message属性

        # 应该包含规划文件夹路径
        self.assertIn(str(self.test_folder), content)
        # 应该包含文件路径
        self.assertIn(str(self.test_folder / "STATUS.md"), content)
        self.assertIn(str(self.test_folder / "TODOLIST.md"), content)
        self.assertIn(str(self.test_folder / "DESIGN.md"), content)
        # 应该包含全局指导文件夹占位符
        # 占位符应该在PLANNING_MODE_PROMPT中被替换
        # 所以不应该在content中找到原始占位符
        # 但应该包含实际的文件夹路径
        self.assertIn("/tmp/test_planning", content)

    def test_inherits_from_runtime_message(self):
        from linhai.agent.base import RuntimeMessage

        message = PlanningPromptMessage(self.test_folder)

        self.assertIsInstance(message, RuntimeMessage)


if __name__ == "__main__":
    unittest.main()
