"""AgentManager模块，管理多个Agent实例的生命周期。"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.agent.create import (
    AgentBuildArguments,
    create_agent_build_context,
    create_agent_from_context,
)
from linhai.agent.main import Agent
from linhai.config import load_config
from linhai.llm import UserMessage, Message, AssistantMessage, SystemMessage


class AgentSession:
    """封装单个Agent及其运行任务。"""

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

    def get_state(self) -> str:
        """获取Agent当前状态。"""
        return self.agent.state_machine.state

    @property
    def registry(self) -> Registry:
        return self.agent.registry

    def get_current_llm(self) -> Optional[str]:
        _, llm_instance = self.agent.get_current_llm_info()
        return llm_instance.get_name()

    async def send_message(self, content: str) -> None:
        await self.registry.send("user_message", UserMessage(content))

    def get_messages(self) -> list[dict]:
        result: list[dict] = []
        for msg in self.agent.message_processor.get_messages():
            role = self._get_message_role(msg)
            if role is None:
                continue
            content = self._get_message_content(msg)
            if content is None:
                continue
            result.append({"role": role, "content": content})
        return result

    @staticmethod
    def _get_message_role(msg: Message) -> Optional[str]:
        if isinstance(msg, SystemMessage):
            return "system"
        if isinstance(msg, UserMessage):
            return "user"
        if isinstance(msg, AssistantMessage):
            return "assistant"
        return None

    @staticmethod
    def _get_message_content(msg: Message) -> Optional[str]:
        if isinstance(msg, (UserMessage, AssistantMessage)):
            return msg.message
        return msg.get_content()

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

    async def stop(self) -> None:
        """停止Agent并清理资源。"""
        task = self._manager._task_supervisor.tasks.get(self._task_name)
        if task is not None and not task.done():
            self._manager._task_supervisor.cancel(self._task_name)
            await asyncio.sleep(0)


class AgentManager:
    """管理多个Agent实例的生命周期。"""

    def __init__(self, config_path: Path):
        self.sessions: dict[str, AgentSession] = {}
        self._registries: dict[str, Registry] = {}
        self.config_path = config_path
        self._config = load_config(self.config_path)
        self._task_supervisor = PlainTaskSupervisor()

    def _create_registry(self) -> Registry:
        """创建独立的Registry实例。"""
        registry = Registry()
        registry.register_member("task_supervisor", self._task_supervisor)
        return registry

    async def create_agent(
        self,
        profile_name: Optional[str] = None,
        init_messages: Optional[list[str]] = None,
    ) -> AgentSession:
        """创建新的Agent实例。"""
        agent_id = str(uuid.uuid4())
        registry = self._create_registry()

        build_args: AgentBuildArguments = {
            "rss": [],
            "telegram": False,
            "disable_waiting_marker": False,
            "afk": False,
            "claw_enabled": False,
            "claw_folder": None,
            "message": init_messages or [],
            "file": [],
            "planning": False,
            "llm_name": None,
            "checklist_path": None,
            "profile_name": profile_name,
        }

        context = create_agent_build_context(
            registry=registry,
            config=self._config,
            config_basedir=Path(self.config_path).parent,
            build_args=build_args,
        )

        agent = await create_agent_from_context(context)

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
        """列出所有Agent实例。"""
        return list(self.sessions.values())

    async def delete_agent(self, agent_id: str) -> bool:
        """停止并删除指定的Agent。"""
        session = self.sessions.get(agent_id)
        if session is None:
            return False

        await session.stop()
        registry = self._registries.pop(agent_id, None)
        if registry is not None:
            await registry.call_cleanups()
        del self.sessions[agent_id]
        return True
