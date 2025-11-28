"""澄清请求SubAgent类型实现。"""

from typing import TYPE_CHECKING
import logging

from linhai.subagent.main import SubAgent
from .prompts import CLARIFIER_SUBAGENT_PROMPT

if TYPE_CHECKING:
    import linhai.agent

logger = logging.getLogger(__name__)


class ClarifierSubAgent(SubAgent):
    """澄清请求SubAgent。"""

    def __init__(
        self,
        name: str,
        task_message: str,
        llm,
        group_chat,
        max_answer_times: int | None,
        initial_messages=None,
    ):
        super().__init__(
            agent_type="clarifier",
            name=name,
            task_message=task_message,
            llm=llm,
            group_chat=group_chat,
            max_answer_times=max_answer_times,
            initial_messages=initial_messages,
        )

    def get_system_message_prompt(self) -> str:
        """返回澄清请求专用的系统消息prompt。"""
        import json
        from linhai.tool.base import to_tools_info
        tools_json = json.dumps(
            to_tools_info(self.toolset.get_tools()),
            ensure_ascii=False,
        )
        return CLARIFIER_SUBAGENT_PROMPT.replace("{|TOOLS|}", tools_json)


