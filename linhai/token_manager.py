"""Token management logic for TUI."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
from linhai.base import AnswerTokenUsage
from linhai.registry import Registry
from linhai.type_hints import CumulativeTokenUsage

if TYPE_CHECKING:
    from linhai.agent import Agent


MAX_RECENT_GENERATIONS = 50


@dataclass
class TokenInfo:
    is_dirty: bool
    last_valid_token_usage: Optional[AnswerTokenUsage]
    cumulative_token_usage: Optional[CumulativeTokenUsage]


class TokenManager:
    """Manager for token usage tracking and display."""

    def __init__(self, registry: Registry):
        registry.register_member("token_manager", self)
        self.registry = registry
        self._current_token_usage: Optional[AnswerTokenUsage] = None
        self._last_valid_token_usage: Optional[AnswerTokenUsage] = None
        self.cumulative_token_usage: Optional[CumulativeTokenUsage] = None
        self.recent_generations: list[AnswerTokenUsage] = []
        self.explicit_cache_tokens: int = 0
        self.is_dirty: bool = False
        self.generation_count: int = 0

    def get_token_info(self) -> TokenInfo:
        return TokenInfo(
            is_dirty=self.is_dirty,
            last_valid_token_usage=self._last_valid_token_usage,
            cumulative_token_usage=self.cumulative_token_usage,
        )

    def mark_dirty(self) -> None:
        self.is_dirty = True
        self._current_token_usage = None
        if self.cumulative_token_usage is not None:
            self.cumulative_token_usage["cache_miss_count"] += 1

    def start_watching(self) -> None:
        from linhai.agent.lifecycle import Lifecycle

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        lifecycle.after_new_parsed_answer.register(self._on_answer_generated)
        lifecycle.after_message_generation.register(self.finalize_round)

    async def _on_answer_generated(self, parsed_answer) -> None:
        token_usage = parsed_answer._answer.get_token_usage()
        if token_usage is not None:
            self._current_token_usage = token_usage

    async def finalize_round(self, _parsed_answer, _tool_calls) -> None:
        if self._current_token_usage is None:
            return
        self._last_valid_token_usage = self._current_token_usage
        self._update_cumulative_from(self._current_token_usage)
        self.is_dirty = False
        self._current_token_usage = None

    def _update_cumulative_from(self, token_usage: AnswerTokenUsage) -> None:
        self.recent_generations.append(token_usage)
        if len(self.recent_generations) > MAX_RECENT_GENERATIONS:
            self.recent_generations.pop(0)
        if self.cumulative_token_usage is None:
            self.cumulative_token_usage = {
                "input_tokens": token_usage.input_tokens,
                "output_tokens": token_usage.output_tokens,
                "total_tokens": token_usage.total_tokens,
                "cached_input_tokens": (
                    token_usage.cached_input_tokens
                    if token_usage.cached_input_tokens is not None
                    else (token_usage.estimated_cached_input_tokens or 0)
                ),
                "cache_creation_input_tokens": (
                    token_usage.cache_creation_input_tokens
                    if token_usage.cache_creation_input_tokens
                    else 0
                ),
                "message_count": 1,
                "cache_miss_count": 0,
            }
        else:
            self.cumulative_token_usage["input_tokens"] += token_usage.input_tokens
            self.cumulative_token_usage["output_tokens"] += token_usage.output_tokens
            self.cumulative_token_usage["total_tokens"] += token_usage.total_tokens
            self.cumulative_token_usage["cached_input_tokens"] += (
                token_usage.cached_input_tokens
                if token_usage.cached_input_tokens is not None
                else (token_usage.estimated_cached_input_tokens or 0)
            )
            self.cumulative_token_usage["cache_creation_input_tokens"] += (
                token_usage.cache_creation_input_tokens or 0
            )
            self.cumulative_token_usage["message_count"] += 1
            if token_usage.cached_input_tokens is not None:
                self.explicit_cache_tokens = token_usage.cached_input_tokens

    def _format_token_number(self, number: int) -> str:
        """Format a large number with k, m, etc. suffixes."""
        if number < 1000:
            return str(number)
        elif number < 1_000_000:
            formatted = f"{number / 1000:.1f}k"
            if formatted.endswith(".0k"):
                return formatted[:-3] + "k"
            return formatted
        elif number < 1_000_000_000:
            formatted = f"{number / 1_000_000:.1f}m"
            if formatted.endswith(".0m"):
                return formatted[:-3] + "m"
            return formatted
        else:
            formatted = f"{number / 1_000_000_000:.1f}b"
            if formatted.endswith(".0b"):
                return formatted[:-3] + "b"
            return formatted

    def get_token_display_pieces(
        self, agent: Agent, current_answer_token: int, use_nerd_font: bool = False
    ) -> list[str]:
        if self.cumulative_token_usage is None:
            return []

        input_tokens = self.cumulative_token_usage["input_tokens"]
        output_tokens = self.cumulative_token_usage["output_tokens"]
        cached_input_tokens = self.cumulative_token_usage["cached_input_tokens"]
        _llm_name, llm_instance = agent.get_current_llm_info()

        if self._current_token_usage is not None:
            input_tokens += self._current_token_usage.input_tokens
            output_tokens += self._current_token_usage.output_tokens
            current_cache = (
                self._current_token_usage.cached_input_tokens
                if self._current_token_usage.cached_input_tokens is not None
                else (self._current_token_usage.estimated_cached_input_tokens or 0)
            )
            cached_input_tokens += current_cache

        token_limit = llm_instance.get_token_limit()

        msg_pieces = agent.orchestration.get_status_display_pieces(use_nerd_font)

        if use_nerd_font:
            cache_symbol = "\uf49b "
            in_symbol = "\uf063 "
            out_symbol = "\uf062 "
        else:
            cache_symbol = "↻ "
            in_symbol = "↓ "
            out_symbol = "↑ "

        display_text_pieces: list[str] = []

        display_text_pieces.extend(msg_pieces)
        if input_tokens > 0 and cached_input_tokens > 0:
            cache_percentage = int((cached_input_tokens / input_tokens) * 100)
            display_text_pieces.append(
                f"{in_symbol}{self._format_token_number(input_tokens)}(~{cache_percentage}% {cache_symbol})"
            )
        else:
            display_text_pieces.append(
                f"{in_symbol}{self._format_token_number(input_tokens)}"
            )

        display_text_pieces.append(
            f"{out_symbol}{self._format_token_number(output_tokens)}"
        )

        if token_limit and token_limit > 0:
            percentage = (current_answer_token / token_limit) * 100

            filled_bars = int(percentage / 10)
            empty_bars = 10 - filled_bars
            progress_bar = "█" * filled_bars + "▒" * empty_bars
            piece = f"{progress_bar} {percentage:.0f}%"
            if llm_instance.get_explicit_cache_info() is not None:
                piece += f" ({self.explicit_cache_tokens / token_limit * 100:.0f}% {cache_symbol})"
            display_text_pieces.append(piece)

        return display_text_pieces

    def serialize(self) -> dict:
        return {
            "cumulative_token_usage": (
                dict(self.cumulative_token_usage)
                if self.cumulative_token_usage
                else None
            ),
            "recent_generations": [g.model_dump() for g in self.recent_generations],
            "explicit_cache_tokens": self.explicit_cache_tokens,
            "is_dirty": self.is_dirty,
            "generation_count": self.generation_count,
            "_last_valid_token_usage": (
                self._last_valid_token_usage.model_dump()
                if self._last_valid_token_usage
                else None
            ),
        }

    def restore_from(self, data: dict) -> None:
        self.cumulative_token_usage = data.get("cumulative_token_usage")
        self.recent_generations = [
            AnswerTokenUsage(**g) for g in data.get("recent_generations", [])
        ]
        self.explicit_cache_tokens = data.get("explicit_cache_tokens", 0)
        self.is_dirty = data.get("is_dirty", False)
        self.generation_count = data.get("generation_count", 0)
        last_valid = data.get("_last_valid_token_usage")
        if last_valid is not None:
            self._last_valid_token_usage = AnswerTokenUsage(**last_valid)
