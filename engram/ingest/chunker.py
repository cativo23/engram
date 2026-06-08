"""Split file text into overlapping line-window chunks.

Line windows are language-agnostic and fast. The embedding model has an 8192-token
context, so 40-line windows never truncate. Line numbers are 1-indexed (to match
GitHub deep links). P2.5+ may upgrade to code-aware (tree-sitter) chunking.
"""

from dataclasses import dataclass


@dataclass
class Chunk:
    line_start: int  # 1-indexed, inclusive
    line_end: int    # 1-indexed, inclusive
    text: str


def chunk_text(content: str, lines_per_chunk: int, overlap: int) -> list[Chunk]:
    """Sliding window over lines. `overlap` lines repeat between adjacent chunks."""
    if not content.strip():
        return []
    lines = content.rstrip("\n").split("\n")
    n = len(lines)
    step = max(1, lines_per_chunk - overlap)
    chunks: list[Chunk] = []
    start = 0  # 0-indexed line offset
    while start < n:
        end = min(start + lines_per_chunk, n)  # exclusive
        text = "\n".join(lines[start:end])
        chunks.append(Chunk(line_start=start + 1, line_end=end, text=text))
        start += step
    return chunks
