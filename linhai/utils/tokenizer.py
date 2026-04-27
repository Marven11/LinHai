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


def _bpe_encode_brute(ranks: dict[bytes, int], piece: bytes) -> list[int]:
    parts: list[bytes] = [bytes([b]) for b in piece]
    while len(parts) > 1:
        pairs = [
            (ranks.get(parts[i] + parts[i + 1], _MAX_RANK), i)
            for i in range(len(parts) - 1)
        ]
        min_rank, min_idx = min(pairs)
        if min_rank == _MAX_RANK:
            break
        parts[min_idx : min_idx + 2] = [parts[min_idx] + parts[min_idx + 1]]
    return [ranks[p] for p in parts]


def _bpe_encode(ranks: dict[bytes, int], piece: bytes) -> list[int]:
    if not piece:
        return []
    if len(piece) < 5:
        return _bpe_encode_brute(ranks, piece)
    n = len(piece)
    token_length = [1] * (n + 1)
    token_length[n] = 0
    prev_token = list(range(-1, n))

    def merge(i: int, j: int, handle_prev_token: bool) -> None:
        if handle_prev_token:
            prev_token[j + token_length[j]] = i
        token_length[i] += token_length[j]

    p = 0
    while True:
        p1 = p
        p2 = p1 + token_length[p1]
        if p2 >= n:
            break
        p3 = p2 + token_length[p2]
        p4 = p3 + token_length[p3]
        w12 = ranks.get(piece[p1 : p1 + token_length[p1] + token_length[p2]], _MAX_RANK)
        w23 = (
            ranks.get(piece[p2 : p2 + token_length[p2] + token_length[p3]], _MAX_RANK)
            if p3 < n
            else _MAX_RANK
        )
        w34 = (
            ranks.get(piece[p3 : p3 + token_length[p3] + token_length[p4]], _MAX_RANK)
            if p3 < n
            else _MAX_RANK
        )

        if p == 0 and w12 != _MAX_RANK and w12 <= w23:
            merge(p1, p2, handle_prev_token=True)
        elif p3 < n and w12 > w23 and w23 <= w34 and w23 != _MAX_RANK:
            merge(p2, p3, handle_prev_token=True)
            if p > 0:
                p = prev_token[p]
            if p > 0:
                p = prev_token[p]
        elif p4 + token_length[p4] == n:
            if p4 < n and w34 < w23:
                merge(p3, p4, handle_prev_token=False)
                if p > 0:
                    p = prev_token[p]
            else:
                break
        else:
            p = p2

    tokens: list[int] = []
    pos = 0
    while pos < n:
        tokens.append(ranks[piece[pos : pos + token_length[pos]]])
        pos += token_length[pos]
    return tokens


class EstimatedTokenizer:
    def __init__(self, ranks: dict[bytes, int]) -> None:
        self._ranks = ranks
        self._decoder = {v: k for k, v in ranks.items()}

    def encode(self, text: str, disallowed_special: tuple[str, ...] = ()) -> list[int]:
        return _bpe_encode(self._ranks, text.encode("utf-8"))

    def decode(self, tokens: list[int]) -> str:
        return b"".join(self._decoder[t] for t in tokens).decode(
            "utf-8", errors="replace"
        )


_tokenizer: EstimatedTokenizer | None = None


def get_cl100k_base_tokenizer() -> EstimatedTokenizer:
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = EstimatedTokenizer(_load_ranks())
    return _tokenizer


@lru_cache(maxsize=1000)
def count_tokens(text: str) -> int:
    return len(get_cl100k_base_tokenizer().encode(text))
