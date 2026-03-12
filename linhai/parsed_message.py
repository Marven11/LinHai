from typing import Literal, TypedDict
import asyncio
from .llm import Answer
from .agent.lifecycle import Lifecycle


class Segment(TypedDict):
    segment_type: Literal["reasoning", "normal", "toolcall"]
    content: str
    is_finished: bool


class ParsedAnswer:
    def __init__(self, answer: Answer, lifecycle: Lifecycle, agent):
        self.answer = answer
        self.lifecycle = lifecycle
        self.agent = agent
        self.segment_queue: asyncio.Queue[Segment] = asyncio.Queue()
        self.parsing_task = None
        self.interrupted = False
        from .cli.token_parser import TokenParser

        self.token_parser = TokenParser()
        self.current_segment = None

    async def start_parsing(self):
        self.parsing_task = asyncio.create_task(self._parse_answer())

    async def _process_token(self, parsed_token):
        token_type = parsed_token["token_type"]
        content = parsed_token["content"]
        if self.current_segment is None:
            # 创建segment并立即放入队列
            self.current_segment = Segment(
                segment_type=token_type, content=content, is_finished=False
            )
            await self.segment_queue.put(self.current_segment)
            await self.lifecycle.trigger_after_segment(self, self.current_segment)
        elif self.current_segment["segment_type"] == token_type:
            # 类型相同，更新内容（队列中的segment是同一对象引用，会自动更新）
            self.current_segment["content"] += content
        else:
            # 类型变化：直接创建新segment并放入队列（丢掉前一个）
            self.current_segment["is_finished"] = True
            await self.lifecycle.trigger_after_segment_finished(
                self, self.current_segment
            )
            self.current_segment = Segment(
                segment_type=token_type, content=content, is_finished=False
            )
            await self.lifecycle.trigger_after_segment(self, self.current_segment)
            await self.segment_queue.put(self.current_segment)

    async def _finish_current_segment(self):
        if self.current_segment is not None:
            # 标记当前segment完成（队列中已有该对象，只需更新状态）
            self.current_segment["is_finished"] = True
            await self.lifecycle.trigger_after_segment_finished(
                self, self.current_segment
            )

    async def _parse_answer(self):
        await self.lifecycle.trigger_before_parsing(self)
        async for token in self.answer:
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
            interrupted = await self.lifecycle.trigger_after_token_generation(
                self.agent, self.answer, self.answer.get_current_content()
            )
            if interrupted:
                self.interrupted = True
                break
        for parsed_token in self.token_parser.clear():
            await self._process_token(parsed_token)
        await self._finish_current_segment()
        await self.lifecycle.trigger_after_parsing(self)

    async def wait_parsing(self):
        if self.parsing_task:
            await self.parsing_task
        return not self.interrupted

    def interrupt(self):
        self.interrupted = True
        self.answer.interrupt()
