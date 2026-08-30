"""Employee SQL statements with no HTTP or business-policy logic."""

import sqlite3
from collections.abc import Mapping


class EmployeeRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create(
        self,
        *,
        employee_number: str,
        name: str,
        sewing_line: str,
        timestamp: str,
    ) -> dict:
        cursor = self.connection.execute(
            """
            INSERT INTO employees (
                employee_number,
                name,
                sewing_line,
                is_active,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, 1, ?, ?)
            """,
            (employee_number, name, sewing_line, timestamp, timestamp),
        )
        return self.require_by_id(int(cursor.lastrowid))

    def find_by_id(self, employee_id: int) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM employees WHERE id = ?",
            (employee_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def require_by_id(self, employee_id: int) -> dict:
        record = self.find_by_id(employee_id)
        if record is None:
            raise LookupError(f"Employee {employee_id} was not found after database write")
        return record

    def find_by_number(self, employee_number: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM employees WHERE employee_number = ? COLLATE NOCASE",
            (employee_number,),
        ).fetchone()
        return dict(row) if row is not None else None

    def list(self, *, include_inactive: bool) -> list[dict]:
        if include_inactive:
            query = "SELECT * FROM employees ORDER BY name COLLATE NOCASE, id"
            parameters: tuple = ()
        else:
            query = (
                "SELECT * FROM employees WHERE is_active = ? "
                "ORDER BY name COLLATE NOCASE, id"
            )
            parameters = (1,)

        rows = self.connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def update(self, employee_id: int, changes: Mapping[str, object]) -> dict:
        allowed_columns = {"name", "sewing_line", "is_active", "updated_at"}
        unknown_columns = set(changes) - allowed_columns
        if unknown_columns:
            raise ValueError(f"Unsupported employee columns: {sorted(unknown_columns)}")
        if not changes:
            return self.require_by_id(employee_id)

        assignments = ", ".join(f"{column} = ?" for column in changes)
        parameters = [*changes.values(), employee_id]
        self.connection.execute(
            f"UPDATE employees SET {assignments} WHERE id = ?",
            parameters,
        )
        return self.require_by_id(employee_id)
