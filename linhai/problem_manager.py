import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from linhai.utils.common import generate_id

if TYPE_CHECKING:
    from linhai.registry import Registry


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
