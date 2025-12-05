from __future__ import annotations
import sqlite3
from typing import Dict, Iterator, List, Optional, Tuple, Set

from . import db
from . import nodes

"""
RulesPlan represents the execution plan for a set of Datalog-like rules.
"""
class RulesPlan:
    _heads: Dict[str, _RuleHeadPlan]
    _to_be_inserted: List[Tuple[str, Dict[int, str]]]

    def __init__(self, rules: List[nodes.Rule], idb_storage: sqlite3.Connection, edb_storage: sqlite3.Connection) -> None:
        self._heads = {}
        self._to_be_inserted = []
        idb_relations = set()
        # handling idb relations
        for rule in rules:
            head_relation = rule.head.relation
            if head_relation not in self._heads:
                self._heads[head_relation] = _RuleHeadPlan(db.Db(idb_storage, head_relation, rule.head.arity))
            if head_relation not in idb_relations:
                idb_relations.add(head_relation)
        # handling edb relations and building the plan
        for rule in rules:
            head_relation = rule.head.relation
            head_plan = self._heads[head_relation]
            # handle fact rules
            if len(rule.body) == 0:
                fact_values: Dict[int, str] = {}
                for k, term in enumerate(rule.head.terms):
                    assert isinstance(term, nodes.Constant)
                    fact_values[k] = term.value
                self._to_be_inserted.append((head_relation, fact_values))
                continue
            body_plan = _RuleBodyPlan(head_plan)
            head_plan._add_lower(body_plan)
            cur_cannonical_var = len(rule.head.terms)
            # cannonicalize head variables
            var_mapping: Dict[nodes.Variable, int] = {}
            for var_idx, term in enumerate(rule.head.terms):
                match term:
                    case nodes.Constant(value=value):
                        body_plan._head_spec[var_idx] = value
                    case nodes.Variable():
                        var_mapping[term] = var_idx
            # process body atoms
            for atom_idx, atom in enumerate(rule.body):
                body_relation = atom.relation
                if body_relation not in self._heads and body_relation not in idb_relations:
                    self._heads[body_relation] = _RuleHeadPlan(db.Db(edb_storage, body_relation, atom.arity))
                body_head_plan = self._heads[body_relation]
                body_plan._add_lower(body_head_plan)
                body_head_plan._add_upper(body_plan, atom_idx)
                for var_idx, term in enumerate(atom.terms):
                    match term:
                        case nodes.Constant(value=value):
                            body_plan._mapping_from_idx[(atom_idx, var_idx)] = value
                        case nodes.Variable():
                            if term in var_mapping:
                                body_plan._mapping_from_idx[(atom_idx, var_idx)] = var_mapping[term]
                            else:
                                var_mapping[term] = cur_cannonical_var
                                body_plan._mapping_from_idx[(atom_idx, var_idx)] = cur_cannonical_var
                                cur_cannonical_var += 1

    def query(self, relation: str, *keys: Tuple[int, str]) -> Iterator[Tuple[str, ...]]:
        if relation not in self._heads:
            return
        head_plan = self._heads[relation]
        mapping: Dict[int, str] = {idx: value for idx, value in keys}
        head_plan._propagate_down(mapping)
        yield from head_plan._storage.load(*keys)

    def execute(self) -> None:
        for relation, fact_values in self._to_be_inserted:
            head_plan = self._heads[relation]
            head_plan._propagate_up(fact_values)

"""
RuleHeadPlan represents the intermediate representation of a rule head in a Datalog-like system.
"""
class _RuleHeadPlan:
    _lower: List[_RuleBodyPlan]
    _upper: List[Tuple[_RuleBodyPlan, int]]
    _storage: db.Db
    _explored_mappings: Set[Tuple[Tuple[int, str], ...]]

    def __init__(self, storage: db.Db) -> None:
        self._lower = []
        self._upper = []
        self._storage = storage
        self._explored_mappings = set()

    def _add_lower(self, body: _RuleBodyPlan) -> None:
        self._lower.append(body)

    def _add_upper(self, body: _RuleBodyPlan, index: int) -> None:
        self._upper.append((body, index))

    def _propagate_up(self, mapping: Dict[int, str]) -> None:
        # Build the head row using constants and canonical variables
        head_row: List[str] = []
        for k in range(self._storage.arity):
            assert k in mapping
            head_row.append(mapping[k])
        if not self._storage.store(tuple(head_row)):
            return
        for body, idx in self._upper:
            body._propagate_up(idx, mapping)

    def _propagate_down(self, mapping: Dict[int, str]) -> None:
        mapping_key = tuple(sorted(mapping.items()))
        if mapping_key in self._explored_mappings:
            return
        self._explored_mappings.add(mapping_key)
        if len(self._lower) == 0:
            for e in self._storage.load(*mapping.items()):
                current_mapping: Dict[int, str] = {(i): v for i, v in enumerate(e)}
                for upper, idx in self._upper:
                    upper._propagate_up(idx, current_mapping)
        for body in self._lower:
            body._propagate_down(mapping)

