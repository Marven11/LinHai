from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

_MAX_RANK = 1145141919810


def _load_ranks() -> dict[bytes, int]:
    ranks: dict[bytes, int] = {}
    tiktoken_path = Path(__file__).parent.parent / "cl100k_base.tiktoken"
    for line in tiktoken_path.read_text().strip().splitlines():
        token_b64, weight_str = line.split(maxsplit=1)
        ranks[base64.b64decode(token_b64)] = int(weight_str)
    return ranks


def _bpe_encode(ranks: dict[bytes, int], piece: bytes) -> list[int]:
    if not piece:
        return []
    n = len(piece)
    token_length = [1] * (n + 1)
    token_length[n] = 0
    prev_token = list(range(-1, n))

    def merge(i: int, j: int) -> None:
        prev_token[j + token_length[j]] = i
        token_length[i] += token_length[j]

    while token_length[0] != n:
        p1 = 0
        p2 = p1 + token_length[p1]
        p3 = p2 + token_length[p2]
        b1 = piece[p1 : p1 + token_length[p1]]
        b2 = piece[p2 : p2 + token_length[p2]]
        b3 = piece[p3 : p3 + token_length[p3]]
        if b1 + b2 in ranks and ranks[b1 + b2] <= ranks.get(b2 + b3, _MAX_RANK):
            merge(p1, p2)
        else:
            break

    p = 0
    done = False
    while not done:
        p1 = p
        p2 = p1 + token_length[p1]
        p3 = p2 + token_length[p2]
        p4 = p3 + token_length[p3]
        b1 = piece[p1 : p1 + token_length[p1]]
        b2 = piece[p2 : p2 + token_length[p2]]
        b3 = piece[p3 : p3 + token_length[p3]]
        b4 = piece[p4 : p4 + token_length[p4]]
        if (
            b2 + b3 in ranks
            and ranks[b2 + b3] <= ranks.get(b1 + b2, _MAX_RANK)
            and ranks[b2 + b3] <= ranks.get(b3 + b4, _MAX_RANK)
        ):
            merge(p2, p3)
            if p > 0:
                p = prev_token[p]
            if p > 0:
                p = prev_token[p]
        else:
            p = p2
        if p4 + token_length[p4] == n:
            done = True

    tokens: list[int] = []
    pos = 0
    while pos < n:
        tokens.append(ranks[piece[pos : pos + token_length[pos]]])
        pos += token_length[pos]
    return tokens


class FakeTokenizer:
    def __init__(self, ranks: dict[bytes, int]) -> None:
        self._ranks = ranks
        self._decoder = {v: k for k, v in ranks.items()}

    def encode(self, text: str, disallowed_special: tuple[str, ...] = ()) -> list[int]:
        return _bpe_encode(self._ranks, text.encode("utf-8"))

    def decode(self, tokens: list[int]) -> str:
        return b"".join(self._decoder[t] for t in tokens).decode(
            "utf-8", errors="replace"
        )


_tokenizer: FakeTokenizer | None = None


def get_cl100k_base_tokenizer() -> FakeTokenizer:
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = FakeTokenizer(_load_ranks())
    return _tokenizer


@lru_cache(maxsize=1000)
def count_tokens(text: str) -> int:
    return len(get_cl100k_base_tokenizer().encode(text))
