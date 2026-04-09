"""检测生硬猫娘语气的插件。"""

import re
import time
from typing import TYPE_CHECKING

from .message_checkers import Plugin
from linhai.agent import Agent
from linhai.agent.messages import RuntimeMessage

if TYPE_CHECKING:
    from linhai.agent.lifecycle import Lifecycle
    from linhai.parsed_message import Segment
    from linhai.registry import Registry


class CatgirlTonePlugin(Plugin):
    """检测生硬猫娘语气输出的插件。"""

    WARNING_INTERVAL_SECONDS = 120
    PATTERN = re.compile(r"。喵[~。！]?$")

    def __init__(self, registry: "Registry"):
        super().__init__(registry)
        self._last_warning_time = None

    async def after_segment_finished(self, _parsed_answer, segment: "Segment"):
        if segment["segment_type"] != "normal":
            return

        content = segment["content"]
        lines = content.split("\n")
        if len(lines) != 1:
            return

        line = lines[0].strip()
        if not self.PATTERN.search(line):
            current_time = time.time()
            if (
                self._last_warning_time is not None
                and current_time - self._last_warning_time
                > self.WARNING_INTERVAL_SECONDS
            ):
                self._last_warning_time = None
            return

        current_time = time.time()
        if (
            self._last_warning_time is not None
            and current_time - self._last_warning_time <= self.WARNING_INTERVAL_SECONDS
        ):
            return

        agent = self.registry.get_member_typechecked("agent", Agent)
        warning_msg = (
            "你生硬地输出了喵，这符合用户的期望吗？为什么输出这么生硬？如果你真的特别忙"
            "能不能什么都不输出，安静地调用工具，而不是生硬地喵来喵去假装自己在满足用户的需求？"
            "如果你确实需要说一些什么，为什么不能像一只猫娘而不是像一个机器人一样说话？"
        )
        await agent.message_processor.add_new_message(RuntimeMessage(warning_msg))
        self._last_warning_time = current_time

    def register(self, lifecycle: "Lifecycle"):
        lifecycle.after_segment_finished.register(self.after_segment_finished)
