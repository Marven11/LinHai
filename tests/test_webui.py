import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from linhai.webui.schemas import AgentCreateRequest, AgentInfo
from linhai.webui.agent_manager import AgentManager, AgentSession
from linhai.task_supervisor import PlainTaskSupervisor


class TestSchemas(unittest.TestCase):
    def test_agent_create_request_defaults(self):
        req = AgentCreateRequest()
        self.assertIsNone(req.profile_name)
        self.assertEqual(req.init_messages, [])

    def test_agent_create_request_with_values(self):
        req = AgentCreateRequest(profile_name="test", init_messages=["hello"])
        self.assertEqual(req.profile_name, "test")
        self.assertEqual(req.init_messages, ["hello"])

    def test_agent_info(self):
        info = AgentInfo(
            id="test-id",
            state="working",
            current_llm=None,
            created_at="2026-01-01T00:00:00",
        )
        self.assertEqual(info.id, "test-id")
        self.assertEqual(info.state, "working")
        self.assertIsNone(info.current_llm)


class TestAgentManager(unittest.IsolatedAsyncioTestCase):
    async def test_agent_manager_init(self):
        with patch("linhai.webui.agent_manager.load_config"):
            with patch(
                "linhai.webui.agent_manager.get_default_config_path",
                return_value="/fake/path",
            ):
                manager = AgentManager(config_path="/fake/path")
                self.assertEqual(manager.sessions, {})

    async def test_agent_manager_list_agents(self):
        with patch("linhai.webui.agent_manager.load_config"):
            with patch(
                "linhai.webui.agent_manager.get_default_config_path",
                return_value="/fake/path",
            ):
                manager = AgentManager(config_path="/fake/path")
                mock_session = MagicMock(spec=AgentSession)
                mock_session.get_state = MagicMock(return_value="working")
                mock_session.get_current_llm = MagicMock(return_value="gpt")
                mock_session.created_at = MagicMock()
                manager.sessions["test-id"] = mock_session

                agents = manager.list_agents()
                self.assertEqual(len(agents), 1)

    async def test_agent_manager_get_agent_not_found(self):
        with patch("linhai.webui.agent_manager.load_config"):
            with patch(
                "linhai.webui.agent_manager.get_default_config_path",
                return_value="/fake/path",
            ):
                manager = AgentManager(config_path="/fake/path")
                agent = manager.get_agent("non-existent")
                self.assertIsNone(agent)

    async def test_agent_manager_delete_agent(self):
        with patch("linhai.webui.agent_manager.load_config"):
            with patch(
                "linhai.webui.agent_manager.get_default_config_path",
                return_value="/fake/path",
            ):
                manager = AgentManager(config_path="/fake/path")
                mock_session = MagicMock(spec=AgentSession)
                mock_session.stop = AsyncMock()
                manager.sessions["test-id"] = mock_session
                manager._registries["test-id"] = MagicMock()
                manager._registries["test-id"].call_cleanups = AsyncMock()

                result = await manager.delete_agent("test-id")
                self.assertTrue(result)
                self.assertNotIn("test-id", manager.sessions)
                mock_session.stop.assert_called_once()

    async def test_agent_manager_delete_nonexistent_agent(self):
        with patch("linhai.webui.agent_manager.load_config"):
            with patch(
                "linhai.webui.agent_manager.get_default_config_path",
                return_value="/fake/path",
            ):
                manager = AgentManager(config_path="/fake/path")
                result = await manager.delete_agent("non-existent")
                self.assertFalse(result)


class TestAgentSession(unittest.TestCase):
    def test_agent_session_init(self):
        mock_agent = MagicMock()
        mock_manager = MagicMock()
        session = AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )
        self.assertEqual(session.agent_id, "test-id")
        self.assertEqual(session.agent, mock_agent)
        self.assertEqual(session._task_name, "task-1")

    def test_agent_session_get_state(self):
        mock_agent = MagicMock()
        mock_agent.state_machine.state = "waiting_user"
        mock_manager = MagicMock()
        session = AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )
        state = session.get_state()
        self.assertEqual(state, "waiting_user")

    def test_agent_session_get_current_llm(self):
        mock_llm = MagicMock()
        mock_llm.get_name = MagicMock(return_value="gpt-4")
        mock_agent = MagicMock()
        mock_agent.get_current_llm_info = MagicMock(return_value=(None, mock_llm))
        mock_manager = MagicMock()
        session = AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )
        llm = session.get_current_llm()
        self.assertEqual(llm, "gpt-4")


class TestAgentSessionStop(unittest.IsolatedAsyncioTestCase):
    async def test_agent_session_stop(self):
        mock_agent = MagicMock()
        mock_task = MagicMock()
        mock_task.done = MagicMock(side_effect=[False, True])
        mock_supervisor = MagicMock()
        mock_supervisor.tasks = {"task-1": mock_task}
        mock_supervisor.cancel = MagicMock()
        mock_manager = MagicMock()
        mock_manager._task_supervisor = mock_supervisor
        session = AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )
        await session.stop()
        mock_supervisor.cancel.assert_called_once_with("task-1")


class TestPlainTaskSupervisor(unittest.IsolatedAsyncioTestCase):
    async def test_create_and_wait_task(self):
        supervisor = PlainTaskSupervisor()

        async def dummy_task():
            await asyncio.sleep(0.01)

        supervisor.create_supervised_task("test-task", dummy_task)
        await supervisor.wait("test-task")
        self.assertIn("test-task", supervisor.tasks)

    async def test_cancel_task(self):
        supervisor = PlainTaskSupervisor()

        async def long_task():
            await asyncio.sleep(100)

        supervisor.create_supervised_task("long-task", long_task)
        supervisor.cancel("long-task")
        await asyncio.sleep(0)
        self.assertTrue(supervisor.tasks["long-task"].cancelled())

    def test_cancel_nonexistent_task(self):
        supervisor = PlainTaskSupervisor()
        with self.assertRaisesRegex(RuntimeError, "Task .* not found"):
            supervisor.cancel("nonexistent")
