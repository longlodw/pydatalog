from __future__ import annotations

from dataclasses import replace
from typing import Callable, Optional

from .nodes import Node, Program, Rule, Atom, Term


class Visitor:
    """Composition-based visitor using structural pattern matching.

    - Calls `node_cb` for Program/Rule/Atom (pre-order)
    - Optionally calls `term_cb` for terms found in Atom.terms when `visit_terms=True`
    """

    def __init__(
        self,
        node_cb: Callable[[Node], None],
        term_cb: Optional[Callable[[Term], None]] = None,
    ) -> None:
        self._node_cb = node_cb
        self._term_cb = term_cb

    def visit(self, node: Node) -> None:
        self._node_cb(node)
        match node:
            case Program(rules=rules):
                for r in rules:
                    self.visit(r)
            case Rule(head=head, body=body):
                self.visit(head)
                for a in body:
                    self.visit(a)
            case Atom(terms=terms):
                if self._term_cb is not None:
                    for t in terms:
                        self._term_cb(t)
                return

class Transformer:
    """Composition-based transformer using structural pattern matching.

    - Transforms Program/Rule/Atom children first (post-order)
    - Optionally transforms terms inside Atom.terms via `term_fn` when `transform_terms=True`
    """

    def __init__(
        self,
        node_fn: Callable[[Node], Node],
        term_fn: Optional[Callable[[Term], Term]] = None,
    ) -> None:
        self._node_fn = node_fn
        self._term_fn = term_fn

    def transform(self, node: Node) -> Node:  # type: ignore[override]
        match node:
            case Program(rules=rules):
                node = replace(node, rules=tuple(self.transform(r) for r in rules))
            case Rule(head=head, body=body):
                node = replace(
                    node,
                    head=self.transform(head),
                    body=tuple(self.transform(a) for a in body),
                )
            case Atom(terms=terms):
                if self._term_fn is not None:
                    node = replace(node, terms=tuple(self._term_fn(t) for t in terms))
                return self._node_fn(node)
        return self._node_fn(node)
