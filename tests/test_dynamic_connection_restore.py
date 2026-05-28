import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, create_autospec
from pathlib import Path
from tempfile import TemporaryDirectory

from linhai.registry import Registry
from linhai.agent.savable_state import SavableState
from linhai.agent.message import AgentMessage
from linhai.agent.messages import RuntimeMessage
from linhai.agent.lifecycle import Lifecycle
from linhai.base import SystemMessage


def _make_registry() -> Registry:
    registry = Registry()
    Lifecycle(registry)
    return registry


class TestMCPConnectorSerializeRestore(unittest.TestCase):
    def test_is_savable_state(self):
        from linhai.tool.mcp_connector import MCPConnector

        registry = _make_registry()
        conn = MCPConnector(registry)
        self.assertIsInstance(conn, SavableState)

    def test_serialize_empty_sessions(self):
        from linhai.tool.mcp_connector import MCPConnector

        registry = _make_registry()
        conn = MCPConnector(registry)
        data = conn.serialize()
        self.assertEqual(data, {"sessions": {}})

    def test_serialize_with_sessions(self):
        from linhai.tool.mcp_connector import MCPConnector, MCPServerConnection

        registry = _make_registry()
        conn = MCPConnector(registry)
        mock_conn = MagicMock(spec=MCPServerConnection)
        mock_conn.command = "python server.py"
        conn.sessions["test_server"] = mock_conn
        data = conn.serialize()
        self.assertIn("test_server", data["sessions"])
        self.assertEqual(data["sessions"]["test_server"]["command"], "python server.py")

    def test_restore_clears_sessions(self):
        from linhai.tool.mcp_connector import MCPConnector, MCPServerConnection

        registry = _make_registry()
        conn = MCPConnector(registry)
        mock_conn = MagicMock(spec=MCPServerConnection)
        conn.sessions["test_server"] = mock_conn
        conn.restore_from(
            {"sessions": {"test_server": {"command": "python server.py"}}}
        )
        self.assertEqual(conn.sessions, {})
        self.assertEqual(
            conn._saved_session_info, {"test_server": {"command": "python server.py"}}
        )

    def test_restore_empty_data(self):
        from linhai.tool.mcp_connector import MCPConnector

        registry = _make_registry()
        conn = MCPConnector(registry)
        conn.restore_from({"sessions": {}})
        self.assertEqual(conn._saved_session_info, {})


class TestMachineControlSerializeRestore(unittest.TestCase):
    def test_is_savable_state(self):
        from linhai.machine_control.main import MachineControl

        registry = _make_registry()
        mc = MachineControl(registry)
        self.assertIsInstance(mc, SavableState)

    def test_serialize_master_host_only(self):
        from linhai.machine_control.main import MachineControl

        registry = _make_registry()
        mc = MachineControl(registry)
        data = mc.serialize()
        self.assertEqual(data, {"machines": {}})

    def test_serialize_with_machine(self):
        from linhai.machine_control.main import MachineControl

        registry = _make_registry()
        mc = MachineControl(registry)
        mc.machine_descriptions["remote1"] = "Test remote"
        mc.source_machines["remote1"] = "master_host"
        mc._process_infos["remote1:123"] = {
            "argv": ["ssh", "user@host"],
            "exit_time": None,
        }
        mock_host = MagicMock()
        mc.machines["remote1"] = mock_host
        data = mc.serialize()
        self.assertIn("remote1", data["machines"])
        self.assertEqual(data["machines"]["remote1"]["description"], "Test remote")
        self.assertEqual(data["machines"]["remote1"]["source_machine"], "master_host")
        self.assertEqual(data["machines"]["remote1"]["argv"], ["ssh", "user@host"])

    def test_restore_clears_machines(self):
        from linhai.machine_control.main import MachineControl

        registry = _make_registry()
        mc = MachineControl(registry)
        mc.machine_descriptions["remote1"] = "Test remote"
        mc.source_machines["remote1"] = "master_host"
        mock_host = MagicMock()
        mc.machines["remote1"] = mock_host
        mc.target_machine = "remote1"
        mc.restore_from(
            {
                "machines": {
                    "remote1": {
                        "description": "Test",
                        "source_machine": "master_host",
                        "argv": [],
                    }
                }
            }
        )
        self.assertNotIn("remote1", mc.machines)
        self.assertIn("master_host", mc.machines)
        self.assertEqual(mc.target_machine, "master_host")
        self.assertEqual(
            mc._saved_machine_info,
            {
                "remote1": {
                    "description": "Test",
                    "source_machine": "master_host",
                    "argv": [],
                }
            },
        )


