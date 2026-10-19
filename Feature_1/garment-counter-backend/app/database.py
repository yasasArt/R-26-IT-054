from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            sewing_line TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS device_configuration (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            camera_id TEXT,
            camera_label TEXT,
            camera_tested INTEGER NOT NULL DEFAULT 0 CHECK (camera_tested IN (0, 1)),
            camera_tested_at TEXT,
            iot_mode TEXT NOT NULL DEFAULT 'NOT_CONFIGURED'
                CHECK (iot_mode IN ('NOT_CONFIGURED', 'REAL', 'SIMULATED')),
            iot_device_name TEXT,
            iot_device_id TEXT,
            iot_connected INTEGER NOT NULL DEFAULT 0 CHECK (iot_connected IN (0, 1)),
            iot_notifications_active INTEGER NOT NULL DEFAULT 0
                CHECK (iot_notifications_active IN (0, 1)),
            simulation_approved INTEGER NOT NULL DEFAULT 0
                CHECK (simulation_approved IN (0, 1)),
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS production_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_code TEXT NOT NULL UNIQUE,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            employee_code TEXT NOT NULL,
            employee_name TEXT NOT NULL,
            sewing_line TEXT NOT NULL,
            workstation_id TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            camera_label TEXT NOT NULL,
            target_pieces INTEGER NOT NULL CHECK (target_pieces > 0),
            session_mode TEXT NOT NULL CHECK (session_mode IN ('PRODUCTION', 'VALIDATION')),
            status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED')),
            operator_mode TEXT NOT NULL DEFAULT 'NORMAL'
                CHECK (operator_mode IN ('NORMAL', 'REWORK', 'DOWNTIME')),
            simulated_iot INTEGER NOT NULL DEFAULT 0 CHECK (simulated_iot IN (0, 1)),
            total_pieces INTEGER NOT NULL DEFAULT 0 CHECK (total_pieces >= 0),
            average_cycle_seconds REAL,
            first_sewing_started_at TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS only_one_active_session
            ON production_sessions(status) WHERE status = 'ACTIVE';

        CREATE TABLE IF NOT EXISTS piece_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES production_sessions(id),
            piece_number INTEGER NOT NULL CHECK (piece_number > 0),
            cycle_seconds REAL NOT NULL CHECK (cycle_seconds >= 0),
            sewing_started_at TEXT,
            completed_at TEXT NOT NULL,
            state_from TEXT NOT NULL DEFAULT 'SEWING' CHECK (state_from = 'SEWING'),
            state_to TEXT NOT NULL DEFAULT 'IDLE_SETUP' CHECK (state_to = 'IDLE_SETUP'),
            confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
            event_source TEXT NOT NULL CHECK (event_source IN ('VISION', 'VALIDATION')),
            created_at TEXT NOT NULL,
            UNIQUE (session_id, piece_number)
        );

        CREATE TABLE IF NOT EXISTS iot_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES production_sessions(id),
            employee_id INTEGER REFERENCES employees(id),
            event_type TEXT NOT NULL
                CHECK (event_type IN ('REWORK', 'DOWNTIME', 'RESET', 'DISCONNECTED', 'RECONNECTED')),
            mode_before TEXT NOT NULL CHECK (mode_before IN ('NORMAL', 'REWORK', 'DOWNTIME')),
            mode_after TEXT NOT NULL CHECK (mode_after IN ('NORMAL', 'REWORK', 'DOWNTIME')),
            device_name TEXT,
            event_source TEXT NOT NULL CHECK (event_source IN ('HARDWARE', 'VALIDATION')),
            payload_json TEXT,
            occurred_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS piece_events_session_time
            ON piece_events(session_id, completed_at);
        CREATE INDEX IF NOT EXISTS iot_events_session_time
            ON iot_events(session_id, occurred_at);
        CREATE INDEX IF NOT EXISTS sessions_employee_start
            ON production_sessions(employee_id, started_at);
        """,
    ),
)


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI may enter a synchronous dependency, execute its endpoint, and
    # close the dependency on different AnyIO worker threads. Connections are
    # still request-owned; WAL plus BEGIN IMMEDIATE serialize competing writes.
    connection = sqlite3.connect(
        str(database_path),
        timeout=10,
        isolation_level=None,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    connection.execute("BEGIN IMMEDIATE")

    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )
        """
    )

    for version, statements in MIGRATIONS:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()

        if applied:
            continue

        connection.executescript(
            "BEGIN IMMEDIATE;\n"
            + statements
            + f"\nINSERT INTO schema_migrations(version) VALUES ({version});\nCOMMIT;"
        )
