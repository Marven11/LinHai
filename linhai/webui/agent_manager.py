"""AgentManager模块，管理多个Agent实例的生命周期。"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional

from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.agent.create import (
    AgentBuildArguments,
    create_agent_build_context,
    create_agent_from_context,
)
from linhai.agent.main import Agent
from linhai.config import load_config, get_default_config_path
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

    async def stop(self) -> None:
        """停止Agent并清理资源。"""
        task = self._manager._task_supervisor.tasks.get(self._task_name)
        if task is not None and not task.done():
            self._manager._task_supervisor.cancel(self._task_name)
            await asyncio.sleep(0)


class AgentManager:
    """管理多个Agent实例的生命周期。"""

    def __init__(self, config_path: Optional[str] = None):
        self.sessions: dict[str, AgentSession] = {}
        self._registries: dict[str, Registry] = {}
        self.config_path = config_path or str(get_default_config_path())
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
            config_basedir=None,
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
