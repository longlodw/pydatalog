from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class Span:
    """Source code span.

    Positions are [start, end) in bytes or characters depending on the frontend.
    File identity can be a path or logical id. Spans are optional across the AST.
    """

    file: Optional[str]
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < 0 or self.end < self.start:
            raise ValueError("invalid span range")

    def merge(self, other: Optional[Span]) -> Span:
        if other is None:
            return self
        if self.file != other.file:
            return self
        return Span(self.file, min(self.start, other.start), max(self.end, other.end))

    def __str__(self) -> str:  # debug-friendly
        file = self.file or "<unknown>"
        return f"{file}:{self.start}-{self.end}"
