"""pydatalog: simplified Datalog AST and utilities."""

from .spans import Span
from .diagnostics import Diagnostic, Severity
from .nodes import (
    Node,
    Program,
    Rule,
    Atom,
    Term,
    Variable,
    Constant,
    atom,
    rule,
    fact,
    program,
)
from .visitors import Visitor, Transformer
from .printer import print_program
from .validation import validate
from .magic import magic_rewrite

__all__ = [
    "Span",
    "Diagnostic",
    "Severity",
    "Node",
    "Program",
    "Rule",
    "Atom",
    "Term",
    "Variable",
    "Constant",
    "atom",
    "rule",
    "fact",
    "program",
    "Visitor",
    "Transformer",
    "print_program",
    "validate",
    "magic_rewrite",
]
