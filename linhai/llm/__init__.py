"""LLM模块包，提供OpenAI和Anthropic兼容的LLM实现。"""

from linhai.llm.openai_compatible import (
    OpenAi,
    OpenAiAnswer,
    MinimaxAnswer,
    OpenAIError,
)

__all__ = [
    "OpenAi",
    "OpenAiAnswer",
    "MinimaxAnswer",
    "OpenAIError",
]
