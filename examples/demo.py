import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from pydatalog import *

# Example program with facts and rules using ergonomic factories
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
for d in validate(prog):
    print(d)
