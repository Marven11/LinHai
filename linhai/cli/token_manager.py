"""Token management logic for CLI."""

from typing import Dict, Optional
from linhai.llm import AnswerTokenUsage
from linhai.agent import Agent


class TokenManager:
    """Manager for token usage tracking and display."""

    def __init__(self):
        self.current_token_usage: Optional[AnswerTokenUsage] = None
        self.cumulative_token_usage: Optional[Dict[str, int]] = None

    def update_cumulative_usage(self, token_usage: AnswerTokenUsage) -> None:
        """更新累计token使用量"""
        if self.cumulative_token_usage is None:
            self.cumulative_token_usage = token_usage.model_dump()
            # 确保cached_input_tokens字段存在
            if "cached_input_tokens" not in self.cumulative_token_usage:
                self.cumulative_token_usage["cached_input_tokens"] = token_usage.cached_input_tokens or 0
        else:
            self.cumulative_token_usage["input_tokens"] += token_usage.input_tokens
            self.cumulative_token_usage["output_tokens"] += token_usage.output_tokens
            self.cumulative_token_usage["total_tokens"] += token_usage.total_tokens
            # 处理cached_input_tokens，如果为None则视为0
            current_cache = token_usage.cached_input_tokens or 0
            existing_cache = self.cumulative_token_usage["cached_input_tokens"]
            self.cumulative_token_usage["cached_input_tokens"] = existing_cache + current_cache

    def _format_token_number(self, number: int) -> str:
        """Format a large number with k, m, etc. suffixes."""
        if number < 1000:
            return str(number)
        elif number < 1_000_000:
            formatted = f"{number / 1000:.1f}k"
            # Remove trailing .0 if present
            if formatted.endswith('.0k'):
                return formatted[:-3] + 'k'
            return formatted
        elif number < 1_000_000_000:
            formatted = f"{number / 1_000_000:.1f}m"
            if formatted.endswith('.0m'):
                return formatted[:-3] + 'm'
            return formatted
        else:
            formatted = f"{number / 1_000_000_000:.1f}b"
            if formatted.endswith('.0b'):
                return formatted[:-3] + 'b'
            return formatted

    def get_token_display_text(
        self, agent: Agent, current_answer_token: int
    ) -> str:
        """获取token使用量显示文本"""
        if self.cumulative_token_usage is None:
            return "Token usage: Not available"

        input_tokens = self.cumulative_token_usage["input_tokens"]
        output_tokens = self.cumulative_token_usage["output_tokens"]
        cached_input_tokens = self.cumulative_token_usage["cached_input_tokens"]
        
        # 如果当前有正在进行的token使用，累加
        if self.current_token_usage is not None:
            input_tokens += self.current_token_usage.input_tokens
            output_tokens += self.current_token_usage.output_tokens
            # 直接访问cached_input_tokens属性，如果为None则视为0
            current_cache = self.current_token_usage.cached_input_tokens or 0
            cached_input_tokens += current_cache

        # 获取当前LLM的token限制
        _llm_name, llm_instance = agent.get_current_llm_info()
        token_limit = llm_instance.get_token_limit()

        message_count = len(agent.message_processor.messages)
        
        # 只在有输入token且缓存token大于0时才显示缓存比例
        display_text_pieces = [
            f"{message_count} msgs",
        ]
        
        if input_tokens > 0 and cached_input_tokens > 0:
            # 计算缓存比例
            cache_percentage = int((cached_input_tokens / input_tokens) * 100)
            display_text_pieces.append(f"in {self._format_token_number(input_tokens)} (~{cache_percentage}% cached)")
        else:
            display_text_pieces.append(f"in {self._format_token_number(input_tokens)}")
        
        display_text_pieces.append(f"out {self._format_token_number(output_tokens)}")
        
        if token_limit and token_limit > 0:
            percentage = (current_answer_token / token_limit) * 100
            # 使用进度条样式显示百分比
            filled_bars = int(percentage / 10)  # 每10%一个实心方块
            empty_bars = 10 - filled_bars
            progress_bar = "█" * filled_bars + "▒" * empty_bars
            display_text_pieces.append(
                f"{progress_bar} {percentage:.0f}% of {self._format_token_number(token_limit)}"
            )

        return " | ".join(display_text_pieces)