from typing import Literal, TypedDict, Tuple, Union, TYPE_CHECKING
import asyncio
import json
import re
from .base import Answer, Message, OpenAiToolCallToken, AnthropicToolCallToken
from .agent.lifecycle import Lifecycle
from .markdown_parser import extract_tool_calls_with_errors
from linhai.type_hints import (
    ToolCallDict,
    OpenAiToolCall,
    NativeToolCallResult,
)
from .utils.streamjson import StreamJsonParser, Value, ValuePiece
from .utils.common import BAD_TOOLCALL, guess_content_type

if TYPE_CHECKING:
    from .registry import Registry


class NormalSegment(TypedDict):
    segment_type: Literal["normal"]
    content: str
    is_finished: bool


class ReasoningSegment(TypedDict):
    segment_type: Literal["reasoning"]
    content: str
    is_finished: bool


class ToolCallSegment(TypedDict):
    segment_type: Literal["toolcall"]
    raw: str
    is_finished: bool
    is_corrupted: bool
    markdown_representation: str
    tool_name: str


class OpenAiToolCallSegment(TypedDict):
    segment_type: Literal["openai_toolcall"]
    idx: int
    id: str | None
    raw: str
    is_finished: bool
    is_corrupted: bool
    markdown_representation: str
    tool_name: str


class AnthropicToolCallSegment(TypedDict):
    segment_type: Literal["anthropic_toolcall"]
    idx: int
    id: str | None
    raw: str
    is_finished: bool
    is_corrupted: bool
    markdown_representation: str
    tool_name: str


Segment = Union[
    NormalSegment,
    ReasoningSegment,
    ToolCallSegment,
    OpenAiToolCallSegment,
    AnthropicToolCallSegment,
]


def _get_backtick_count(text: str) -> int:
    matches = re.findall(r"^`+", text, re.MULTILINE)
    max_count = max((len(m) for m in matches), default=0)
    return max(3, max_count + 1)


class ToolCallFeeder:
    def __init__(self, segment: ToolCallSegment):
        self._segment = segment
        self._parser = StreamJsonParser()
        self._current_key = ""
        self._current_value = ""
        self._content_before_current_value = ""
        self._current_content = ""
        self._guessed_content_type = ""

    def feed(self, content: str) -> None:
        self._segment["raw"] += content
        if self._segment["is_corrupted"]:
            return
        self._parser.feed_string(content)
        if self._parser.is_corrupted:
            self._segment["is_corrupted"] = True
            self._segment["markdown_representation"] = BAD_TOOLCALL
            return
        self._process_parser_values()

    def finish(self) -> None:
        self._segment["is_finished"] = True

    def _process_parser_values(self) -> None:
        for value in self._parser:
            if value.index_key != self._current_key:
                self._current_key = value.index_key
                self._content_before_current_value = self._current_content
                self._current_content += f"- {self._current_key}: `"

            if isinstance(value, Value):
                final_value = (
                    value.value
                    if isinstance(value.value, str)
                    else json.dumps(value.value, ensure_ascii=False)
                )
                if value.index_key == "name" and isinstance(value.value, str):
                    self._segment["tool_name"] = value.value

                if "\n" in final_value:
                    backticks = "`" * _get_backtick_count(final_value)
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}:\n\n{backticks}{self._guessed_content_type}\n{final_value}\n{backticks}\n\n"
                    )
                else:
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}: `{final_value}`\n"
                    )

                new_guessed_type = guess_content_type(final_value)
                if not self._guessed_content_type or new_guessed_type:
                    self._guessed_content_type = new_guessed_type

                self._current_value = ""

            elif isinstance(value, ValuePiece):
                self._current_value += value.token
                if "\n" in self._current_value:
                    backticks = "`" * _get_backtick_count(self._current_value)
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}:\n\n{backticks}{self._guessed_content_type}\n{self._current_value}\n{backticks}"
                    )
                else:
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}: `{self._current_value}`"
                    )

        self._segment["markdown_representation"] = self._current_content.strip()


