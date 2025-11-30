from pydatalog import Program, Rule, Atom, Variable, Constant, print_program


def test_print_facts_and_rules():
    prog = Program(rules=(
        Rule(Atom("edge", (Constant("a"), Constant("b"))), ()),
        Rule(Atom("edge", (Constant("b"), Constant("c"))), ()),
        Rule(Atom("path", (Variable("X"), Variable("Y"))), (
            Atom("edge", (Variable("X"), Variable("Y"))),
        )),
        Rule(Atom("path", (Variable("X"), Variable("Z"))), (
            Atom("edge", (Variable("X"), Variable("Y"))),
            Atom("path", (Variable("Y"), Variable("Z"))),
        )),
    ))

    out = print_program(prog)
    expected = "\n".join([
        "edge(a, b) :- .",
        "edge(b, c) :- .",
        "path(X, Y) :- edge(X, Y) .",
        "path(X, Z) :- edge(X, Y), path(Y, Z) .",
    ])
    assert out == expected


def test_print_zero_arity_atom():
    # A zero-arity atom prints as just the relation name
    prog = Program(rules=(Rule(Atom("start"), ()),))
    assert print_program(prog) == "start :- ."
