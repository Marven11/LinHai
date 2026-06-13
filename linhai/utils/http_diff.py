from difflib import ndiff
from pathlib import Path


def _split_lines_by_80(text: str) -> list[str]:
    result: list[str] = []
    for line in text.splitlines():
        for i in range(0, len(line), 80):
            result.append(line[i : i + 80])
    return result


def http_diff(filepath1: str, filepath2: str) -> str:
    path1 = Path(filepath1)
    path2 = Path(filepath2)
    if not path1.is_absolute():
        raise ValueError(f"filepath1 must be absolute: {filepath1}")
    if not path2.is_absolute():
        raise ValueError(f"filepath2 must be absolute: {filepath2}")

    lines1 = _split_lines_by_80(path1.read_text(encoding="utf-8"))
    lines2 = _split_lines_by_80(path2.read_text(encoding="utf-8"))

    diff_lines = list(ndiff(lines1, lines2))
    diff_lines = [line for line in diff_lines if not line.startswith("  ")]

    return "\n".join(diff_lines)
