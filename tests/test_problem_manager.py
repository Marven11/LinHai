import asyncio
import unittest
from unittest.mock import MagicMock

from linhai.problem_manager import (
    ProblemManagerProtocol,
    PlainProblemManager,
    _display_width,
)


def _make_registry() -> MagicMock:
    registry = MagicMock()
    registry.register_member = MagicMock()
    return registry


class TestProblemManagerProtocol(unittest.TestCase):
    def test_plain_is_problem_manager(self):
        self.assertIsInstance(
            PlainProblemManager(_make_registry()), ProblemManagerProtocol
        )


class TestRegistryRegistration(unittest.TestCase):
    def test_registers_itself(self):
        registry = _make_registry()
        mgr = PlainProblemManager(registry)
        registry.register_member.assert_called_once_with("problem_manager", mgr)


class TestCreateProblem(unittest.TestCase):
    def test_create_problem_returns_id(self):
        mgr = PlainProblemManager(_make_registry())
        pid = mgr.create_problem("hello?", ["yes", "no"])
        self.assertTrue(pid.startswith("problem_"))

    def test_create_problem_stores_data(self):
        mgr = PlainProblemManager(_make_registry())
        pid = mgr.create_problem("question", ["a", "b"])
        data = mgr.get_problem(pid)
        self.assertEqual(data.content, "question")
        self.assertEqual(data.options, ["a", "b"])
        self.assertIsNone(data.answer)

    def test_create_problem_empty_options_raises(self):
        mgr = PlainProblemManager(_make_registry())
        with self.assertRaises(ValueError):
            mgr.create_problem("q", [])

    def test_create_problem_newline_in_option_raises(self):
        mgr = PlainProblemManager(_make_registry())
        with self.assertRaises(ValueError):
            mgr.create_problem("q", ["line1\nline2"])

    def test_create_problem_newline_in_content_raises(self):
        mgr = PlainProblemManager(_make_registry())
        with self.assertRaises(ValueError):
            mgr.create_problem("line1\nline2", ["a"])

    def test_create_problem_content_too_wide_raises(self):
        mgr = PlainProblemManager(_make_registry())
        long_content = "a" * 241
        with self.assertRaises(ValueError):
            mgr.create_problem(long_content, ["a"])

    def test_create_problem_content_exactly_240_ok(self):
        mgr = PlainProblemManager(_make_registry())
        content = "a" * 240
        pid = mgr.create_problem(content, ["a"])
        self.assertTrue(pid.startswith("problem_"))

    def test_create_problem_chinese_content(self):
        mgr = PlainProblemManager(_make_registry())
        chinese_120 = "中" * 120
        pid = mgr.create_problem(chinese_120, ["a"])
        self.assertTrue(pid.startswith("problem_"))

    def test_create_problem_chinese_too_wide_raises(self):
        mgr = PlainProblemManager(_make_registry())
        chinese_121 = "中" * 121
        with self.assertRaises(ValueError):
            mgr.create_problem(chinese_121, ["a"])

    def test_create_problem_unique_ids(self):
        mgr = PlainProblemManager(_make_registry())
        ids = {mgr.create_problem("q", ["a"]) for _ in range(10)}
        self.assertEqual(len(ids), 10)


class TestSetAnswer(unittest.IsolatedAsyncioTestCase):
    async def test_set_and_wait_answer(self):
        mgr = PlainProblemManager(_make_registry())
        pid = mgr.create_problem("q?", ["yes", "no"])

        async def answer_later():
            await asyncio.sleep(0.05)
            mgr.set_answer(pid, "yes")

        asyncio.create_task(answer_later())
        result = await mgr.wait_answer(pid, timeout=1.0)
        self.assertEqual(result, "yes")

    def test_set_answer_unknown_problem_raises(self):
        mgr = PlainProblemManager(_make_registry())
        with self.assertRaises(RuntimeError):
            mgr.set_answer("problem_nonexistent", "x")

    def test_set_answer_twice_raises(self):
        mgr = PlainProblemManager(_make_registry())
        pid = mgr.create_problem("q?", ["a", "b"])
        mgr.set_answer(pid, "a")
        with self.assertRaises(RuntimeError):
            mgr.set_answer(pid, "b")


class TestWaitAnswer(unittest.IsolatedAsyncioTestCase):
    async def test_wait_answer_already_answered(self):
        mgr = PlainProblemManager(_make_registry())
        pid = mgr.create_problem("q?", ["a"])
        mgr.set_answer(pid, "a")
        result = await mgr.wait_answer(pid, timeout=1.0)
        self.assertEqual(result, "a")

    async def test_wait_answer_timeout(self):
        mgr = PlainProblemManager(_make_registry())
        pid = mgr.create_problem("q?", ["a"])
        with self.assertRaises(asyncio.TimeoutError):
            await mgr.wait_answer(pid, timeout=0.05)

    async def test_wait_answer_unknown_problem_raises(self):
        mgr = PlainProblemManager(_make_registry())
        with self.assertRaises(RuntimeError):
            await mgr.wait_answer("problem_nonexistent", timeout=1.0)


class TestGetUnansweredProblems(unittest.TestCase):
    def test_get_unanswered(self):
        mgr = PlainProblemManager(_make_registry())
        pid1 = mgr.create_problem("q1", ["a"])
        pid2 = mgr.create_problem("q2", ["b"])
        mgr.set_answer(pid1, "a")
        unanswered = mgr.get_unanswered_problems()
        self.assertEqual(len(unanswered), 1)
        self.assertEqual(unanswered[0][0], pid2)

    def test_get_problem_unknown_raises(self):
        mgr = PlainProblemManager(_make_registry())
        with self.assertRaises(RuntimeError):
            mgr.get_problem("problem_nonexistent")


class TestCreateToolset(unittest.IsolatedAsyncioTestCase):
    def test_create_toolset_returns_toolset(self):
        from linhai.tool.base import ToolSet

        mgr = PlainProblemManager(_make_registry())
        ts = mgr.create_toolset()
        self.assertIsInstance(ts, ToolSet)
        tool_names = list(ts.get_tools().keys())
        self.assertIn("problem_create", tool_names)
        self.assertIn("problem_wait_answer", tool_names)

    def test_problem_create_tool(self):
        mgr = PlainProblemManager(_make_registry())
        ts = mgr.create_toolset()
        create_tool = ts.get_tools()["problem_create"]
        result = create_tool["func"]("q?", ["a", "b"])
        self.assertIn("problem_", result.content)
        self.assertIsNotNone(mgr.get_problem(result.content))

    async def test_problem_wait_answer_tool(self):
        mgr = PlainProblemManager(_make_registry())
        ts = mgr.create_toolset()
        create_tool = ts.get_tools()["problem_create"]
        wait_tool = ts.get_tools()["problem_wait_answer"]

        pid_result = create_tool["func"]("q?", ["a", "b"])
        pid = pid_result.content

        async def answer_later():
            await asyncio.sleep(0.05)
            mgr.set_answer(pid, "a")

        asyncio.create_task(answer_later())
        result = await wait_tool["func"](problem_id=pid, timeout=1.0)
        self.assertEqual(result.content, "a")


class TestDisplayWidth(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(_display_width("hello"), 5)

    def test_chinese(self):
        self.assertEqual(_display_width("你好"), 4)

    def test_mixed(self):
        self.assertEqual(_display_width("hello你好"), 9)

    def test_empty(self):
        self.assertEqual(_display_width(""), 0)


if __name__ == "__main__":
    unittest.main()
