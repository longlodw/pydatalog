from __future__ import annotations
from typing import Dict, Iterator, List, Optional, Tuple

from . import db
from . import nodes

class DbContext:
    idb_connection: db.sqlite3.Connection
    edb_connection: db.sqlite3.Connection

    def __init__(self, edb_conn: db.sqlite3.Connection, idb_conn: db.sqlite3.Connection) -> None:
        self.edb_connection = edb_conn
        self.idb_connection = idb_conn

    def query(self, rules: List[nodes.Rule], relation: str, *keys: Tuple[int, str]) -> Iterator[Tuple[str, ...]]:
        idb_relations, edb_relations = self._compile(rules)
        for rule in rules:
            And(idb_relations, edb_relations, rule)
        self._evaluate(edb_relations)
        if relation in idb_relations:
            cachable = idb_relations[relation]
        elif relation in edb_relations:
            cachable = edb_relations[relation]
        else:
            assert False, f"Relation {relation} not found in ProgramContext"
        yield from cachable[*keys]

    def _compile(self, rules: List[nodes.Rule]) -> Tuple[Dict[str, IdbCachable], Dict[str, EdbCachable]]:
        idb_relations: Dict[str, IdbCachable] = {}
        edb_relations: Dict[str, EdbCachable] = {}
        for rule in rules:
            head = rule.head.relation
            arity = len(rule.head.terms)
            if head not in idb_relations:
                idb_relations[head] = IdbCachable(self, head, arity)
        for rule in rules:
            for atom in rule.body:
                relation = atom.relation
                arity = len(atom.terms)
                if relation not in idb_relations and relation not in edb_relations:
                    edb_relations[relation] = EdbCachable(self, relation, arity)
        for rule in rules:
            And(idb_relations, edb_relations, rule)
        return idb_relations, edb_relations

    def _evaluate(self, edb_relations: Dict[str, EdbCachable]) -> None:
        # Semi-naive: seed once from EDB; push-based propagation handles closure
        for cachable in edb_relations.values():
            cachable(None)

class And:
    parent: IdbCachable
    def __init__(self, idb_relations: Dict[str, IdbCachable], edb_relations: Dict[str, EdbCachable], rule: nodes.Rule):
        self._bindings: List[List[int | str]] = []
        self._children: List[Cachable] = []
        self._parent_binding: List[int | str] = []
        head = rule.head.relation
        assert head in idb_relations
        parent = idb_relations[head]
        self.parent = parent
        next_binding = 0
        var_map: Dict[str, int] = {}
        # Build variable map across head and body terms
        for term in _rules_terms(rule):
            match term:
                case nodes.Variable(name=name):
                    if name not in var_map:
                        var_map[name] = next_binding
                        next_binding += 1
                case nodes.Constant():
                    pass
        # Map head terms to parent binding (indices/constants)
        for term in rule.head.terms:
            match term:
                case nodes.Variable(name=name):
                    self._parent_binding.append(var_map[name])
                case nodes.Constant(value=value):
                    self._parent_binding.append(value)
        # Setup children and per-child bindings (indices/constants)
        for k, atom in enumerate(rule.body):
            relation = atom.relation
            if relation in idb_relations:
                child = idb_relations[relation]
            elif relation in edb_relations:
                child = edb_relations[relation]
            else:
                assert False, f"Relation {relation} not found in ProgramContext"
            # Build bindings for this child atom
            child_binding: List[int | str] = []
            for t in atom.terms:
                match t:
                    case nodes.Variable(name=name):
                        child_binding.append(var_map[name])
                    case nodes.Constant(value=value):
                        child_binding.append(value)
            self._bindings.append(child_binding)
            child.parents.append((self, k))
            self._children.append(child)

    def __call__(self, idx: int, v: Tuple[str, ...]) -> None:
        bindings: Dict[int, str] = {}
        for k, b in enumerate(self._bindings[idx]):
            match b:
                case int(binding_index):
                    bindings[binding_index] = v[k]
                case str(constant):
                    if constant != v[k]:
                        return
        for result in self._propagate(idx, 0, bindings):
            self.parent(result)

    def _propagate(self, idx: int, cur: int, bindings: Dict[int, str]) -> Iterator[Tuple[str, ...]]:
        if cur == idx:
            cur += 1
        if cur == len(self._children):
            result = []
            for i in range(len(self._parent_binding)):
                match self._parent_binding[i]:
                    case int(binding_index):
                        result.append(bindings[binding_index])
                    case str(constant):
                        result.append(constant)
            yield tuple(result)
            return
        child = self._children[cur]
        key_pairs = tuple(
            (i, (b if isinstance(b, str) else bindings[b]))
            for i, b in enumerate(self._bindings[cur])
            if isinstance(b, str) or b in bindings
        )
        for cached in child[*key_pairs]:
            new_bindings = bindings.copy()
            match_success = True
            for i, b in enumerate(self._bindings[cur]):
                match b:
                    case int(binding_index):
                        new_bindings[binding_index] = cached[i]
                    case str(constant):
                        if constant != cached[i]:
                            match_success = False
                            break
            if not match_success:
                continue
            yield from self._propagate(idx, cur + 1, new_bindings)

class EdbCachable:
    parents: List[Tuple[And, int]]
    def __init__(self, pc: DbContext, name: str, arity: int) -> None:
        self._has_new_data_edb = True
        self._cache: db.Db = db.Db(pc.edb_connection, name, arity)
        self.parents = []
    def __getitem__(self, keys: Tuple[Tuple[int, str], ...]) -> Iterator[Tuple[str, ...]]:
        self._has_new_data_edb = False
        yield from self._cache.load(*keys)

    def __call__(self, v: Optional[Tuple[str, ...]]) -> None:
        match v:
            case None:
                if not self._has_new_data_edb:
                    return
                self._has_new_data_edb = False
                for item in self[()]:
                    self(item)
            case tuple():
                for parent, idx in self.parents:
                    parent(idx, v)

class IdbCachable:
    parents: List[Tuple[And, int]]
    def __init__(self, pc: DbContext, name: str, arity: int) -> None:
        self._cache: db.Db = db.Db(pc.idb_connection, name, arity)
        self.parents = []
    def __getitem__(self, keys: Tuple[Tuple[int, str], ...]) -> Iterator[Tuple[str, ...]]:
        yield from self._cache.load(*keys)

    def __call__(self, v: Tuple[str, ...]) -> None:
        # Check if tuple already exists by peeking first row
        existing_iter = self._cache.load(*( (i, v[i]) for i in range(len(v)) ))
        try:
            next(existing_iter)
            return  # already present
        except StopIteration:
            pass
        self._cache.store(v)
        for parent, idx in self.parents:
            parent(idx, v)

Cachable = IdbCachable | EdbCachable

def _rules_terms(rule: nodes.Rule) -> Iterator[nodes.Term]:
    for atom in rule.head.terms:
        yield atom
    for atom in rule.body:
        for term in atom.terms:
            yield term

