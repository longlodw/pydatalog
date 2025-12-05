from pydatalog.execution import RulesPlan, _union
from pydatalog.nodes import Rule, Atom, Variable, Constant
from pydatalog.db import Db
import sqlite3


def test_simple_projection_from_edb():
    conn = sqlite3.connect(":memory:")
    q = Db(conn, "q", 2)
    q.store(("a", "b"))
    q.store(("a", "b"))  # duplicate in EDB
    rules = [
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (Atom("q", (Variable("X"), Variable("Y"))),)),
    ]
    plan = RulesPlan(rules, idb_storage=conn, edb_storage=conn)
    # query returns multiple rows handled via storage semantics
    assert list(set(plan.query("p"))) == [("a", "b")]
    conn.close()


def test_head_constant_projection():
    conn = sqlite3.connect(":memory:")
    k2 = Db(conn, "k2", 2)
    k2.store(("tag", "a"))
    k2.store(("tag", "b"))
    k2.store(("zz", "c"))
    rules = [
        Rule(Atom("s", (Constant("tag"), Variable("X"))), (Atom("k2", (Constant("tag"), Variable("X"))),)),
        # head with multiple bodies via an additional rule producing a different constant
        Rule(Atom("s", (Constant("tag2"), Variable("X"))), (Atom("k2", (Constant("zz"), Variable("X"))),)),
    ]
    plan = RulesPlan(rules, idb_storage=conn, edb_storage=conn)
    assert set(plan.query("s")) == {("tag", "a"), ("tag", "b"), ("tag2", "c")}
    assert list(plan.query("s", (0, "zz"))) == []
    conn.close()


def test_query_with_keys_filters():
    conn = sqlite3.connect(":memory:")
    q = Db(conn, "q", 2)
    q.store(("a", "b"))
    q.store(("c", "d"))
    q.store(("a", "b"))  # duplicate row
    rules = [
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (Atom("q", (Variable("X"), Variable("Y"))),)),
    ]
    plan = RulesPlan(rules, idb_storage=conn, edb_storage=conn)
    assert list(set(plan.query("p", (0, "a")))) == [("a", "b")]
    assert list(set(plan.query("p", (1, "d")))) == [("c", "d")]
    conn.close()


def test_three_body_join_rule():
    conn = sqlite3.connect(":memory:")
    a = Db(conn, "a", 2)
    b = Db(conn, "b", 2)
    c = Db(conn, "c", 2)
    a.store(("a", "b")); a.store(("a", "x"))
    b.store(("b", "c")); b.store(("x", "y"))
    c.store(("c", "d")); c.store(("y", "z"))
    rules = [
        Rule(Atom("r", (Variable("X"), Variable("Z"), Variable("W"))), (
            Atom("a", (Variable("X"), Variable("Y"))),
            Atom("b", (Variable("Y"), Variable("Z"))),
            Atom("c", (Variable("Z"), Variable("W"))),
        )),
    ]
    plan = RulesPlan(rules, idb_storage=conn, edb_storage=conn)
    rows = set(plan.query("r"))
    assert rows == {("a", "c", "d"), ("a", "y", "z")}
    # varying number of terms and multi-row query
    assert len(rows) == 2
    conn.close()


def test_recursive_path():
    conn = sqlite3.connect(":memory:")
    edge = Db(conn, "edge", 2)
    for e in [("a","b"),("b","c"),("c","d")]:
        edge.store(e)
    rules = [
        Rule(Atom("path", (Variable("X"), Variable("Y"))), (Atom("edge", (Variable("X"), Variable("Y"))),)),
        Rule(Atom("path", (Variable("X"), Variable("Z"))), (
            Atom("edge", (Variable("X"), Variable("Y"))),
            Atom("path", (Variable("Y"), Variable("Z"))),
        )),
    ]
    plan = RulesPlan(rules, idb_storage=conn, edb_storage=conn)
    paths = set(plan.query("path"))
    expected = {("a", "b"), ("b", "c"), ("c", "d"), ("a", "c"), ("b", "d"), ("a", "d")}
    assert expected.issubset(paths)
    # query returns multiple rows
    assert len(paths) >= 6
    conn.close()


def test_recursive_query_with_many_irrelevant_facts():
    conn = sqlite3.connect(":memory:")
    # Relevant relation for the recursive query
    edge = Db(conn, "edge", 2)
    # a small chain that should be discovered via recursion
    for e in [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]:
        edge.store(e)
    # Add irrelevant components in the same relation that don't involve 'a'
    for i in range(500):
        edge.store((f"u{i}", f"u{i+1}"))
    # Other EDB relations with facts not used by path
    noise = Db(conn, "noise", 2)
    for i in range(80):
        noise.store((f"n{i}", f"n{i % 10}"))
    other = Db(conn, "other", 1)
    for i in range(400):
        other.store((f"o{i}",))

    # Rules include recursion for path and some unrelated rules
    rules = [
        Rule(Atom("path", (Variable("X"), Variable("Y"))), (Atom("edge", (Variable("X"), Variable("Y"))),)),
        Rule(Atom("path", (Variable("X"), Variable("Z"))), (
            Atom("edge", (Variable("X"), Variable("Y"))),
            Atom("path", (Variable("Y"), Variable("Z"))),
        )),
        # Unrelated rule shouldn't affect path queries
        Rule(Atom("junk", (Variable("X"),)), (Atom("other", (Variable("X"),)),)),
    ]

    plan = RulesPlan(rules, idb_storage=conn, edb_storage=conn)

    # Query only the paths that start from 'a' to ensure filtering works
    rows = set(plan.query("path", (0, "a")))
    expected = {("a", "b"), ("a", "c"), ("a", "d"), ("a", "e")}
    assert rows == expected

    conn.close()