class TestAfterConversationRestoreCallbacks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_full_registry(self) -> Registry:
        registry = Registry()
        Lifecycle(registry)
        from linhai.agent.main import Agent

        mock_agent = create_autospec(Agent, instance=True)
        registry.register_member("agent", mock_agent)
        from linhai.llm_manager import LlmManager

        mock_llm_manager = create_autospec(LlmManager, instance=True)
        mock_llm = MagicMock()
        mock_llm.get_explicit_cache_info = MagicMock(return_value=None)
        mock_llm_manager.get_current_llm = MagicMock(return_value=mock_llm)
        registry.register_member("llm_manager", mock_llm_manager)
        registry.register_member("conversation_folder", Path(self.temp_dir.name))
        return registry

    async def test_mcp_callback_adds_notification(self):
        from linhai.tool.mcp_connector import MCPConnector

        registry = self._make_full_registry()
        am = AgentMessage(registry, [])
        conn = MCPConnector(registry)
        conn._saved_session_info = {"server1": {"command": "python test.py"}}
        conn.register_lifecycle()
        lifecycle = registry.get_member_typechecked("lifecycle", Lifecycle)
        await lifecycle.after_conversation_restore.trigger()
        self.assertIn("mcp_disconnected", am.notification_messages)
        msg = am.notification_messages["mcp_disconnected"]
        self.assertIsInstance(msg, RuntimeMessage)
        self.assertIn("server1", msg.message)
        self.assertIn("python test.py", msg.message)

    async def test_mcp_callback_noop_when_empty(self):
        from linhai.tool.mcp_connector import MCPConnector

        registry = self._make_full_registry()
        am = AgentMessage(registry, [])
        conn = MCPConnector(registry)
        conn._saved_session_info = {}
        conn.register_lifecycle()
        lifecycle = registry.get_member_typechecked("lifecycle", Lifecycle)
        await lifecycle.after_conversation_restore.trigger()
        self.assertNotIn("mcp_disconnected", am.notification_messages)

    async def test_machine_callback_adds_notification(self):
        from linhai.machine_control.main import MachineControl

        registry = self._make_full_registry()
        am = AgentMessage(registry, [])
        mc = MachineControl(registry)
        mc._saved_machine_info = {
            "remote1": {
                "description": "Test machine",
                "source_machine": "master_host",
                "argv": ["ssh", "user@host"],
            }
        }
        lifecycle = registry.get_member_typechecked("lifecycle", Lifecycle)
        mc.register_plugin(lifecycle)
        await lifecycle.after_conversation_restore.trigger()
        self.assertIn("machine_disconnected", am.notification_messages)
        msg = am.notification_messages["machine_disconnected"]
        self.assertIsInstance(msg, RuntimeMessage)
        self.assertIn("remote1", msg.message)
        self.assertIn("ssh user@host", msg.message)

    async def test_machine_callback_noop_when_empty(self):
        from linhai.machine_control.main import MachineControl

        registry = self._make_full_registry()
        am = AgentMessage(registry, [])
        mc = MachineControl(registry)
        mc._saved_machine_info = {}
        lifecycle = registry.get_member_typechecked("lifecycle", Lifecycle)
        mc.register_plugin(lifecycle)
        await lifecycle.after_conversation_restore.trigger()
        self.assertNotIn("machine_disconnected", am.notification_messages)

    async def test_tool_manager_callback_updates_tools(self):
        from linhai.tool.main import ToolManager
        from linhai.tool.mcp_connector import MCPConnector
        from linhai.config import ToolConfig

        registry = self._make_full_registry()
        mock_reg = Registry()
        mock_reg.register_member = MagicMock()
        sys_msg = SystemMessage(registry=mock_reg)
        registry.register_member("system_message", sys_msg)
        mcp = MCPConnector(registry)
        tool_config = MagicMock(spec=ToolConfig)
        tm = ToolManager(registry, tool_config, mcp)
        tm.register_lifecycle()
        lifecycle = registry.get_member_typechecked("lifecycle", Lifecycle)
        await lifecycle.after_conversation_restore.trigger()
        tools_keys = [key for key, _ in sys_msg.introduction_items]
        self.assertIn("TOOLS", tools_keys)


if __name__ == "__main__":
    unittest.main()
