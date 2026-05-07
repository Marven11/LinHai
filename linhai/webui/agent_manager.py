import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from linhai.machine_control.process import ProcessIOError
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.token_manager import TokenManager
from linhai.agent.create import (
    AgentBuildArguments,
    create_agent_build_context,
    create_agent_from_context,
)
from linhai.agent.main import Agent
from linhai.config import load_config
from linhai.utils.jsonpubsub import JsonPublisher, TaggedEvent
from .schemas import (
    WebuiUserMessage,
    WebuiNotificationMessage,
    WebuiAgentMessage,
    WebuiSegmentType,
)


class AgentSession:

    def __init__(
        self,
        agent_id: str,
        agent: Agent,
        task_name: str,
        manager: "AgentManager",
    ):
        self.agent_id = agent_id
        self.agent = agent
        self._task_name = task_name
        self._manager = manager
        self.created_at = datetime.now()
        self._data: dict = {
            "messages": [],
            "processes": [],
            "status_bar": [],
            "context": {},
            "planning": {},
        }
        self._publisher = JsonPublisher(self._data)
        self._lock = asyncio.Lock()

    def get_state(self) -> str:
        return self.agent.state_machine.state

    @property
    def registry(self) -> Registry:
        return self.agent.registry

    def get_current_llm(self) -> Optional[str]:
        _, llm_instance = self.agent.get_current_llm_info()
        return llm_instance.get_name()

    async def send_message(self, content: str) -> None:
        from linhai.base import UserMessage

        await self.registry.send("user_message", UserMessage(content))
        self.add_user_message(content)

    def add_user_message(self, content: str) -> None:
        msg: WebuiUserMessage = {"type": "user", "content": content}
        self._data["messages"].append(msg)

    def add_notification(self, level: str, content: str) -> None:
        msg: WebuiNotificationMessage = {
            "type": "notification",
            "level": level,
            "content": content,
        }
        self._data["messages"].append(msg)

    def add_agent_message(self) -> int:
        msg: WebuiAgentMessage = {
            "type": "agent",
            "content": "",
            "segments": [],
        }
        self._data["messages"].append(msg)
        return len(self._data["messages"]) - 1

    def add_segment_to_agent_message(
        self, agent_idx: int, segment: WebuiSegmentType
    ) -> None:
        agent_msg = self._data["messages"][agent_idx]
        agent_msg["segments"].append(segment)

    def update_agent_message_content(self, agent_idx: int, content: str) -> None:
        agent_msg = self._data["messages"][agent_idx]
        agent_msg["content"] = content

    async def get_diff(self) -> list[TaggedEvent]:
        async with self._lock:
            return self._publisher.calculate_diff()

    async def handle_reset(self) -> TaggedEvent:
        async with self._lock:
            return self._publisher.reset()

    def sync_context(self) -> None:
        from linhai.context_statistics import (
            compute_context_statistics,
            compute_notification_details,
        )
        from linhai.agent.orchestration import (
            AgentContextOrchestration,
            get_cleanable_large_messages,
            check_cleanable_threshold,
        )

        agent = self.agent
        registry = self.registry
        mp = agent.message_processor
        messages = mp.messages
        pinned_messages = mp.pinned_messages
        notification_entries = list(
            entry["message"] for entry in mp.notification_messages.values()
        )

        threshold_info = agent.get_threshold_info()
        _, current_llm = agent.get_current_llm_info()
        token_limit = current_llm.get_token_limit()

        current_token_usage = None
        generation_count = None
        cumulative_token_usage = None

        if registry.has_member("token_manager"):
            token_manager = registry.get_member_typechecked(
                "token_manager", TokenManager
            )
            current_token_usage = token_manager.current_token_usage
            generation_count = token_manager.generation_count
            cumulative_token_usage = token_manager.cumulative_token_usage

        large_message_count = 0
        cleanable_count = 0
        cleanable_tokens = 0
        can_clean = False
        if registry.has_member("agent_context_orchestration"):
            orchestration = registry.get_member_typechecked(
                "agent_context_orchestration", AgentContextOrchestration
            )
            large_message_count = len(orchestration.large_messages)
            cleanable_messages = get_cleanable_large_messages(
                orchestration.large_messages,
                orchestration.agent_message,
                cleaned_messages_dict=orchestration.cleaned_messages,
            )
            can_clean, cleanable_count, cleanable_tokens = check_cleanable_threshold(
                cleanable_messages
            )

        notification_details = compute_notification_details(mp.notification_messages)

        stats = compute_context_statistics(
            messages=messages,
            pinned_messages=pinned_messages,
            notification_entries=notification_entries,
            notification_details=notification_details,
            large_message_count=large_message_count,
            cleanable_large_message_count=cleanable_count,
            cleanable_large_message_tokens=cleanable_tokens,
            can_clean_large_messages=can_clean,
            threshold_info=threshold_info,
            token_limit=token_limit,
            generation_count=generation_count,
            current_token_usage=current_token_usage,
            cumulative_token_usage=cumulative_token_usage,
        )
        self._data["context"] = stats

    def get_planning_files(self) -> dict[str, str | None]:
        from pathlib import Path

        if not self.registry.has_member("planning_folder"):
            return {"status": None, "todolist": None, "design": None}

        planning_folder = self.registry.get_member_typechecked("planning_folder", Path)
        result: dict[str, str | None] = {}
        for key, filename in [
            ("status", "STATUS.md"),
            ("todolist", "TODOLIST.md"),
            ("design", "DESIGN.md"),
        ]:
            filepath = planning_folder / filename
            if filepath.exists():
                result[key] = filepath.read_text()
            else:
                result[key] = None
        return result

    def get_llms(self) -> list:
        if not self.registry.has_member("llm_manager"):
            return []
        from linhai.llm_manager import LlmManager

        llm_manager = self.registry.get_member_typechecked("llm_manager", LlmManager)
        return llm_manager.list_available_llms()

    async def switch_llm(self, name: str) -> None:
        from linhai.llm_manager import LlmManager

        llm_manager = self.registry.get_member_typechecked("llm_manager", LlmManager)
        await llm_manager.switch_to_llm(name)

    def get_processes(self):
        if not self.registry.has_member("machine_control"):
            return []
        from linhai.machine_control.main import MachineControl, _ProcessEntry

        mc = self.registry.get_member_typechecked("machine_control", MachineControl)
        return mc.list_processes()

    def get_status_bar_pieces(self) -> list[str]:
        agent = self.agent
        registry = self.registry
        token_pieces: list[str] = []
        if registry.has_member("token_manager"):
            token_manager = registry.get_member_typechecked(
                "token_manager", TokenManager
            )
            token_pieces = token_manager.get_token_display_pieces(
                agent, current_answer_token=0, use_nerd_font=True
            )
        from linhai.sandbox import NoSandbox, ProcessSandboxProtocol

        if registry.has_member("process_sandbox"):
            sandbox = registry.get_member_typechecked(
                "process_sandbox", ProcessSandboxProtocol
            )
            if not isinstance(sandbox, NoSandbox):
                token_pieces.append("\uf132")
        _, llm_instance = agent.get_current_llm_info()
        llm_name = llm_instance.get_name()
        token_pieces.append(b"\xf3\xb0\xab\xa2".decode() + f" {llm_name}")
        return token_pieces

    def sync_planning(self) -> None:
        self._data["planning"] = self.get_planning_files()

    def sync_status_bar(self) -> None:
        self._data["status_bar"] = self.get_status_bar_pieces()

    def sync_processes(self) -> None:
        self._data["processes"] = self.get_processes()

    async def kill_process(self, pid: str, machine_id: str) -> bool:
        if not self.registry.has_member("machine_control"):
            return False
        from linhai.machine_control.main import MachineControl

        mc = self.registry.get_member_typechecked("machine_control", MachineControl)
        host = mc.machines.get(machine_id)
        if host is None:
            return False
        proc = host.get_process(pid)
        if proc is None:
            return False
        result = await proc.kill(graceful=True)
        if isinstance(result, ProcessIOError):
            return False
        return result.success

    async def stop(self) -> None:
        task = self._manager._task_supervisor.tasks.get(self._task_name)
        if task is not None and not task.done():
            self._manager._task_supervisor.cancel(self._task_name)
            await asyncio.sleep(0)


