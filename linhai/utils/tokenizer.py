from functools import lru_cache
from pathlib import Path

import tiktoken
from tiktoken.load import load_tiktoken_bpe

_CL100K_BASE_PAT_STR = r"(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s"

_cl100k_base_tokenizer: tiktoken.Encoding | None = None


def get_cl100k_base_tokenizer() -> tiktoken.Encoding:
    global _cl100k_base_tokenizer
    if _cl100k_base_tokenizer is None:
        tiktoken_path = str(Path(__file__).parent.parent / "cl100k_base.tiktoken")
        ranks = load_tiktoken_bpe(tiktoken_path)
        _cl100k_base_tokenizer = tiktoken.Encoding(
            name="cl100k_base_local",
            pat_str=_CL100K_BASE_PAT_STR,
            mergeable_ranks=ranks,
            special_tokens={
                "<|endofprompt|>": 100276,
                "<|fim_prefix|>": 100258,
                "<|fim_middle|>": 100259,
                "<|fim_suffix|>": 100260,
                "<|endoftext|>": 100257,
            },
        )
    return _cl100k_base_tokenizer


@lru_cache(maxsize=1000)
def count_tokens(text: str) -> int:
    return len(get_cl100k_base_tokenizer().encode(text, disallowed_special=()))
