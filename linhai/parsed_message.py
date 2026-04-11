from typing import Literal, TypedDict, Tuple, TYPE_CHECKING
import asyncio
from .base import Answer
from .agent.lifecycle import Lifecycle
from .markdown_parser import extract_tool_calls_with_errors

if TYPE_CHECKING:
    from .registry import Registry


class Segment(TypedDict):
    segment_type: Literal["reasoning", "normal", "toolcall"]
    content: str
    is_finished: bool


class ParsedAnswer:
    def __init__(
        self, answer: Answer, lifecycle: Lifecycle, agent, registry: "Registry"
    ):
        self._answer = answer
        self.lifecycle = lifecycle
        self.agent = agent
        self.registry = registry
        self.segment_queue: asyncio.Queue[Segment] = asyncio.Queue()
        self._parsing_task_name: str = f"parsed_answer_parsing_{id(self)}"
        self.interrupted = False
        from .utils.token_parser import TokenParser

        self.token_parser = TokenParser()
        self.current_segment = None

    async def start_parsing(self):
        from linhai.task_supervisor import TaskSupervisor

        task_supervisor = self.registry.get_member_typechecked(
            "task_supervisor", TaskSupervisor
        )
        task_supervisor.create_supervised_task(
            self._parsing_task_name, self._parse_answer
        )

    async def _process_token(self, parsed_token):
        token_type = parsed_token["token_type"]
        content = parsed_token["content"]
        if self.current_segment is None:
            # 创建segment并立即放入队列
            self.current_segment = Segment(
                segment_type=token_type, content=content, is_finished=False
            )
            await self.segment_queue.put(self.current_segment)
            await self.lifecycle.after_segment.trigger(self, self.current_segment)
        elif self.current_segment["segment_type"] == token_type:
            self.current_segment["content"] += content
            await self.lifecycle.after_segment_update.trigger(
                self, self.current_segment
            )
        else:
            # 类型变化：直接创建新segment并放入队列（丢掉前一个）
            self.current_segment["is_finished"] = True
            await self.lifecycle.after_segment_finished.trigger(
                self, self.current_segment
            )
            self.current_segment = Segment(
                segment_type=token_type, content=content, is_finished=False
            )
            await self.lifecycle.after_segment.trigger(self, self.current_segment)
            await self.segment_queue.put(self.current_segment)

    async def _finish_current_segment(self):
        if self.current_segment is not None:
            # 标记当前segment完成（队列中已有该对象，只需更新状态）
            self.current_segment["is_finished"] = True
            await self.lifecycle.after_segment_finished.trigger(
                self, self.current_segment
            )

    async def _parse_answer(self):
        await self.lifecycle.before_parsing.trigger(self)
        async for token in self._answer:
            if self.interrupted:
                break
            reasoning_content = token.reasoning_content
            content_raw = reasoning_content or token.content
            if not content_raw:
                continue
            is_reasoning = reasoning_content is not None
            parsed_tokens = self.token_parser.receive_token(content_raw, is_reasoning)
            for parsed_token in parsed_tokens:
                await self._process_token(parsed_token)
            interrupted = await self.lifecycle.after_token_generation.trigger(
                self.agent, self._answer, self._answer.get_current_content()
            )
            if interrupted:
                self.interrupted = True
                break
        for parsed_token in self.token_parser.clear():
            await self._process_token(parsed_token)
        await self._finish_current_segment()
        await self.lifecycle.after_parsing.trigger(self)

    async def wait_parsing(self):
        from linhai.task_supervisor import TaskSupervisor

        task_supervisor = self.registry.get_member_typechecked(
            "task_supervisor", TaskSupervisor
        )
        await task_supervisor.wait(self._parsing_task_name)
        return not self.interrupted

    def interrupt(self):
        self.interrupted = True
        self._answer.interrupt()

    def get_toolcalls(self) -> Tuple[list[dict], list[str]]:
        """获取工具调用和错误列表。

        Returns:
            Tuple[list[dict], list[str]]: (工具调用列表, 错误列表)
        """
        full_response = self._answer.get_current_content()
        tool_calls, errors = extract_tool_calls_with_errors(full_response)
        return tool_calls, errors
