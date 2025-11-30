from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .diagnostics import Diagnostic, Severity
from .nodes import Program, Variable, Constant


@dataclass(frozen=True)
class ArityError:
    relation: str
    seen: Tuple[int, ...]


def validate(program: Program) -> List[Diagnostic]:
    diags: List[Diagnostic] = []
    diags.extend(check_variable_names(program))
    diags.extend(check_arity_consistency(program))
    return diags


def check_variable_names(program: Program) -> List[Diagnostic]:
    diags: List[Diagnostic] = []
    for r in program.rules:
        for a in (r.head, *r.body):
            for t in a.terms:
                match t:
                    case Variable():
                        if not t.name:
                            diags.append(Diagnostic(code="E100", message="variable name must be non-empty", span=t.span))
                        # Uppercase-first constraint
                        if not t.name[0].isupper():
                            diags.append(Diagnostic(code="E101", message=f"variable '{t.name}' must start with an uppercase letter", span=t.span))
                    case Constant():
                        # Constants are opaque strings; optionally warn on empty
                        if t.value == "":
                            diags.append(Diagnostic(code="W110", message="empty constant string", severity=Severity.WARNING, span=t.span))
    return diags


def check_arity_consistency(program: Program) -> List[Diagnostic]:
    diags: List[Diagnostic] = []
    arities: Dict[str, int] = {}
    for r in program.rules:
        atoms = (r.head, *r.body)
        for a in atoms:
            if not a.relation:
                diags.append(Diagnostic(code="E120", message="relation name must be non-empty", span=a.span))
                continue
            ar = a.arity
            prev = arities.get(a.relation)
            if prev is None:
                arities[a.relation] = ar
            elif prev != ar:
                diags.append(Diagnostic(
                    code="E121",
                    message=f"arity mismatch for relation '{a.relation}': expected {prev}, found {ar}",
                    span=a.span,
                ))
    return diags
