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


class TestAgentSessionGetMessages(unittest.TestCase):
    def test_get_messages_filters_unknown_roles(self):
        mock_agent = MagicMock()
        mock_msg = MagicMock()
        mock_msg.get_content.return_value = "hello"
        mock_agent.message_processor.get_messages.return_value = [mock_msg]
        mock_manager = MagicMock()
        session = AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )
        result = session.get_messages()
        self.assertEqual(result, [])

    def test_get_messages_includes_user_messages(self):
        from linhai.llm import UserMessage

        mock_agent = MagicMock()
        user_msg = UserMessage("hello")
        mock_agent.message_processor.get_messages.return_value = [user_msg]
        mock_manager = MagicMock()
        session = AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )
        result = session.get_messages()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "hello")

    def test_registry_property(self):
        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry
        mock_manager = MagicMock()
        session = AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )
        self.assertEqual(session.registry, mock_registry)


class TestAgentSessionSendMessage(unittest.IsolatedAsyncioTestCase):
    async def test_send_message(self):
        mock_registry = MagicMock()
        mock_registry.send = AsyncMock()
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry
        mock_manager = MagicMock()
        session = AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )
        await session.send_message("hello")
        mock_registry.send.assert_called_once()
        args = mock_registry.send.call_args
        self.assertEqual(args[0][0], "user_message")


class TestNewSchemas(unittest.TestCase):
    def test_message_request(self):
        from linhai.webui.schemas import MessageRequest

        req = MessageRequest(content="hello")
        self.assertEqual(req.content, "hello")

    def test_message_item(self):
        from linhai.webui.schemas import MessageItem

        item = MessageItem(role="user", content="hello")
        self.assertEqual(item.role, "user")

    def test_ws_segment_event(self):
        from linhai.webui.schemas import WsSegmentEvent

        event = WsSegmentEvent(segment_type="normal", content="hi", is_finished=False)
        self.assertEqual(event.type, "segment")
        self.assertEqual(event.segment_type, "normal")

    def test_ws_state_change_event(self):
        from linhai.webui.schemas import WsStateChangeEvent

        event = WsStateChangeEvent(old_state="working", new_state="waiting_user")
        self.assertEqual(event.type, "state_change")

    def test_ws_ui_log_event(self):
        from linhai.webui.schemas import WsUiLogEvent

        event = WsUiLogEvent(level="INFO", content="test")
        self.assertEqual(event.type, "ui_log")


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


class TestNewSchemasContextPlanning(unittest.TestCase):
    def test_token_usage_info(self):
        from linhai.webui.schemas import TokenUsageInfo

        info = TokenUsageInfo(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cached_input_tokens=80,
            cache_creation_input_tokens=10,
            message_count=5,
            cache_miss_count=1,
        )
        self.assertEqual(info.input_tokens, 100)
        self.assertEqual(info.message_count, 5)

    def test_context_stats_response(self):
        from linhai.webui.schemas import ContextStatsResponse

        resp = ContextStatsResponse(
            message_count=10,
            pinned_message_count=2,
            notification_count=1,
            large_message_count=0,
            traffic_light="绿灯",
            is_dirty=False,
            generation_count=3,
        )
        self.assertEqual(resp.message_count, 10)
        self.assertIsNone(resp.cumulative_token_usage)

    def test_planning_file_response(self):
        from linhai.webui.schemas import PlanningFileResponse

        resp = PlanningFileResponse(status="# Status", todolist=None, design="# Design")
        self.assertEqual(resp.status, "# Status")
        self.assertIsNone(resp.todolist)

    def test_config_response(self):
        from linhai.webui.schemas import ConfigResponse, ProfileInfo, LlmInfo

        resp = ConfigResponse(
            profiles=[ProfileInfo(name="default")],
            llms=[LlmInfo(name="gpt", model="gpt-4", type="openai")],
        )
        self.assertEqual(len(resp.profiles), 1)
        self.assertEqual(resp.llms[0].model, "gpt-4")


