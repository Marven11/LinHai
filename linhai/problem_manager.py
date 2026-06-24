from __future__ import annotations

import asyncio
import time
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from linhai.utils.common import generate_id


def _display_width(text: str) -> int:
    width = 0
    for ch in text:
        ea = unicodedata.east_asian_width(ch)
        width += 2 if ea in ("W", "F") else 1
    return width


if TYPE_CHECKING:
    from linhai.registry import Registry
    from linhai.tool.base import ToolSet


@runtime_checkable
class ProblemManagerProtocol(Protocol):
    def create_problem(self, content: str, options: list[str]) -> str: ...

    def set_answer(self, problem_id: str, answer: str) -> None: ...

    async def wait_answer(self, problem_id: str, timeout: float) -> str: ...


@dataclass
class ProblemData:
    content: str
    options: list[str]
    created_at: float = field(default_factory=time.monotonic)
    answer: str | None = None


class PlainProblemManager:
    def __init__(self, registry: "Registry") -> None:
        self._problems: dict[str, ProblemData] = {}
        registry.register_member("problem_manager", self)

    def create_problem(self, content: str, options: list[str]) -> str:
        if not options:
            raise ValueError("options cannot be empty")
        if "\n" in content:
            raise ValueError("content cannot contain newlines")
        if _display_width(content) > 240:
            raise ValueError(
                f"content display width {_display_width(content)} exceeds 240 (3 lines * 80 chars)"
            )
        for option in options:
            if "\n" in option:
                raise ValueError(f"option contains newline: {option!r}")
        problem_id = generate_id("problem")
        self._problems[problem_id] = ProblemData(content=content, options=options)
        return problem_id

    def set_answer(self, problem_id: str, answer: str) -> None:
        if problem_id not in self._problems:
            raise RuntimeError(f"problem {problem_id} not found")
        problem = self._problems[problem_id]
        if problem.answer is not None:
            raise RuntimeError(f"problem {problem_id} already answered")
        problem.answer = answer

    async def wait_answer(self, problem_id: str, timeout: float) -> str:
        if problem_id not in self._problems:
            raise RuntimeError(f"problem {problem_id} not found")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            problem = self._problems[problem_id]
            if problem.answer is not None:
                return problem.answer
            await asyncio.sleep(0.1)
        raise asyncio.TimeoutError()

    def get_problem(self, problem_id: str) -> ProblemData:
        if problem_id not in self._problems:
            raise RuntimeError(f"problem {problem_id} not found")
        return self._problems[problem_id]

    def get_unanswered_problems(self) -> list[tuple[str, ProblemData]]:
        return [(pid, p) for pid, p in self._problems.items() if p.answer is None]

    def create_toolset(self) -> ToolSet:
        from linhai.tool.base import (
            ToolSet,
            ToolArgInfo,
            SuccessfulToolResult,
        )
        from linhai.utils.i18n import t

        toolset = ToolSet()

        @toolset.register_tool(
            name="problem_create",
            desc=t(
                {
                    "zh_CN": "创建一个选择题问题，等待用户回答。返回问题ID",
                    "en": "Create a multiple-choice problem, wait for user answer. Returns problem ID",
                }
            ),
            args={
                "content": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "问题内容",
                            "en": "Problem content",
                        }
                    ),
                    schema={"type": "string"},
                ),
                "options": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": '选项列表，例如 ["是 - 允许...", "否 - 不允许...", "其他 - ..."]',
                            "en": 'List of options, e.g. ["yes - allow...", "no - disallow...", "other - ..."]',
                        }
                    ),
                    schema={"type": "array", "items": {"type": "string"}},
                ),
            },
            required_args=["content", "options"],
        )
        def problem_create(content: str, options: list[str]):
            pid = self.create_problem(content, options)
            return SuccessfulToolResult(content=pid)

        @toolset.register_tool(
            name="problem_wait_answer",
            desc=t(
                {
                    "zh_CN": "等待问题回答，有回答则立即返回回答内容",
                    "en": "Wait for problem answer, return answer content immediately when available",
                }
            ),
            args={
                "problem_id": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "问题ID",
                            "en": "Problem ID",
                        }
                    ),
                    schema={"type": "string"},
                ),
                "timeout": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "超时时间（秒），默认60秒",
                            "en": "Timeout in seconds, default 60",
                        }
                    ),
                    schema={"type": "number"},
                ),
            },
            required_args=["problem_id"],
        )
        async def problem_wait_answer(problem_id: str, timeout: float = 60.0):
            answer = await self.wait_answer(problem_id, timeout)
            return SuccessfulToolResult(content=answer)

        return toolset