class OpenAiToolCallFeeder:
    def __init__(self, segment: OpenAiToolCallSegment):
        self._segment = segment
        self._parser = StreamJsonParser()
        self._current_key = ""
        self._current_value = ""
        self._content_before_current_value = ""
        self._current_content = ""
        self._guessed_content_type = ""

    def feed(self, content: str) -> None:
        self._segment["raw"] += content
        if self._segment["is_corrupted"]:
            return
        self._parser.feed_string(content)
        if self._parser.is_corrupted:
            self._segment["is_corrupted"] = True
            self._segment["markdown_representation"] = BAD_TOOLCALL
            return
        self._process_parser_values()

    def finish(self) -> None:
        self._segment["is_finished"] = True

    def _process_parser_values(self) -> None:
        for value in self._parser:
            if value.index_key != self._current_key:
                self._current_key = value.index_key
                self._content_before_current_value = self._current_content
                self._current_content += f"- {self._current_key}: `"

            if isinstance(value, Value):
                final_value = (
                    value.value
                    if isinstance(value.value, str)
                    else json.dumps(value.value, ensure_ascii=False)
                )

                if "\n" in final_value:
                    backticks = "`" * _get_backtick_count(final_value)
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}:\n\n{backticks}{self._guessed_content_type}\n{final_value}\n{backticks}\n\n"
                    )
                else:
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}: `{final_value}`\n"
                    )

                new_guessed_type = guess_content_type(final_value)
                if not self._guessed_content_type or new_guessed_type:
                    self._guessed_content_type = new_guessed_type

                self._current_value = ""

            elif isinstance(value, ValuePiece):
                self._current_value += value.token
                if "\n" in self._current_value:
                    backticks = "`" * _get_backtick_count(self._current_value)
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}:\n\n{backticks}{self._guessed_content_type}\n{self._current_value}\n{backticks}"
                    )
                else:
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}: `{self._current_value}`"
                    )

        self._update_markdown()

    def _update_markdown(self) -> None:
        tool_name = self._segment["tool_name"] or "\u672a\u77e5\u5de5\u5177"
        args_md = self._current_content.strip()
        if args_md:
            self._segment["markdown_representation"] = f"{tool_name}:\n\n{args_md}"
        else:
            self._segment["markdown_representation"] = f"{tool_name}:"

    def refresh_tool_name(self) -> None:
        if not self._segment["is_corrupted"]:
            self._update_markdown()


class AnthropicToolCallFeeder:
    def __init__(self, segment: AnthropicToolCallSegment):
        self._segment = segment
        self._parser = StreamJsonParser()
        self._current_key = ""
        self._current_value = ""
        self._content_before_current_value = ""
        self._current_content = ""
        self._guessed_content_type = ""

    def feed(self, content: str) -> None:
        self._segment["raw"] += content
        if self._segment["is_corrupted"]:
            return
        self._parser.feed_string(content)
        if self._parser.is_corrupted:
            self._segment["is_corrupted"] = True
            self._segment["markdown_representation"] = BAD_TOOLCALL
            return
        self._process_parser_values()

    def finish(self) -> None:
        self._segment["is_finished"] = True

    def _process_parser_values(self) -> None:
        for value in self._parser:
            if value.index_key != self._current_key:
                self._current_key = value.index_key
                self._content_before_current_value = self._current_content
                self._current_content += f"- {self._current_key}: `"

            if isinstance(value, Value):
                final_value = (
                    value.value
                    if isinstance(value.value, str)
                    else json.dumps(value.value, ensure_ascii=False)
                )

                if "\n" in final_value:
                    backticks = "`" * _get_backtick_count(final_value)
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}:\n\n{backticks}{self._guessed_content_type}\n{final_value}\n{backticks}\n\n"
                    )
                else:
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}: `{final_value}`\n"
                    )

                new_guessed_type = guess_content_type(final_value)
                if not self._guessed_content_type or new_guessed_type:
                    self._guessed_content_type = new_guessed_type

                self._current_value = ""

            elif isinstance(value, ValuePiece):
                self._current_value += value.token
                if "\n" in self._current_value:
                    backticks = "`" * _get_backtick_count(self._current_value)
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}:\n\n{backticks}{self._guessed_content_type}\n{self._current_value}\n{backticks}"
                    )
                else:
                    self._current_content = (
                        self._content_before_current_value
                        + f"- {self._current_key}: `{self._current_value}`"
                    )

        self._update_markdown()

    def _update_markdown(self) -> None:
        tool_name = self._segment["tool_name"] or "\u672a\u77e5\u5de5\u5177"
        args_md = self._current_content.strip()
        if args_md:
            self._segment["markdown_representation"] = f"{tool_name}:\n\n{args_md}"
        else:
            self._segment["markdown_representation"] = f"{tool_name}:"

    def refresh_tool_name(self) -> None:
        if not self._segment["is_corrupted"]:
            self._update_markdown()


