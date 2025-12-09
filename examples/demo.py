import sys, os
import sqlite3

# Adjust python path to include src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydatalog import program, fact, rule, atom, Constant, Variable, print_program
from pydatalog.execution import RulesPlan


def main():
    # Define a program with facts and recursive rules
    prog = program(
        fact(atom("edge", Constant("a"), Constant("b"))),
        fact(atom("edge", Constant("b"), Constant("c"))),
        rule(
            atom("path", Variable("X"), Variable("Y")),
            atom("edge", Variable("X"), Variable("Y")),
        ),
        rule(
            atom("path", Variable("X"), Variable("Z")),
            atom("edge", Variable("X"), Variable("Y")),
            atom("path", Variable("Y"), Variable("Z")),
        ),
    )

    print("--- Datalog Program ---")
    print(print_program(prog))

    # Execute the program using in-memory SQLite storage
    conn = sqlite3.connect(":memory:")
    plan = RulesPlan(prog, idb_storage=conn, edb_storage=conn)
    plan.execute()

    # Query results
    print("\n--- Query Results: path(X, Y) ---")
    results = list(plan.query("path"))
    for r in sorted(results):
        print(r)


if __name__ == "__main__":
    main()
