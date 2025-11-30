# pydatalog

[![PyPI - Version](https://img.shields.io/pypi/v/pydatalog.svg)](https://pypi.org/project/pydatalog)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pydatalog.svg)](https://pypi.org/project/pydatalog)

-----

## Table of Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Visitors and transformers](#visitors-and-transformers)
- [API](#api)
- [License](#license)

## Installation

Requires Python 3.10+.

```console
pip install pydatalog
```

## Quick start

Construct AST using simple dataclasses or ergonomic factories:

```python
from pydatalog import Program, Rule, Atom, Variable, Constant

prog = Program(rules=(
    Rule(Atom("edge", (Constant("a"), Constant("b"))), ()),
    Rule(Atom("edge", (Constant("b"), Constant("c"))), ()),
    Rule(Atom("path", (Variable("X"), Variable("Y"))), (
        Atom("edge", (Variable("X"), Variable("Y"))),
    )),
))
```

Or use factories for strict, readable construction:

```python
from pydatalog import program, rule, fact, atom, Variable, Constant

prog = program(
    fact(atom("edge", Constant("a"), Constant("b"))),
    fact(atom("edge", Constant("b"), Constant("c"))),
    rule(atom("path", Variable("X"), Variable("Y")), atom("edge", Variable("X"), Variable("Y"))),
)
```

Print and validate:

```python
from pydatalog import print_program, validate

print(print_program(prog))
for d in validate(prog):
    print(d)
```

## Visitors and transformers

Nodes are a union: `Node = Program | Rule | Atom`. Terms are not nodes: `Term = Variable | Constant`.

- Visitor: pre-order traversal over nodes; optionally visit terms.
- Transformer: post-order transform; optionally transform terms.

```python
from dataclasses import replace
from pydatalog import Visitor, Transformer, Atom, Variable

# Collect node kinds
kinds = []
Visitor(lambda n: kinds.append(type(n).__name__)).visit(prog)

# Rename relations
renamed = Transformer(
    lambda n: replace(n, relation="edge2") if isinstance(n, Atom) and n.relation == "edge" else n
).transform(prog)

# Optionally transform terms
renamed_terms = Transformer(
    lambda n: n,
    term_fn=lambda t: Variable("Z") if isinstance(t, Variable) else t,
    transform_terms=True,
).transform(prog)
```

## API

- Nodes: `Program`, `Rule`, `Atom`
- Terms: `Variable`, `Constant`
- Factories: `program`, `rule`, `fact`, `atom`
- Utilities: `print_program`, `validate`, `Visitor`, `Transformer`

## License

`pydatalog` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
