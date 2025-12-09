from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Union

@dataclass(frozen=True, slots=True)
class Variable:
    name: str

@dataclass(frozen=True, slots=True)
class Constant:
    value: str

@dataclass(frozen=True, slots=True)
class Atom:
    relation: str
    terms: Tuple[Term, ...] = ()

    @property
    def arity(self) -> int:
        return len(self.terms)


@dataclass(frozen=True, slots=True)
class Rule:
    head: Atom
    body: Tuple[Atom, ...] = ()


@dataclass(frozen=True, slots=True)
class Program:
    rules: Tuple[Rule, ...] = ()

    def __post_init__(self):
        arities: Dict[str, int] = {}
        for r in self.rules:
            atoms = (r.head, *r.body)
            for a in atoms:
                ar = a.arity
                prev = arities.get(a.relation)
                if prev is None:
                    arities[a.relation] = ar
                elif prev != ar:
                    raise ValueError(
                        f"arity mismatch for relation '{a.relation}': "
                        f"previously seen arity {prev}, now seen arity {ar} in atom '{a}' of rule '{r}'"
                    )

# Term is a union of concrete term node types
Term = Union[Variable, Constant]

# Ergonomic factories for strict construction

def atom(relation: str, *terms: Term) -> Atom:
    return Atom(relation=relation, terms=tuple(terms))


def rule(head: Atom, *body: Atom) -> Rule:
    return Rule(head=head, body=tuple(body))


def fact(head: Atom) -> Rule:
    return Rule(head=head, body=())


def program(*rules: Rule) -> Program:
    return Program(rules=tuple(rules))