class AgentManager:

    def __init__(self, config_path: Path):
        self.sessions: dict[str, AgentSession] = {}
        self._registries: dict[str, Registry] = {}
        self.config_path = config_path
        self._config = load_config(self.config_path)
        self._task_supervisor = PlainTaskSupervisor()

    def _create_registry(self) -> Registry:
        registry = Registry()
        registry.register_member("task_supervisor", self._task_supervisor)
        TokenManager(registry)
        return registry

    async def create_agent(self, build_args: AgentBuildArguments) -> AgentSession:
        agent_id = str(uuid.uuid4())
        registry = self._create_registry()

        context = create_agent_build_context(
            registry=registry,
            config=self._config,
            config_basedir=Path(self.config_path).parent,
            build_args=build_args,
        )

        agent = await create_agent_from_context(context)

        restore_path = build_args.get("restore_path")
        if restore_path is not None:
            from linhai.agent.conversation_save import restore_conversation

            await restore_conversation(registry, restore_path)

        token_manager = registry.get_member_typechecked("token_manager", TokenManager)
        token_manager.start_watching()

        async def run_agent():
            await agent.run()

        task_name = f"agent_{agent_id}"
        self._task_supervisor.create_supervised_task(task_name, run_agent)
        self._registries[agent_id] = registry

        session = AgentSession(
            agent_id=agent_id,
            agent=agent,
            task_name=task_name,
            manager=self,
        )
        self.sessions[agent_id] = session

        for msg in build_args.get("message", []):
            session.add_user_message(msg)

        if restore_path is not None:
            self._populate_session_from_restored(session)

        return session

    def _populate_session_from_restored(self, session: AgentSession) -> None:
        from linhai.agent.message import AgentMessage
        from linhai.base import UserMessage, AssistantMessage

        agent_message = session.registry.get_member_typechecked(
            "agent_message", AgentMessage
        )
        for msg in agent_message.messages:
            if isinstance(msg, UserMessage):
                session.add_user_message(msg.get_content())
            elif isinstance(msg, AssistantMessage):
                idx = session.add_agent_message()
                session.update_agent_message_content(idx, msg.get_content())

    def get_registry(self, agent_id: str) -> Optional[Registry]:
        return self._registries.get(agent_id)

    def get_config_info(self) -> dict:
        config = self._config
        profiles = [{"name": a.name} for a in config.agent if a.name]
        llms = [
            {"name": llm.name, "model": llm.model, "type": llm.type}
            for llm in config.llm
        ]
        return {"profiles": profiles, "llms": llms}

    def get_agent(self, agent_id: str) -> Optional[AgentSession]:
        return self.sessions.get(agent_id)

    def list_agents(self) -> list[AgentSession]:
        return list(self.sessions.values())

    async def delete_agent(self, agent_id: str) -> bool:
        session = self.sessions.get(agent_id)
        if session is None:
            return False

        await session.stop()
        await self._task_supervisor.check_tasks_for_errors()
        registry = self._registries.pop(agent_id, None)
        if registry is not None:
            await registry.call_cleanups()
        del self.sessions[agent_id]
        return True