class _RuleBodyPlan:
    _lower: List[_RuleHeadPlan]
    _mapping_from_idx: Dict[Tuple[int, int], int | str]
    _upper: _RuleHeadPlan
    _head_spec: Dict[int, str]
    
    def __init__(self, upper: _RuleHeadPlan) -> None:
        self._lower = []
        self._mapping_from_idx = {}
        self._upper = upper
        self._head_spec = {}

    def _add_lower(self, head: _RuleHeadPlan) -> None:
        self._lower.append(head)

    def _from_lower_mapping(self, atom_idx: int, mapping: Dict[int, str]) -> Optional[Dict[int, str]]:
        result: Dict[int, str] = {}
        # Iterate expected positions for this atom
        for (a_idx, var_idx), expected_var in self._mapping_from_idx.items():
            if a_idx != atom_idx:
                continue
            match expected_var:
                case str() as const_val:
                    # If a constant is expected, ensure any provided lower/canonical mapping agrees
                    if var_idx in mapping and mapping[var_idx] != const_val:
                        return None
                    # constants don't contribute to canonical mapping
                case int() as canon_idx:
                    # Prefer lower var index value if present, else canonical mapping
                    if var_idx in mapping:
                        result[canon_idx] = mapping[var_idx]
                    elif canon_idx in mapping:
                        result[canon_idx] = mapping[canon_idx]
                    else:
                        # insufficient info to map
                        return None
        return result

    def _to_lower_mapping(self, atom_idx: int, mapping: Dict[int, str]) -> Dict[int, str]:
        result: Dict[int, str] = {}
        keys = filter(lambda k: k[0] == atom_idx, self._mapping_from_idx.keys())
        for key in keys:
            m = self._mapping_from_idx[key]
            match m:
                case str() as const_val:
                    result[key[1]] = const_val
                case int() as canon_idx:
                    if canon_idx in mapping:
                        result[key[1]] = mapping[canon_idx]
        return result

    def _propagate_up(self, atom_idx: int, mapping: Dict[int, str]) -> None:
        shared_mapping = self._from_lower_mapping(atom_idx, mapping)
        if shared_mapping is None:
            return
        for join_mapping in self._join(0, shared_mapping, atom_idx):
            combined_mapping = _union(join_mapping, self._head_spec)
            if combined_mapping is None:
                continue
            # Propagate only variable mappings upstream
            filtered_mapping = {k: v for k, v in combined_mapping.items()}
            self._upper._propagate_up(filtered_mapping)

    def _join(self, cur_idx: int, mapping: Dict[int, str], skip_idx: int) -> Iterator[Dict[int, str]]:
        if cur_idx >= len(self._lower):
            yield mapping
            return
        if cur_idx == skip_idx:
            yield from self._join(cur_idx + 1, mapping, skip_idx)
            return
        atom = self._lower[cur_idx]
        atom_mapping = self._to_lower_mapping(cur_idx, mapping)
        for e in atom._storage.load(*atom_mapping.items()):
            lower_mapping: Dict[int, str] = {i: v for i, v in enumerate(e)}
            converted_lower_mapping = self._from_lower_mapping(cur_idx, lower_mapping)
            if converted_lower_mapping is None:
                continue
            new_mapping = _union(mapping, converted_lower_mapping)
            if new_mapping is None:
                continue
            yield from self._join(cur_idx + 1, new_mapping, skip_idx)
        self._propagate_down(atom_mapping)

    def _propagate_down(self, mapping: Dict[int, str]) -> None:
        assert len(self._lower) > 0
        atom_mapping: Dict[int, str] = {}
        for atom_idx, atom in enumerate(self._lower):
            for var_idx in range(atom._storage.arity):
                key = (atom_idx, var_idx)
                assert key in self._mapping_from_idx
                var = self._mapping_from_idx[key]
                match var:
                    case str():
                        atom_mapping[var_idx] = var
                    case int() as v_idx:
                        if v_idx in mapping:
                            atom_mapping[var_idx] = mapping[v_idx]
        # Propagate down to the first atom only; others will be joined in _join
        self._lower[0]._propagate_down(atom_mapping)

def _union(l: Dict[int, str], r: Dict[int, str]) -> Optional[Dict[int, str]]:
    result = l | r
    for k, v in l.items():
        if k in r and r[k] != v:
            return None
    return result
