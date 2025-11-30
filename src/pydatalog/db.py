import sqlite3
from typing import Iterator, Tuple

class Db:
    relation: str
    arity: int
    def __init__(self, conn: sqlite3.Connection, relation: str, arity: int) -> None:
        self._db_connection = conn
        self.arity = arity
        self.relation = relation
        self._create_table_if_not_exists(relation)
    def store(self, tuple_data: tuple) -> None:
        if len(tuple_data) != self.arity:
            raise ValueError(f"Tuple arity {len(tuple_data)} does not match expected arity {self.arity}")
        cursor = self._db_connection.cursor()
        placeholders = ', '.join(['?'] * self.arity)
        cursor.execute(f'''
            INSERT INTO {self.relation} VALUES ({placeholders})
        ''', tuple_data)
        self._db_connection.commit()

    def load(self, *keys: Tuple[int, str]) -> Iterator[Tuple[str, ...]]:
        cursor = self._db_connection.cursor()
        if not keys:
            cursor.execute(f'SELECT * FROM {self.relation}')
            for row in cursor:
                yield row
            return
        
        conditions = []
        values = []
        for index, value in keys:
            conditions.append(f'col{index} = ?')
            values.append(value)
        
        where_clause = ' AND '.join(conditions)
        query = f'SELECT * FROM {self.relation} WHERE {where_clause}'
        cursor.execute(query, values)
        for row in cursor:
            yield row

    def _create_table_if_not_exists(self, relation: str) -> None:
        cursor = self._db_connection.cursor()
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {relation} (
                {' ,'.join([f'col{i} TEXT' for i in range(self.arity)])}
            )
        ''')
        self._db_connection.commit()
