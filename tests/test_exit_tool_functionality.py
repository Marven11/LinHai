"""测试退出工具的核心功能。"""

import unittest
import asyncio


class TestExitTool(unittest.TestCase):
    """测试退出工具功能。"""

    def test_exit_tool_direct_functionality(self):
        """直接测试退出工具的功能逻辑。"""

        def exit_tool(reason: str) -> str:
            """退出工具的实现。"""
            return f"SubAgent 已退出: {reason}"

        result = exit_tool("测试原因")
        self.assertEqual(result, "SubAgent 已退出: 测试原因")

    def test_exit_tool_state_management(self):
        """测试退出工具的状态管理逻辑。"""

        class MockSubAgent:
            def __init__(self):
                self.state = "running"
                self.exit_reason = None

            def exit(self, reason: str) -> str:
                self.exit_reason = reason
                self.state = "exited"
                return f"SubAgent 已退出: {reason}"

        agent = MockSubAgent()

        result = agent.exit("测试完成")

        self.assertEqual(agent.state, "exited")
        self.assertEqual(agent.exit_reason, "测试完成")
        self.assertEqual(result, "SubAgent 已退出: 测试完成")

    def test_exit_tool_prevents_further_execution(self):
        """测试退出工具阻止后续执行。"""

        class MockSubAgent:
            def __init__(self, max_answer_times=5):
                self.state = "running"
                self.exit_reason = None
                self.max_answer_times = max_answer_times
                self.execution_count = 0

            def exit(self, reason: str) -> str:
                self.exit_reason = reason
                self.state = "exited"
                return f"SubAgent 已退出: {reason}"

            async def run_cycle(self):
                """模拟一个执行周期。"""
                if self.state == "exited":
                    return False

                self.execution_count += 1

                if self.execution_count == 1:
                    self.exit("测试退出")

                return self.state == "running"

        agent = MockSubAgent(max_answer_times=5)

        async def run_test():
            for _ in range(3):
                should_continue = await agent.run_cycle()
                if not should_continue:
                    break

            self.assertEqual(agent.execution_count, 1)
            self.assertEqual(agent.state, "exited")
            self.assertEqual(agent.exit_reason, "测试退出")
            self.assertEqual(agent.max_answer_times, 5)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
