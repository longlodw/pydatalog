from dataclasses import replace

from pydatalog import Program, Rule, Atom, Variable, Constant, Visitor, Transformer


def test_visitor_nodes_only_by_default_and_terms_when_enabled():
    prog = Program(rules=(
        Rule(Atom("p", (Variable("X"), Constant("a"))), ()),
        Rule(Atom("q", (Variable("Y"),)), (Atom("p", (Variable("Y"), Constant("b"))),)),
    ))

    kinds = []
    terms = []

    Visitor(lambda n: kinds.append(type(n).__name__)).visit(prog)
    assert any(k == "Atom" for k in kinds)
    assert any(k == "Rule" for k in kinds)
    assert any(k == "Program" for k in kinds)

    Visitor(lambda _: None, term_cb=lambda t: terms.append(type(t).__name__)).visit(prog)
    assert "Variable" in terms and "Constant" in terms


def test_transformer_can_rename_relations_and_transform_terms_optionally():
    prog = Program(rules=(
        Rule(Atom("p", (Variable("X"),)), (Atom("q", (Variable("X"),)),)),
    ))

    # Rename relation at node level
    out = Transformer(lambda n: replace(n, relation="p2") if isinstance(n, Atom) and n.relation == "p" else n).transform(prog)
    assert isinstance(out, Program)
    assert out.rules[0].head.relation == "p2"
    assert out.rules[0].body[0].relation == "q"

    # Transform term optionally
    out2 = Transformer(lambda n: n, term_fn=lambda t: Variable("Z") if isinstance(t, Variable) else t).transform(out)
    assert isinstance(out2, Program)
    head_terms = out2.rules[0].head.terms
    assert isinstance(head_terms[0], Variable) and head_terms[0].name == "Z"
