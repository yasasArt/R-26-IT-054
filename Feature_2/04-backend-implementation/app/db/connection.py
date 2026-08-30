import sqlite3
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_BUSY_TIMEOUT_MS = 5_000


def connect_database(database_path: str | Path) -> sqlite3.Connection:

    location = str(database_path)
    if location != ":memory:":
        path = Path(location).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        location = str(path)

    connection = sqlite3.connect(
        location,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        isolation_level=None,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {DEFAULT_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA synchronous = NORMAL")

    connection.execute("PRAGMA journal_mode = WAL")

    return connection


def close_database(connection: sqlite3.Connection) -> None:

    connection.close()