class TestAgentSessionContextStats(unittest.TestCase):
    def _make_session(self, agent_mock=None, registry_mock=None):
        if agent_mock is None:
            agent_mock = MagicMock()
        if registry_mock is None:
            registry_mock = MagicMock()
        agent_mock.registry = registry_mock
        manager = MagicMock()
        return AgentSession(
            agent_id="test-id",
            agent=agent_mock,
            task_name="task-1",
            manager=manager,
        )

    def test_get_context_stats_basic(self):
        mock_agent = MagicMock()
        mock_agent.get_threshold_info.return_value = None
        mock_mp = MagicMock()
        mock_mp.get_message_count.return_value = 5
        mock_mp.pinned_messages = [MagicMock()]
        mock_mp.notification_messages = {}
        mock_agent.message_processor = mock_mp
        mock_registry = MagicMock()
        mock_registry.has_member.return_value = False

        session = self._make_session(mock_agent, mock_registry)
        stats = session.get_context_stats()

        self.assertEqual(stats["message_count"], 5)
        self.assertEqual(stats["pinned_message_count"], 1)
        self.assertEqual(stats["traffic_light"], "绿灯")
        self.assertFalse(stats["is_dirty"])

    def test_get_context_stats_yellow_light(self):
        mock_agent = MagicMock()
        mock_agent.get_threshold_info.return_value = {"usage_ratio": 0.85}
        mock_mp = MagicMock()
        mock_mp.get_message_count.return_value = 10
        mock_mp.pinned_messages = []
        mock_mp.notification_messages = {}
        mock_agent.message_processor = mock_mp
        mock_registry = MagicMock()
        mock_registry.has_member.return_value = False

        session = self._make_session(mock_agent, mock_registry)
        stats = session.get_context_stats()

        self.assertEqual(stats["traffic_light"], "黄灯")
        self.assertEqual(stats["context_usage_ratio"], 0.85)

    def test_get_context_stats_red_light(self):
        mock_agent = MagicMock()
        mock_agent.get_threshold_info.return_value = {"usage_ratio": 0.95}
        mock_mp = MagicMock()
        mock_mp.get_message_count.return_value = 10
        mock_mp.pinned_messages = []
        mock_mp.notification_messages = {}
        mock_agent.message_processor = mock_mp
        mock_registry = MagicMock()
        mock_registry.has_member.return_value = False

        session = self._make_session(mock_agent, mock_registry)
        stats = session.get_context_stats()

        self.assertEqual(stats["traffic_light"], "红灯")

    def test_get_planning_files_no_planning(self):
        mock_registry = MagicMock()
        mock_registry.has_member.return_value = False
        mock_agent = MagicMock()
        mock_agent.registry = mock_registry

        session = self._make_session(mock_agent, mock_registry)
        result = session.get_planning_files()

        self.assertIsNone(result["status"])
        self.assertIsNone(result["todolist"])
        self.assertIsNone(result["design"])


class TestAgentManagerConfigInfo(unittest.IsolatedAsyncioTestCase):
    async def test_get_config_info(self):
        with patch("linhai.webui.agent_manager.load_config") as mock_load:
            mock_config = MagicMock()
            mock_agent_config = MagicMock()
            mock_agent_config.name = "default"
            mock_config.agent = [mock_agent_config]
            mock_llm = MagicMock()
            mock_llm.name = "gpt"
            mock_llm.model = "gpt-4"
            mock_llm.type = "openai"
            mock_config.llm = [mock_llm]
            mock_load.return_value = mock_config

            with patch(
                "linhai.webui.agent_manager.get_default_config_path",
                return_value="/fake/path",
            ):
                manager = AgentManager(config_path="/fake/path")
                info = manager.get_config_info()

                self.assertEqual(len(info["profiles"]), 1)
                self.assertEqual(info["profiles"][0]["name"], "default")
                self.assertEqual(len(info["llms"]), 1)
                self.assertEqual(info["llms"][0]["name"], "gpt")
