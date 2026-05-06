import asyncio
import json
from datetime import datetime
from typing import TYPE_CHECKING

from croniter import croniter

from linhai.base import LanguageModelMessage, Message, register_message

if TYPE_CHECKING:
    from linhai.agent.main import Agent

from linhai.agent.state_machine import AgentStateMachine


@register_message
class CronDiffMessage(Message):

    def __init__(self, cron_expression: str, command: str, result: str):
        self.cron_expression = cron_expression
        self.command = command
        self.result = result

    def to_llm_message(self) -> LanguageModelMessage:
        return {"role": "user", "content": self.get_content()}

    def get_content(self) -> str:
        return (
            "<<cron_diff>>\n"
            f"<<cron_expression>>{self.cron_expression}<<cron_expression>>\n"
            f"<<command>>{self.command}<<command>>\n"
            f"<<result>>{self.result}<<result>>\n"
            "<<cron_diff>>"
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "cron_expression": self.cron_expression,
                "command": self.command,
                "result": self.result,
            }
        )

    @classmethod
    def from_json(cls, json_str: str, registry):
        data = json.loads(json_str)
        return cls(
            cron_expression=data["cron_expression"],
            command=data["command"],
            result=data["result"],
        )


def _format_result(stdout: str, stderr: str, pid: int) -> str:
    return f"stdout:\n\n{stdout}\n\nstderr:\n\n{stderr}\n\npid:\n\n{pid}"


def parse_cron_arg(cron_arg: str) -> tuple[str, str]:
    parts = cron_arg.split(None, 5)
    if len(parts) < 6:
        raise ValueError(
            f"Invalid --cron format: '{cron_arg}'. "
            "Expected: '<cron_expression> <command>'"
        )
    cron_expression = " ".join(parts[:5])
    command = parts[5]
    return cron_expression, command


class CronPlugin:

    def __init__(self, registry, cron_expression: str, command: str):
        self.registry = registry
        self.cron_expression = cron_expression
        self.command = command
        self._last_result: str | None = None

    async def _run_command_with_timeout(self, timeout: float) -> tuple[str, str, int]:
        proc = await asyncio.create_subprocess_shell(
            self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        communicate_task = asyncio.ensure_future(proc.communicate())
        done, _ = await asyncio.wait({communicate_task}, timeout=timeout)
        if communicate_task in done:
            stdout_bytes, stderr_bytes = communicate_task.result()
        else:
            proc.kill()
            stdout_bytes, stderr_bytes = await communicate_task
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return stdout, stderr, proc.pid

    async def _run_loop(self) -> None:
        from linhai.agent import Agent as AgentType

        agent = self.registry.get_member_typechecked("agent", AgentType)
        cron = croniter(self.cron_expression, datetime.now())
        next_time = cron.get_next(datetime)

        while True:
            now = datetime.now()
            sleep_seconds = (next_time - now).total_seconds()
            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)

            next_time = cron.get_next(datetime)
            timeout = max((next_time - datetime.now()).total_seconds(), 1.0)

            stdout, stderr, pid = await self._run_command_with_timeout(timeout)
            current_result = _format_result(stdout, stderr, pid)

            if self._last_result is not None and current_result != self._last_result:
                if agent:
                    msg = CronDiffMessage(
                        cron_expression=self.cron_expression,
                        command=self.command,
                        result=current_result,
                    )
                    await agent.message_processor.add_new_message(msg)
                    state_machine = self.registry.get_member_typechecked(
                        "state_machine", AgentStateMachine
                    )
                    state_machine.interrupt_to_working()

            self._last_result = current_result

    async def before_agent_loop(self, _agent: "Agent") -> None:
        from linhai.task_supervisor import TaskSupervisor

        task_supervisor = self.registry.get_member_typechecked(
            "task_supervisor", TaskSupervisor
        )
        task_name = f"cron_{self.cron_expression}_{self.command}"
        task_supervisor.create_supervised_task(task_name, self._run_loop)

    def register(self, lifecycle) -> None:
        lifecycle.before_agent_loop.register(self.before_agent_loop)
