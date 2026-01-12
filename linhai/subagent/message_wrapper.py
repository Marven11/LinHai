"""SubAgent消息包装类，用于在队列中传输SubAgent消息。"""

from dataclasses import dataclass
from typing import Union

from linhai.llm import Answer
from linhai.parsed_message import ParsedAnswer
from linhai.utils import CliRuntimeNotice


@dataclass
class SubAgentParsedAnswerWrapper:
    """SubAgent的ParsedAnswer包装类，用于传输解析后的回答。"""

    subagent_name: str
    parsed_answer: ParsedAnswer


SubAgentMessageWrapper = Union[SubAgentParsedAnswerWrapper]
