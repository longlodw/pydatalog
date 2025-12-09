# pydatalog

-----

## Table of Contents

- [Development Setup](#development-setup)
- [Quick start](#quick-start)
- [API](#api)
- [License](#license)

## Development Setup

This project uses [Hatch](https://hatch.pypa.io/latest/) for development and packaging.

Requires Python 3.10+.

1. Install Hatch:

```console
pip install hatch
```

2. Run tests:

```console
hatch run test
```

3. Build artifacts (sdist and wheel):

```console
hatch build
```

4. Run the demo:

```console
hatch run python examples/demo.py
```

## Quick start

Construct AST using simple dataclasses or ergonomic factories:

```python
from pydatalog import program, rule, fact, atom, Variable, Constant, print_program
from pydatalog.execution import RulesPlan
import sqlite3

# Define a program:
# edge(a, b).
# edge(b, c).
# path(X, Y) :- edge(X, Y).
# path(X, Z) :- edge(X, Y), path(Y, Z).
prog = program(
    fact(atom("edge", Constant("a"), Constant("b"))),
    fact(atom("edge", Constant("b"), Constant("c"))),
    rule(atom("path", Variable("X"), Variable("Y")), atom("edge", Variable("X"), Variable("Y"))),
    rule(
        atom("path", Variable("X"), Variable("Z")),
        atom("edge", Variable("X"), Variable("Y")),
        atom("path", Variable("Y"), Variable("Z")),
    ),
)

print(print_program(prog))

# Execute the program using SQLite as the storage engine
conn = sqlite3.connect(":memory:")
plan = RulesPlan(prog, idb_storage=conn, edb_storage=conn)
plan.execute()

# Query results
print("Paths:")
for result in plan.query("path"):
    print(result)
```

## API

### AST Nodes (`pydatalog.nodes`)
- `Program`, `Rule`, `Atom`
- `Variable`, `Constant`

### Helper Factories (`pydatalog`)
- `program(*rules)`
- `rule(head, *body)`
- `fact(head)`
- `atom(relation, *terms)`

### Execution (`pydatalog.execution`)
- `RulesPlan(program, idb_storage, edb_storage)`: creates an execution plan backed by `sqlite3.Connection` objects.
  - `execute()`: Runs the Datalog program logic.
  - `query(relation_name, *keys)`: Yields tuples satisfying the relation.

### Utilities
- `print_program(program)`: Returns a string representation of the program.

## License

`pydatalog` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
