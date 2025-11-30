from __future__ import annotations

from .nodes import Program, Rule, Atom, Term, Variable, Constant


def print_program(p: Program) -> str:
    return "\n".join(print_rule(r) for r in p.rules)


def print_rule(r: Rule) -> str:
    head = print_atom(r.head)
    if not r.body:
        return f"{head} :- ."
    body = ", ".join(print_atom(a) for a in r.body)
    return f"{head} :- {body} ."


def print_atom(a: Atom) -> str:
    if a.terms:
        args = ", ".join(print_term(t) for t in a.terms)
        return f"{a.relation}({args})"
    return a.relation


def print_term(t: Term) -> str:
    match t:
        case Variable():
            return t.name
        case Constant():
            return t.value

