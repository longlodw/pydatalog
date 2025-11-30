from pydatalog import Program, Rule, Atom, Variable, Constant, validate


def codes(diags):
    return {d.code for d in diags}


def test_validate_variable_names_uppercase_first():
    prog = Program(rules=(
        Rule(Atom("p", (Variable("x"),)), ()),  # invalid: lowercase-first
        Rule(Atom("q", (Variable("X"),)), ()),  # valid
    ))
    diags = validate(prog)
    assert "E101" in codes(diags)


def test_validate_empty_constant_warning():
    prog = Program(rules=(
        Rule(Atom("p", (Constant("") ,)), ()),
    ))
    diags = validate(prog)
    assert "W110" in codes(diags)


def test_validate_arity_consistency():
    prog = Program(rules=(
        Rule(Atom("r", (Constant("a"),)), ()),
        Rule(Atom("r", (Constant("a"), Constant("b"))), ()),  # mismatch
    ))
    diags = validate(prog)
    assert "E121" in codes(diags)
