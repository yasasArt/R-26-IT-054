"""Small, explicit migration runner for the embedded SQLite database."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.db.connection import connect_database
from app.db.transaction import transaction


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql_file: Path


MIGRATIONS = (
    Migration(
        version=1,
        name="initial_garment_counter_schema",
        sql_file=Path(__file__).with_name("schema.sql"),
    ),
)


def _migration_table(connection: sqlite3.Connection) -> None:

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def _sql_statements(script: str) -> list[str]:

    statements: list[str] = []
    buffer: list[str] = []

    for line in script.splitlines():
        buffer.append(line)
        candidate = "\n".join(buffer).strip()
        if candidate and sqlite3.complete_statement(candidate):
            statements.append(candidate)
            buffer.clear()

    remaining = "\n".join(buffer).strip()
    if remaining:
        raise ValueError("Migration SQL contains an incomplete statement")

    return statements


def applied_versions(connection: sqlite3.Connection) -> set[int]:
    _migration_table(connection)
    rows = connection.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()
    return {int(row["version"]) for row in rows}


def current_schema_version(connection: sqlite3.Connection) -> int:
    versions = applied_versions(connection)
    return max(versions, default=0)


def apply_migrations(connection: sqlite3.Connection) -> int:

    _migration_table(connection)
    completed = applied_versions(connection)

    for migration in MIGRATIONS:
        if migration.version in completed:
            continue

        script = migration.sql_file.read_text(encoding="utf-8")
        statements = _sql_statements(script)

        with transaction(connection):
            for statement in statements:
                connection.execute(statement)

            connection.execute(
                """
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                """,
                (migration.version, migration.name),
            )
            connection.execute(f"PRAGMA user_version = {migration.version}")

        completed.add(migration.version)

    return max(completed, default=0)


def initialize_database(database_path: str | Path) -> int:

    connection = connect_database(database_path)
    try:
        return apply_migrations(connection)
    finally:
        connection.close()
