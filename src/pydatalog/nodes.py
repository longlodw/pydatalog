from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .spans import Span


@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    span: Optional[Span] = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Variable must have a name")


@dataclass(frozen=True, slots=True)
class Constant:
    value: str
    span: Optional[Span] = None


@dataclass(frozen=True, slots=True)
class Atom:
    relation: str
    terms: Tuple[Term, ...] = ()
    span: Optional[Span] = None

    def __post_init__(self) -> None:
        if not self.relation:
            raise ValueError("Atom must have a relation name")

    @property
    def arity(self) -> int:
        return len(self.terms)


@dataclass(frozen=True, slots=True)
class Rule:
    head: Atom
    body: Tuple[Atom, ...] = ()
    span: Optional[Span] = None


@dataclass(frozen=True, slots=True)
class Program:
    rules: Tuple[Rule, ...] = ()
    span: Optional[Span] = None


# Term is a union of concrete term node types
Term = Union[Variable, Constant]

# Node excludes terms (Variable/Constant)
Node = Union[Program, Rule, Atom]


# Ergonomic factories for strict construction

def atom(relation: str, *terms: Term, span: Optional[Span] = None) -> Atom:
    return Atom(relation=relation, terms=tuple(terms), span=span)


def rule(head: Atom, *body: Atom, span: Optional[Span] = None) -> Rule:
    return Rule(head=head, body=tuple(body), span=span)


def fact(head: Atom, span: Optional[Span] = None) -> Rule:
    return Rule(head=head, body=(), span=span)


def program(*rules: Rule, span: Optional[Span] = None) -> Program:
    return Program(rules=tuple(rules), span=span)
