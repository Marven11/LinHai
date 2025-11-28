"""澄清系统管理模块，负责Agent和SubAgent之间的问答交互。"""

import asyncio
import logging
from typing import TypedDict
from datetime import datetime

from linhai.group_chat import GroupChat
from linhai.utils import CliRuntimeNotice
from linhai.agent.base import RuntimeMessage

logger = logging.getLogger(__name__)


class Clarification(TypedDict):
    """澄清问题数据结构"""

    id: str
    question: str
    from_subagent: str
    created_at: datetime
    answered: bool
    answer: str | None


class ClarificationManager:
    """澄清管理器，负责管理Agent和SubAgent之间的澄清问答。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat
        self.clarifications: dict[str, Clarification] = {}
        self._response_events: dict[str, asyncio.Event] = {}
        group_chat.register_member("clarification_manager", self)

    def has_unanswered_clarifications(self) -> bool:
        """检查是否有未解答的澄清。"""
        return any(not c["answered"] for c in self.clarifications.values())

    async def add_clarification(
        self, clarification_id: str, question: str, from_subagent: str
    ) -> None:
        """添加一个新的澄清问题。"""
        self.clarifications[clarification_id] = {
            "id": clarification_id,
            "question": question,
            "from_subagent": from_subagent,
            "created_at": datetime.now(),
            "answered": False,
            "answer": None,
        }
        self._response_events[clarification_id] = asyncio.Event()

        from linhai.agent.message import AgentMessage

        agent_message = self.group_chat.get_members("agent_message", AgentMessage)
        agent_message.append_message(
            RuntimeMessage(
                f"收到来自SubAgent(@{from_subagent})的澄清问题，ID为{clarification_id}，请尽快使用工具回答: {question}"
            )
        )

        from linhai.agent.main import Agent

        agent = self.group_chat.get_members("agent", Agent)
        if agent.state == "waiting_user":
            agent.state = "working"

    async def request_clarification(
        self, clarification_id: str, question: str, from_subagent: str
    ) -> None:
        """请求澄清并通知Agent。"""
        await self.add_clarification(clarification_id, question, from_subagent)

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"SubAgent添加了澄清请求{clarification_id}"
            ),
        )

    async def wait_for_response(self, clarification_id: str) -> str:
        """等待指定澄清的回复。"""
        if clarification_id not in self._response_events:
            raise ValueError(f"澄清 {clarification_id} 不存在")

        await self._response_events[clarification_id].wait()
        clarification = self.clarifications[clarification_id]
        assert clarification["answer"] is not None
        return clarification["answer"]

    def respond_clarification(self, clarification_id: str, answer: str) -> None:
        """回复一个澄清问题。"""
        if clarification_id not in self.clarifications:
            raise ValueError(f"澄清 {clarification_id} 不存在")

        clarification = self.clarifications[clarification_id]
        clarification["answered"] = True
        clarification["answer"] = answer

        if clarification_id in self._response_events:
            self._response_events[clarification_id].set()

        logger.info("回复澄清 %s: %s", clarification_id, answer)

    def get_unanswered_clarifications(self) -> list[Clarification]:
        """获取所有未解答的澄清列表。"""
        return [c for c in self.clarifications.values() if not c["answered"]]
