import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.task_supervisor import (
    TaskSupervisor,
    PlainTaskSupervisor,
    TextualTaskSupervisor,
)


class TestTaskSupervisorProtocol(unittest.TestCase):
    def test_plain_is_task_supervisor(self):
        self.assertIsInstance(PlainTaskSupervisor(), TaskSupervisor)


class TestPlainTaskSupervisor(unittest.IsolatedAsyncioTestCase):
    async def test_create_and_wait_task(self):
        supervisor = PlainTaskSupervisor()
        result = []

        async def work():
            result.append(1)

        supervisor.create_supervised_task("test_task", work)
        await supervisor.wait("test_task")
        self.assertEqual(result, [1])

    async def test_cancel_task(self):
        supervisor = PlainTaskSupervisor()
        cancelled = []

        async def long_work():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise

        supervisor.create_supervised_task("long_task", long_work)
        await asyncio.sleep(0.01)
        supervisor.cancel("long_task")
        await asyncio.sleep(0.01)
        self.assertEqual(cancelled, [True])

    async def test_wait_nonexistent_raises(self):
        supervisor = PlainTaskSupervisor()
        with self.assertRaises(RuntimeError):
            await supervisor.wait("nonexistent")

    async def test_cancel_nonexistent_raises(self):
        supervisor = PlainTaskSupervisor()
        with self.assertRaises(RuntimeError):
            supervisor.cancel("nonexistent")


class TestTextualTaskSupervisor(unittest.IsolatedAsyncioTestCase):
    async def test_create_and_wait_worker(self):
        mock_app = MagicMock()
        mock_worker = AsyncMock()
        mock_worker.wait = AsyncMock()

        def run_worker_consume(coro, name=None):
            asyncio.create_task(coro)
            return mock_worker

        mock_app.run_worker = run_worker_consume
        supervisor = TextualTaskSupervisor(mock_app)

        async def work():
            pass

        supervisor.create_supervised_task("test_worker", work)
        await supervisor.wait("test_worker")
        mock_worker.wait.assert_called_once()

    async def test_cancel_worker(self):
        mock_app = MagicMock()
        mock_worker = MagicMock()

        def run_worker_consume(coro, name=None):
            asyncio.create_task(coro)
            return mock_worker

        mock_app.run_worker = run_worker_consume
        supervisor = TextualTaskSupervisor(mock_app)

        async def work():
            pass

        supervisor.create_supervised_task("test_worker", work)
        supervisor.cancel("test_worker")
        mock_worker.cancel.assert_called_once()

    async def test_wait_nonexistent_raises(self):
        mock_app = MagicMock()
        supervisor = TextualTaskSupervisor(mock_app)
        with self.assertRaises(RuntimeError):
            await supervisor.wait("nonexistent")

    async def test_cancel_nonexistent_raises(self):
        mock_app = MagicMock()
        supervisor = TextualTaskSupervisor(mock_app)
        with self.assertRaises(RuntimeError):
            supervisor.cancel("nonexistent")


class TestTUIAppRegistersTaskSupervisor(unittest.IsolatedAsyncioTestCase):
    async def test_cli_app_registers_textual_task_supervisor(self):
        import argparse

        from linhai.tui.app import TUIApp
        from linhai.config import TUIConfig
        from linhai.registry import Registry

        registry = Registry()
        cli_args = argparse.Namespace(message=None, file=None)
        registry.register_member("cli_args", cli_args)
        tui_config = TUIConfig()
        TUIApp(registry, tui_config, init_messages=[], init_files=[])
        supervisor = registry.get_member_typechecked("task_supervisor", TaskSupervisor)
        self.assertIsInstance(supervisor, TextualTaskSupervisor)


if __name__ == "__main__":
    unittest.main()
