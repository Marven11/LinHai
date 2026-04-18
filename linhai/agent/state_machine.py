from datetime import datetime, timedelta

from linhai.registry import Registry
from linhai.type_hints import AgentState
from linhai.utils.i18n import t
from linhai.tool.base import (
    ToolArgInfo,
    ToolSet,
    ToolResultSuccess,
)


class AgentStateMachine:
    def __init__(self, registry: Registry) -> None:
        self.state: AgentState = "waiting_user"
        self.sleeping_since: datetime | None = None
        self.sleeping_deadline: datetime | None = None
        self.registry = registry
        self.registry.register_member("state_machine", self)

    def transition_to_working(self) -> None:
        self.state = "working"

    def transition_to_sleeping(self, since: datetime, deadline: datetime) -> None:
        self.sleeping_since = since
        self.sleeping_deadline = deadline
        self.state = "sleeping"

    def transition_to_waiting_user(self) -> None:
        self.state = "waiting_user"

    def interrupt_to_working(self) -> None:
        if self.state == "sleeping":
            self.sleeping_since = None
            self.sleeping_deadline = None
        self.state = "working"

    def finish_sleeping(self) -> None:
        self.sleeping_since = None
        self.sleeping_deadline = None
        self.state = "working"

    def generate_sleep_toolset(self) -> ToolSet:
        state_machine = self
        sleep_toolset = ToolSet()

        @sleep_toolset.register_tool(
            name="sleep",
            desc=t(
                {
                    "zh_CN": "睡眠X秒，返回开始和结束时间",
                    "en": "Sleep for X seconds, return start and end time",
                }
            ),
            args={
                "seconds": ToolArgInfo(
                    desc=t({"zh_CN": "睡眠的秒数", "en": "Seconds to sleep"}),
                    type="float",
                )
            },
            required_args=["seconds"],
        )
        async def sleep_tool(seconds: float) -> ToolResultSuccess:
            start = datetime.now()
            state_machine.transition_to_sleeping(
                start, start + timedelta(seconds=seconds)
            )
            return ToolResultSuccess(
                content=f"开始睡眠{seconds}秒，从 {start.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        return sleep_toolset
