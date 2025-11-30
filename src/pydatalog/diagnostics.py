from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable, List, Optional, Tuple

from .spans import Span


class Severity(Enum):
    ERROR = auto()
    WARNING = auto()
    INFO = auto()


@dataclass(frozen=True, slots=True)
class Related:
    message: str
    span: Optional[Span]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    severity: Severity = Severity.ERROR
    span: Optional[Span] = None
    related: Tuple[Related, ...] = ()

    def with_related(self, *rels: Related) -> "Diagnostic":
        return Diagnostic(
            code=self.code,
            message=self.message,
            severity=self.severity,
            span=self.span,
            related=tuple(list(self.related) + list(rels)),
        )


def collect(diags: Iterable[Diagnostic]) -> List[Diagnostic]:
    return list(diags)


def format_diagnostic(d: Diagnostic) -> str:
    loc = f" at {d.span}" if d.span else ""
    lines = [f"{d.severity.name}: {d.code}{loc}: {d.message}"]
    for r in d.related:
        loc2 = f" at {r.span}" if r.span else ""
        lines.append(f"  note{loc2}: {r.message}")
    return "\n".join(lines)