# ---- merged from test_execution_complex.py ----

def test_long_body_chain():
    conn = sqlite3.connect(":memory:")
    a = Db(conn, "a", 2)
    b = Db(conn, "b", 2)
    c = Db(conn, "c", 2)
    d = Db(conn, "d", 2)
    e = Db(conn, "e", 2)
    r = Db(conn, "r", 5)
    a.store(("n1", "n2"))
    b.store(("n2", "n3"))
    c.store(("n3", "n4"))
    d.store(("n4", "n5"))
    e.store(("n5", "n6"))
    rules = [
        Rule(Atom("r", (Variable("A"), Variable("B"), Variable("C"), Variable("D"), Variable("E"))), (
            Atom("a", (Variable("A"), Variable("B"))),
            Atom("b", (Variable("B"), Variable("C"))),
            Atom("c", (Variable("C"), Variable("D"))),
            Atom("d", (Variable("D"), Variable("E"))),
        )),
    ]
    plan = RulesPlan(rules, idb_storage=conn, edb_storage=conn)
    rows = set(plan.query("r"))
    assert rows == {("n1", "n2", "n3", "n4", "n5")}
    conn.close()


def test_head_multiple_rules_and_constants():
    conn = sqlite3.connect(":memory:")
    src = Db(conn, "src", 2)
    dst = Db(conn, "dst", 2)
    src.store(("alpha", "1"))
    src.store(("beta", "2"))
    rules = [
        Rule(Atom("dst", (Constant("tag"), Variable("X"))), (Atom("src", (Variable("Y"), Variable("X"))),)),
        Rule(Atom("dst", (Constant("tag"), Constant("3"))), ()),
    ]
    plan = RulesPlan(rules, idb_storage=conn, edb_storage=conn)
    plan.execute()
    rows = set(plan.query("dst"))
    assert {("tag", "1"), ("tag", "2"), ("tag", "3")} == rows
    conn.close()


def test_mutual_recursion_even_odd():
    conn = sqlite3.connect(":memory:")
    succ = Db(conn, "succ", 2)
    even = Db(conn, "even", 1)
    odd = Db(conn, "odd", 1)
    for i in range(0, 6):
        succ.store((str(i), str(i + 1)))
    rules = [
        Rule(Atom("even", (Constant("0"),)), ()),
        Rule(Atom("odd", (Variable("Y"),)), (
            Atom("succ", (Variable("X"), Variable("Y"))),
            Atom("even", (Variable("X"),)),
        )),
        Rule(Atom("even", (Variable("Y"),)), (
            Atom("succ", (Variable("X"), Variable("Y"))),
            Atom("odd", (Variable("X"),)),
        )),
    ]
    plan = RulesPlan(rules, idb_storage=conn, edb_storage=conn)
    plan.execute()
    evens = set(plan.query("even"))
    odds = set(plan.query("odd"))
    # Expect evens 0,2,4,6 and odds 1,3,5
    assert {("0",), ("2",), ("4",), ("6",)}.issuperset(evens)
    assert {("1",), ("3",), ("5",)}.issuperset(odds)
    conn.close()


def test_varying_arities_and_multi_row():
    conn = sqlite3.connect(":memory:")
    a1 = Db(conn, "a1", 1)
    a2 = Db(conn, "a2", 1)
    r2 = Db(conn, "r2", 2)
    a1.store(("x",))
    a1.store(("y",))
    a2.store(("z",))
    rules = [
        Rule(Atom("r2", (Variable("X"), Variable("Z"))), (
            Atom("a1", (Variable("X"),)),
            Atom("a2", (Variable("Z"),)),
        )),
    ]
    plan = RulesPlan(rules, idb_storage=conn, edb_storage=conn)
    rows = set(plan.query("r2"))
    assert rows == {("x", "z"), ("y", "z")}
    conn.close()

# ---- merged from test_execution_union.py ----

def test_union_disjoint_merges():
    left = {0: "a", 2: "c"}
    right = {1: "b"}
    result = _union(left, right)
    assert result == {0: "a", 1: "b", 2: "c"}


def test_union_overlapping_same_values_keeps():
    left = {0: "a", 1: "b"}
    right = {1: "b", 2: "c"}
    result = _union(left, right)
    assert result == {0: "a", 1: "b", 2: "c"}


def test_union_conflict_returns_none():
    left = {0: "a", 1: "b"}
    right = {1: "x", 2: "c"}
    result = _union(left, right)
    assert result is None

if __name__ == "__main__":
    print("Running tests...")
    test_simple_projection_from_edb()
    test_head_constant_projection()
    test_query_with_keys_filters()
    test_three_body_join_rule()
    test_recursive_path()
    test_recursive_query_with_many_irrelevant_facts()
    test_long_body_chain()
    test_head_multiple_rules_and_constants()
    test_mutual_recursion_even_odd()
    test_varying_arities_and_multi_row()
    test_union_disjoint_merges()
    test_union_overlapping_same_values_keeps()
    test_union_conflict_returns_none()
