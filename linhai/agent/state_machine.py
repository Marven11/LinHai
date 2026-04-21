import asyncio
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

    async def execute_sleep(self) -> str:
        from .user_message_handler import UserMessageHandler

        user_message_handler = self.registry.get_member_typechecked(
            "user_message_handler", UserMessageHandler
        )
        assert self.sleeping_since is not None
        assert self.sleeping_deadline is not None

        while True:
            if self.state != "sleeping":
                return f"睡眠被中断，从 {self.sleeping_since.strftime('%Y-%m-%d %H:%M:%S')} 开始"
            if user_message_handler.has_message():
                should_interrupt = await user_message_handler.receive_and_dispatch()
                if should_interrupt:
                    self.finish_sleeping()
                    return f"睡眠被用户消息打断，从 {self.sleeping_since.strftime('%Y-%m-%d %H:%M:%S')} 开始"
            now = datetime.now()
            if now >= self.sleeping_deadline:
                break
            remaining = (self.sleeping_deadline - now).total_seconds()
            sleep_time = min(1.0, remaining)
            await asyncio.sleep(sleep_time)

        since = self.sleeping_since
        self.finish_sleeping()
        return f"睡眠完成，从 {since.strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

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
            result = await state_machine.execute_sleep()
            return ToolResultSuccess(content=result)

        return sleep_toolset
