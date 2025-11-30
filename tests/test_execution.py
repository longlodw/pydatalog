import sqlite3

from pydatalog.execution import DbContext, _rules_terms
from pydatalog.nodes import Rule, Atom, Variable, Constant


def test_program_context_builds_relation_maps():
    rules = [
        Rule(Atom("p", (Variable("X"),)), (Atom("q", (Variable("X"),)),)),
        Rule(Atom("r", (Variable("Y"), Variable("Z"))), (Atom("s", (Variable("Y"),)),)),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    pc = DbContext(edb, idb)
    idb_relations, edb_relations = pc._compile(rules)

    assert set(idb_relations.keys()) == {"p", "r"}
    assert set(edb_relations.keys()) == {"q", "s"}

    edb.close()
    idb.close()


def test_rules_terms_yields_head_then_body_in_order():
    rule = Rule(
        Atom("p", (Variable("X"), Constant("a"))),
        (Atom("q", (Variable("X"), Constant("b"))),),
    )
    terms = list(_rules_terms(rule))
    kinds = [type(t).__name__ for t in terms]
    assert kinds == ["Variable", "Constant", "Variable", "Constant"]
    assert isinstance(terms[0], Variable) and terms[0].name == "X"
    assert isinstance(terms[1], Constant) and terms[1].value == "a"


essentially_same = lambda rows: list(rows)


def test_program_context_query_unknown_relation_raises():
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    pc = DbContext(edb, idb)
    try:
        _ = list(pc.query([], "missing"))
        assert False, "Expected AssertionError for unknown relation"
    except AssertionError:
        pass
    finally:
        edb.close()
        idb.close()


def test_recursive_with_mixed_constants():
    # path_to_d(X) :- edge(X,"d")
    # path_to_d(X) :- edge(X,Y), path_to_d(Y) with constant "d"
    rules = [
        Rule(Atom("path_to_d", (Variable("X"),)), (Atom("edge", (Variable("X"), Constant("d"))),)),
        Rule(Atom("path_to_d", (Variable("X"),)), (
            Atom("edge", (Variable("X"), Variable("Y"))),
            Atom("path_to_d", (Variable("Y"),)),
        )),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE edge (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO edge VALUES (?, ?)", [("a","b"),("b","c"),("c","d"),("x","d")])
    edb.commit()
    pc = DbContext(edb, idb)
    rows = set(pc.query(rules, "path_to_d"))
    # Should include a,b,c,x all reaching d
    assert rows == {("a",),("b",),("c",),("x",)}
    edb.close()
    idb.close()


def test_mutual_recursion_with_constants_filtering():
    # p(X) :- base(X,"ok")
    # q(X) :- p(X), base(X,"ok") (redundant constant condition)
    # p(X) :- q(X) mutual recursion; constants restrict propagation
    rules = [
        Rule(Atom("p", (Variable("X"),)), (Atom("base", (Variable("X"), Constant("ok"))),)),
        Rule(Atom("q", (Variable("X"),)), (
            Atom("p", (Variable("X"),)),
            Atom("base", (Variable("X"), Constant("ok"))),
        )),
        Rule(Atom("p", (Variable("X"),)), (Atom("q", (Variable("X"),)),)),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE base (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO base VALUES (?, ?)", [("a","ok"),("b","bad"),("c","ok")])
    edb.commit()
    pc = DbContext(edb, idb)
    p_rows = set(pc.query(rules, "p"))
    q_rows = set(pc.query(rules, "q"))
    expected = {("a",),("c",)}
    assert p_rows == expected
    assert q_rows == expected
    edb.close()
    idb.close()


def test_mutual_recursion_with_cross_constants():
    # p(X,Y) :- edge(X,Y), const(Y) ensures Y has flag "t"
    # q(X,Y) :- p(X,Y), edge(Y,Z), const(Z) propagate one step further if Z flagged
    # p(X,Y) :- q(X,Y) (cycle) retain only flagged paths
    rules = [
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (
            Atom("edge", (Variable("X"), Variable("Y"))),
            Atom("flag", (Variable("Y"), Constant("t"))),
        )),
        Rule(Atom("q", (Variable("X"), Variable("Y"))), (
            Atom("p", (Variable("X"), Variable("Y"))),
            Atom("edge", (Variable("Y"), Variable("Z"))),
            Atom("flag", (Variable("Z"), Constant("t"))),
        )),
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (Atom("q", (Variable("X"), Variable("Y"))),)),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE edge (col0 TEXT, col1 TEXT)")
    cur.execute("CREATE TABLE flag (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO edge VALUES (?, ?)", [("a","b"),("b","c"),("c","d"),("d","e")])
    # Flags only b,d (c not flagged so path via c must rely on d flagged further)
    cur.executemany("INSERT INTO flag VALUES (?, ?)", [("b","t"),("d","t")])
    edb.commit()
    pc = DbContext(edb, idb)
    p_rows = set(pc.query(rules, "p"))
    q_rows = set(pc.query(rules, "q"))
    # Initial p from edge(X,Y) where Y flagged -> (a,b) and (c,d)
    # q extends (a,b)->(a,c) only if c flagged (not), (c,d)->(c,e) only if e flagged (not)
    # So q empty; mutual recursion adds nothing new
    assert p_rows == {("a","b"),("c","d")}
    assert q_rows == set()
    edb.close()
    idb.close()


def test_simple_join_propagation():
    # p(X, Y) :- q(X, Y)
    rules = [
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (Atom("q", (Variable("X"), Variable("Y"))),)),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    # Pre-populate EDB relation q before ProgramContext
    cur = edb.cursor()
    cur.execute("CREATE TABLE q (col0 TEXT, col1 TEXT)")
    cur.execute("INSERT INTO q VALUES (?, ?)", ("a", "b"))
    edb.commit()
    pc = DbContext(edb, idb)
    assert list(pc.query(rules, "p")) == [("a", "b")]
    edb.close()
    idb.close()


def test_transitive_path_recursive_rules():
    # edge facts + path rules:
    # path(X,Y) :- edge(X,Y)
    # path(X,Z) :- edge(X,Y), path(Y,Z)
    rules = [
        Rule(Atom("path", (Variable("X"), Variable("Y"))), (Atom("edge", (Variable("X"), Variable("Y"))),)),
        Rule(Atom("path", (Variable("X"), Variable("Z"))), (
            Atom("edge", (Variable("X"), Variable("Y"))),
            Atom("path", (Variable("Y"), Variable("Z"))),
        )),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    # Pre-populate edge facts before ProgramContext
    cur = edb.cursor()
    cur.execute("CREATE TABLE edge (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO edge VALUES (?, ?)", [("a","b"),("b","c"),("c","d")])
    edb.commit()
    pc = DbContext(edb, idb)
    paths = set(pc.query(rules, "path"))
    expected = {("a", "b"), ("b", "c"), ("c", "d"), ("a", "c"), ("b", "d"), ("a", "d")}
    assert expected.issubset(paths)
    idb.close()
    edb.close()


def test_mutual_recursion_two_relations():
    # p(X,Y) :- edge(X,Y)
    # q(X,Y) :- p(X,Y)
    # p(X,Y) :- q(X,Y)   (mutual recursion p<->q)
    rules = [
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (Atom("edge", (Variable("X"), Variable("Y"))),)),
        Rule(Atom("q", (Variable("X"), Variable("Y"))), (Atom("p", (Variable("X"), Variable("Y"))),)),
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (Atom("q", (Variable("X"), Variable("Y"))),)),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE edge (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO edge VALUES (?, ?)", [("a","b"),("b","c")])
    edb.commit()
    pc = DbContext(edb, idb)
    p_rows = set(pc.query(rules, "p"))
    q_rows = set(pc.query(rules, "q"))
    expected = {("a","b"),("b","c")}
    assert p_rows == expected
    assert q_rows == expected
    edb.close()
    idb.close()


def test_mutual_recursion_three_cycle():
    # p :- edge
    # q :- p
    # r :- q
    # p :- r   (cycle p->q->r->p)
    rules = [
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (Atom("edge", (Variable("X"), Variable("Y"))),)),
        Rule(Atom("q", (Variable("X"), Variable("Y"))), (Atom("p", (Variable("X"), Variable("Y"))),)),
        Rule(Atom("r", (Variable("X"), Variable("Y"))), (Atom("q", (Variable("X"), Variable("Y"))),)),
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (Atom("r", (Variable("X"), Variable("Y"))),)),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE edge (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO edge VALUES (?, ?)", [("x","y"),("y","z")])
    edb.commit()
    pc = DbContext(edb, idb)
    expected = {("x","y"),("y","z")}
    assert set(pc.query(rules, "p")) == expected
    assert set(pc.query(rules, "q")) == expected
    assert set(pc.query(rules, "r")) == expected
    edb.close()
    idb.close()


def test_three_body_join_rule():
    # r(X,Z,W) :- a(X,Y), b(Y,Z), c(Z,W)
    rules = [
        Rule(Atom("r", (Variable("X"), Variable("Z"), Variable("W"))), (
            Atom("a", (Variable("X"), Variable("Y"))),
            Atom("b", (Variable("Y"), Variable("Z"))),
            Atom("c", (Variable("Z"), Variable("W"))),
        )),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE a (col0 TEXT, col1 TEXT)")
    cur.execute("CREATE TABLE b (col0 TEXT, col1 TEXT)")
    cur.execute("CREATE TABLE c (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO a VALUES (?, ?)", [("a","b"),("a","x")])
    cur.executemany("INSERT INTO b VALUES (?, ?)", [("b","c"),("x","y")])
    cur.executemany("INSERT INTO c VALUES (?, ?)", [("c","d"),("y","z")])
    edb.commit()
    pc = DbContext(edb, idb)
    rows = set(pc.query(rules, "r"))
    assert {("a","c","d"), ("a","y","z")} == rows
    edb.close()
    idb.close()


def test_out_of_order_variable_dependencies():
    # s(X,Z) :- c(Z,W), a(X,Y), b(Y,Z)
    rules = [
        Rule(Atom("s", (Variable("X"), Variable("Z"))), (
            Atom("c", (Variable("Z"), Variable("W"))),
            Atom("a", (Variable("X"), Variable("Y"))),
            Atom("b", (Variable("Y"), Variable("Z"))),
        )),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE a (col0 TEXT, col1 TEXT)")
    cur.execute("CREATE TABLE b (col0 TEXT, col1 TEXT)")
    cur.execute("CREATE TABLE c (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO a VALUES (?, ?)", [("a","b"),("a","x")])
    cur.executemany("INSERT INTO b VALUES (?, ?)", [("b","c"),("x","y")])
    cur.executemany("INSERT INTO c VALUES (?, ?)", [("c","d"),("y","z")])
    edb.commit()
    pc = DbContext(edb, idb)
    rows = set(pc.query(rules, "s"))
    assert {("a","c"), ("a","y")} == rows
    edb.close()
    idb.close()


def test_constants_with_out_of_order():
    # t(X) :- k1(X,"k"), k2("k", X)
    rules = [
        Rule(Atom("t", (Variable("X"),)), (
            Atom("k1", (Variable("X"), Constant("k"))),
            Atom("k2", (Constant("k"), Variable("X"))),
        )),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE k1 (col0 TEXT, col1 TEXT)")
    cur.execute("CREATE TABLE k2 (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO k1 VALUES (?, ?)", [("a","k"),("b","x")])
    cur.executemany("INSERT INTO k2 VALUES (?, ?)", [("k","a"),("k","c")])
    edb.commit()
    pc = DbContext(edb, idb)
    rows = set(pc.query(rules, "t"))
    assert rows == {("a",)}
    edb.close()
    idb.close()


def test_long_chain_out_of_order_four_body():
    # u(X,E) :- d(D,E), a(X,Y), b(Y,Z), c(Z,D)
    rules = [
        Rule(Atom("u", (Variable("X"), Variable("E"))), (
            Atom("d", (Variable("D"), Variable("E"))),
            Atom("a", (Variable("X"), Variable("Y"))),
            Atom("b", (Variable("Y"), Variable("Z"))),
            Atom("c", (Variable("Z"), Variable("D"))),
        )),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE a (col0 TEXT, col1 TEXT)")
    cur.execute("CREATE TABLE b (col0 TEXT, col1 TEXT)")
    cur.execute("CREATE TABLE c (col0 TEXT, col1 TEXT)")
    cur.execute("CREATE TABLE d (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO a VALUES (?, ?)", [("a","b")])
    cur.executemany("INSERT INTO b VALUES (?, ?)", [("b","c")])
    cur.executemany("INSERT INTO c VALUES (?, ?)", [("c","d")])
    cur.executemany("INSERT INTO d VALUES (?, ?)", [("d","e")])
    edb.commit()
    pc = DbContext(edb, idb)
    rows = set(pc.query(rules, "u"))
    assert rows == {("a","e")}
    edb.close()
    idb.close()


def test_constant_mismatch_no_results():
    # r(X) :- k1(X,"k"), k2("x", X)  (no k2 facts with "x")
    rules = [
        Rule(Atom("r", (Variable("X"),)), (
            Atom("k1", (Variable("X"), Constant("k"))),
            Atom("k2", (Constant("x"), Variable("X"))),
        )),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE k1 (col0 TEXT, col1 TEXT)")
    cur.execute("CREATE TABLE k2 (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO k1 VALUES (?, ?)", [("a","k"),("b","k")])
    # Only tag "k" exists in col0 for k2, so constant "x" won't match
    cur.executemany("INSERT INTO k2 VALUES (?, ?)", [("k","a"),("k","b")])
    edb.commit()
    pc = DbContext(edb, idb)
    assert set(pc.query(rules, "r")) == set()
    edb.close()
    idb.close()


def test_head_constants_projected_correctly():
    # s("tag", X) :- k2("tag", X)
    rules = [
        Rule(Atom("s", (Constant("tag"), Variable("X"))), (
            Atom("k2", (Constant("tag"), Variable("X"))),
        )),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE k2 (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO k2 VALUES (?, ?)", [("tag","a"),("tag","b"),("zz","c")])
    edb.commit()
    pc = DbContext(edb, idb)
    assert set(pc.query(rules, "s")) == {("tag","a"), ("tag","b")}
    edb.close()
    idb.close()


def test_empty_mutual_recursion_no_seed():
    # p(X) :- q(X)
    # q(X) :- p(X)
    rules = [
        Rule(Atom("p", (Variable("X"),)), (Atom("q", (Variable("X"),)),)),
        Rule(Atom("q", (Variable("X"),)), (Atom("p", (Variable("X"),)),)),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    pc = DbContext(edb, idb)
    assert list(pc.query(rules, "p")) == []
    assert list(pc.query(rules, "q")) == []
    edb.close()
    idb.close()


def test_query_with_keys_filters():
    # p(X,Y) :- q(X,Y); then filter by columns via keys
    rules = [
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (Atom("q", (Variable("X"), Variable("Y"))),)),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE q (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO q VALUES (?, ?)", [("a","b"),("c","d")])
    edb.commit()
    pc = DbContext(edb, idb)
    # Filter by first column == "a"
    assert list(pc.query(rules, "p", (0, "a"))) == [("a","b")]
    # Filter by second column == "d"
    assert list(pc.query(rules, "p", (1, "d"))) == [("c","d")]
    edb.close()
    idb.close()


def test_query_requires_constant_in_body():
    # r(X) :- e(X,"k"). Query r with specific constants
    rules = [
        Rule(Atom("r", (Variable("X"),)), (
            Atom("e", (Variable("X"), Constant("k"))),
        )),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE e (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO e VALUES (?, ?)", [("a","k"),("b","x")])
    edb.commit()
    pc = DbContext(edb, idb)
    # Unfiltered query yields only the tuple supported by constant "k"
    assert set(pc.query(rules, "r")) == {("a",)}
    # Query requiring X == "a" returns the tuple
    assert list(pc.query(rules, "r", (0, "a"))) == [("a",)]
    # Query requiring X == "b" returns empty (constant mismatch in rule body)
    assert list(pc.query(rules, "r", (0, "b"))) == []
    edb.close()
    idb.close()


def test_query_requires_head_constant_value():
    # s("tag", X) :- k2("tag", X). Query must require the head constant
    rules = [
        Rule(Atom("s", (Constant("tag"), Variable("X"))), (
            Atom("k2", (Constant("tag"), Variable("X"))),
        )),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE k2 (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO k2 VALUES (?, ?)", [("tag","a"),("tag","b"),("zz","c")])
    edb.commit()
    pc = DbContext(edb, idb)
    # Query explicitly requiring first column == "tag"
    assert set(pc.query(rules, "s", (0, "tag"))) == {("tag","a"), ("tag","b")}
    # Query requiring an impossible constant on the head position returns empty
    assert list(pc.query(rules, "s", (0, "zz"))) == []
    edb.close()
    idb.close()


def test_query_with_multiple_key_constraints():
    # p(X,Y) :- q(X,Y). Query with two key constraints
    rules = [
        Rule(Atom("p", (Variable("X"), Variable("Y"))), (Atom("q", (Variable("X"), Variable("Y"))),)),
    ]
    edb = sqlite3.connect(":memory:")
    idb = sqlite3.connect(":memory:")
    cur = edb.cursor()
    cur.execute("CREATE TABLE q (col0 TEXT, col1 TEXT)")
    cur.executemany("INSERT INTO q VALUES (?, ?)", [("a","b"),("a","c"),("x","y")])
    edb.commit()
    pc = DbContext(edb, idb)
    # Matching both constraints returns a single tuple
    assert list(pc.query(rules, "p", (0, "a"), (1, "b"))) == [("a","b")]
    # Second constraint mismatched yields empty
    assert list(pc.query(rules, "p", (0, "a"), (1, "z"))) == []
    edb.close()
    idb.close()
