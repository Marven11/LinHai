"""SubAgent消息包装类，用于在队列中传输AnswerToken和Answer。"""

from dataclasses import dataclass
from typing import Union

from linhai.llm import AnswerToken, Answer
from linhai.parsed_message import ParsedAnswer
from linhai.utils import CliRuntimeNotice


@dataclass
class SubAgentAnswerTokenWrapper:
    """SubAgent的AnswerToken包装类，包含subagent名称和token。"""

    subagent_name: str
    token: AnswerToken


@dataclass
class SubAgentAnswerCompleteWrapper:
    """SubAgent的Answer完成包装类，包含subagent名称和完整的answer。"""

    subagent_name: str
    answer: Answer


@dataclass
class SubAgentNoticeWrapper:
    """SubAgent的CliRuntimeNotice包装类，用于传输运行时通知。"""

    subagent_name: str
    notice: CliRuntimeNotice


@dataclass
class SubAgentParsedAnswerWrapper:
    """SubAgent的ParsedAnswer包装类，用于传输解析后的回答。"""

    subagent_name: str
    parsed_answer: ParsedAnswer


SubAgentMessageWrapper = Union[
    SubAgentAnswerTokenWrapper, SubAgentAnswerCompleteWrapper, SubAgentNoticeWrapper, SubAgentParsedAnswerWrapper
]
