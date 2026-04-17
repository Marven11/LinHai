import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

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
from linhai.jsonpubsub import JsonPublisher, TaggedEvent
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
        self._messages_data: dict = {"messages": []}
        self._publisher = JsonPublisher(self._messages_data)
        self._processes_data: dict = {"processes": []}
        self._process_publisher = JsonPublisher(self._processes_data)
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
        self._messages_data["messages"].append(msg)

    def add_notification(self, level: str, content: str) -> None:
        msg: WebuiNotificationMessage = {
            "type": "notification",
            "level": level,
            "content": content,
        }
        self._messages_data["messages"].append(msg)

    def add_agent_message(self) -> int:
        msg: WebuiAgentMessage = {
            "type": "agent",
            "content": "",
            "segments": [],
        }
        self._messages_data["messages"].append(msg)
        return len(self._messages_data["messages"]) - 1

    def add_segment_to_agent_message(
        self, agent_idx: int, segment: WebuiSegmentType
    ) -> None:
        agent_msg = self._messages_data["messages"][agent_idx]
        agent_msg["segments"].append(segment)

    def update_agent_message_content(self, agent_idx: int, content: str) -> None:
        agent_msg = self._messages_data["messages"][agent_idx]
        agent_msg["content"] = content

    async def get_diff(self) -> list[TaggedEvent]:
        async with self._lock:
            return self._publisher.calculate_diff()

    async def handle_reset(self) -> TaggedEvent:
        async with self._lock:
            return self._publisher.reset()

    def get_context_stats(self) -> dict:
        agent = self.agent
        mp = agent.message_processor
        registry = self.registry

        threshold_info = agent.get_threshold_info()
        usage_ratio = None
        traffic_light = "绿灯"
        if threshold_info is not None:
            usage_ratio = threshold_info["usage_ratio"]
            percentage = usage_ratio * 100
            if percentage < 80:
                traffic_light = "绿灯"
            elif percentage < 90:
                traffic_light = "黄灯"
            else:
                traffic_light = "红灯"

        is_dirty = False
        large_message_count = 0
        if registry.has_member("token_manager"):
            from linhai.token_manager import TokenManager

            token_manager = registry.get_member_typechecked(
                "token_manager", TokenManager
            )
            is_dirty = token_manager.is_dirty

        if registry.has_member("agent_context_orchestration"):
            from linhai.agent.orchestration import AgentContextOrchestration

            orchestration = registry.get_member_typechecked(
                "agent_context_orchestration", AgentContextOrchestration
            )
            large_message_count = len(orchestration.large_messages)

        cumulative_usage = None
        generation_count = 0
        if registry.has_member("token_manager"):
            from linhai.token_manager import TokenManager

            token_manager = registry.get_member_typechecked(
                "token_manager", TokenManager
            )
            generation_count = token_manager.generation_count
            if token_manager.cumulative_token_usage is not None:
                cu = token_manager.cumulative_token_usage
                cumulative_usage = {
                    "input_tokens": cu["input_tokens"],
                    "output_tokens": cu["output_tokens"],
                    "total_tokens": cu["total_tokens"],
                    "cached_input_tokens": cu["cached_input_tokens"],
                    "cache_creation_input_tokens": cu["cache_creation_input_tokens"],
                    "message_count": cu["message_count"],
                    "cache_miss_count": cu["cache_miss_count"],
                }

        return {
            "message_count": mp.get_message_count(),
            "pinned_message_count": len(mp.pinned_messages),
            "notification_count": len(mp.notification_messages),
            "large_message_count": large_message_count,
            "traffic_light": traffic_light,
            "context_usage_ratio": usage_ratio,
            "is_dirty": is_dirty,
            "cumulative_token_usage": cumulative_usage,
            "generation_count": generation_count,
        }

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

    def get_processes(self) -> list[dict[str, str]]:
        if not self.registry.has_member("machine_control"):
            return []
        from linhai.machine_control.main import MachineControl

        mc = self.registry.get_member_typechecked("machine_control", MachineControl)
        return mc.list_processes()

    def sync_processes(self) -> list[TaggedEvent]:
        self._processes_data["processes"] = self.get_processes()
        return self._process_publisher.calculate_diff()

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

        return session

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
