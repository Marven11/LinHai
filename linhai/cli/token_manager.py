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
        else:
            self.cumulative_token_usage["input_tokens"] += token_usage.input_tokens
            self.cumulative_token_usage["output_tokens"] += token_usage.output_tokens
            self.cumulative_token_usage["total_tokens"] += token_usage.total_tokens

    def get_token_display_text(
        self, agent: Agent, current_answer_token: int
    ) -> str:
        """获取token使用量显示文本"""
        if self.cumulative_token_usage is None:
            return "Token usage: Not available"

        input_tokens = self.cumulative_token_usage["input_tokens"]
        output_tokens = self.cumulative_token_usage["output_tokens"]
        
        # 如果当前有正在进行的token使用，累加
        if self.current_token_usage is not None:
            input_tokens += self.current_token_usage.input_tokens
            output_tokens += self.current_token_usage.output_tokens

        # 获取当前LLM的token限制
        llm_name, llm_instance = agent.get_current_llm_info()
        token_limit = llm_instance.get_token_limit()

        message_count = len(agent.message_processor.messages)
        display_text_pieces = [
            llm_name,
            f"{message_count} msgs",
            f"in {input_tokens:,}",
            f"out {output_tokens:,}",
        ]
        
        if token_limit and token_limit > 0:
            percentage = (current_answer_token / token_limit) * 100
            # 使用进度条样式显示百分比
            filled_bars = int(percentage / 10)  # 每10%一个实心方块
            empty_bars = 10 - filled_bars
            progress_bar = "█" * filled_bars + "▒" * empty_bars
            display_text_pieces.append(
                f"{progress_bar} {percentage:.0f}% of {token_limit:,}"
            )

        return " | ".join(display_text_pieces)