class ParsedAnswer:
    def __init__(
        self, answer: Answer, lifecycle: Lifecycle, agent, registry: "Registry"
    ):
        self._answer = answer
        self.lifecycle = lifecycle
        self.agent = agent
        self.registry = registry
        self.segment_queue: asyncio.Queue[Segment | None] = asyncio.Queue()
        self._parsing_task_name: str = f"parsed_answer_parsing_{id(self)}"
        self.interrupted = False
        from .utils.token_parser import TokenParser

        self.token_parser = TokenParser()
        self.current_segment: Segment | None = None
        self._current_feeder: ToolCallFeeder | None = None
        self._openai_toolcall_segments: dict[int, OpenAiToolCallSegment] = {}
        self._openai_toolcall_feeders: dict[int, OpenAiToolCallFeeder] = {}
        self._anthropic_toolcall_segments: dict[int, AnthropicToolCallSegment] = {}
        self._anthropic_toolcall_feeders: dict[int, AnthropicToolCallFeeder] = {}

    async def start_parsing(self):
        from linhai.task_supervisor import TaskSupervisor

        task_supervisor = self.registry.get_member_typechecked(
            "task_supervisor", TaskSupervisor
        )
        task_supervisor.create_supervised_task(
            self._parsing_task_name, self._parse_answer
        )

    def _create_segment(self, token_type: str, content: str) -> Segment:
        if token_type == "toolcall":
            segment: Segment = ToolCallSegment(
                segment_type="toolcall",
                raw="",
                is_finished=False,
                is_corrupted=False,
                markdown_representation="",
                tool_name="",
            )
            feeder = ToolCallFeeder(segment)
            feeder.feed(content)
            self._current_feeder = feeder
        elif token_type == "reasoning":
            segment = ReasoningSegment(
                segment_type="reasoning", content=content, is_finished=False
            )
        else:
            segment = NormalSegment(
                segment_type="normal", content=content, is_finished=False
            )
        return segment

    async def _process_token(self, parsed_token):
        token_type = parsed_token["token_type"]
        content = parsed_token["content"]
        if self.current_segment is None:
            self.current_segment = self._create_segment(token_type, content)
            await self.segment_queue.put(self.current_segment)
            await self.lifecycle.after_segment.trigger(self, self.current_segment)
        elif self.current_segment["segment_type"] == token_type:
            current = self.current_segment
            if current["segment_type"] == "toolcall":
                assert self._current_feeder is not None
                self._current_feeder.feed(content)
            elif current["segment_type"] == "openai_toolcall":
                pass
            elif current["segment_type"] == "anthropic_toolcall":
                pass
            else:
                current["content"] += content
            await self.lifecycle.after_segment_update.trigger(
                self, self.current_segment
            )
        else:
            self.current_segment["is_finished"] = True
            if self._current_feeder is not None:
                self._current_feeder.finish()
                self._current_feeder = None
            await self.lifecycle.after_segment_finished.trigger(
                self, self.current_segment
            )
            self.current_segment = self._create_segment(token_type, content)
            await self.lifecycle.after_segment.trigger(self, self.current_segment)
            await self.segment_queue.put(self.current_segment)

    async def _process_openai_toolcall_token(self, token: OpenAiToolCallToken) -> None:
        idx = token.idx
        segment = self._openai_toolcall_segments.get(idx)
        feeder = self._openai_toolcall_feeders.get(idx)
        if segment is None:
            segment = OpenAiToolCallSegment(
                segment_type="openai_toolcall",
                idx=idx,
                id=token.id,
                raw="",
                is_finished=False,
                is_corrupted=False,
                markdown_representation="",
                tool_name="",
            )
            self._openai_toolcall_segments[idx] = segment
            feeder = OpenAiToolCallFeeder(segment)
            self._openai_toolcall_feeders[idx] = feeder
            await self.segment_queue.put(segment)
            await self.lifecycle.after_segment.trigger(self, segment)
        assert feeder is not None
        if token.id is not None:
            segment["id"] = token.id
        if token.name is not None:
            segment["tool_name"] = token.name
            feeder.refresh_tool_name()
        if token.args is not None:
            feeder.feed(token.args)
        await self.lifecycle.after_segment_update.trigger(self, segment)

    async def _process_anthropic_toolcall_token(
        self, token: AnthropicToolCallToken
    ) -> None:
        idx = token.idx
        segment = self._anthropic_toolcall_segments.get(idx)
        feeder = self._anthropic_toolcall_feeders.get(idx)
        if segment is None:
            segment = AnthropicToolCallSegment(
                segment_type="anthropic_toolcall",
                idx=idx,
                id=token.id,
                raw="",
                is_finished=False,
                is_corrupted=False,
                markdown_representation="",
                tool_name="",
            )
            self._anthropic_toolcall_segments[idx] = segment
            feeder = AnthropicToolCallFeeder(segment)
            self._anthropic_toolcall_feeders[idx] = feeder
            await self.segment_queue.put(segment)
            await self.lifecycle.after_segment.trigger(self, segment)
        assert feeder is not None
        if token.id is not None:
            segment["id"] = token.id
        if token.name is not None:
            segment["tool_name"] = token.name
            feeder.refresh_tool_name()
        if token.args is not None:
            feeder.feed(token.args)
        await self.lifecycle.after_segment_update.trigger(self, segment)

    async def _finish_current_segment(self):
        if self.current_segment is not None:
            self.current_segment["is_finished"] = True
            if self._current_feeder is not None:
                self._current_feeder.finish()
                self._current_feeder = None
            await self.lifecycle.after_segment_finished.trigger(
                self, self.current_segment
            )

    async def _parse_answer(self):
        await self.lifecycle.before_parsing.trigger(self)
        async for token in self._answer:
            if self.interrupted:
                break
            if isinstance(token, AnthropicToolCallToken):
                await self._process_anthropic_toolcall_token(token)
                continue
            if isinstance(token, OpenAiToolCallToken):
                await self._process_openai_toolcall_token(token)
                continue
            reasoning_content = token.reasoning_content
            content_raw = reasoning_content or token.content
            if not content_raw:
                continue
            is_reasoning = reasoning_content is not None
            parsed_tokens = self.token_parser.receive_token(content_raw, is_reasoning)
            for parsed_token in parsed_tokens:
                await self._process_token(parsed_token)
            interrupted = await self.lifecycle.after_token_generation.trigger(
                self.agent, self._answer, self._answer.get_current_content() or ""
            )
            if interrupted:
                self.interrupted = True
                break
        for parsed_token in self.token_parser.clear():
            await self._process_token(parsed_token)
        await self._finish_current_segment()
        for idx, segment in self._openai_toolcall_segments.items():
            feeder = self._openai_toolcall_feeders.get(idx)
            if feeder is not None:
                feeder.finish()
            segment["is_finished"] = True
            await self.lifecycle.after_segment_finished.trigger(self, segment)
        for idx, segment in self._anthropic_toolcall_segments.items():
            feeder = self._anthropic_toolcall_feeders.get(idx)
            if feeder is not None:
                feeder.finish()
            segment["is_finished"] = True
            await self.lifecycle.after_segment_finished.trigger(self, segment)
        await self.segment_queue.put(None)
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

    def get_message(self) -> Message:
        return self._answer.get_message()

    def extract_tool_calls_with_errors(self) -> Tuple[list[ToolCallDict], list[str]]:
        full_response = self._answer.get_current_content() or ""
        tool_calls, errors = extract_tool_calls_with_errors(full_response)
        return tool_calls, errors

    async def get_openai_toolcalls(self) -> list[NativeToolCallResult] | None:
        """获取解析后的OpenAI工具调用列表，参数已解析为dict。"""
        return await self._answer.get_openai_toolcalls()

    async def get_anthropic_toolcalls(self) -> list[NativeToolCallResult] | None:
        """获取解析后的Anthropic工具调用列表，参数已解析为dict。"""
        return await self._answer.get_anthropic_toolcalls()
