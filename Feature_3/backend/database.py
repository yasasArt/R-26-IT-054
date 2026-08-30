"""Cross-platform SQLite storage for the ThreadScan measurement backend."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Electron sets THREADSCAN_DATA_DIR to its writable user-data directory.
# During ordinary Python development, data is stored beside this file.
DATA_DIRECTORY = Path(
    os.getenv(
        "THREADSCAN_DATA_DIR",
        str(Path(__file__).resolve().parent / "data"),
    )
).expanduser().resolve()
DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIRECTORY / "garment_measurements.db"

GARMENT_TYPES = ("tshirt", "shirt", "trouser")
SIZES = ("XS", "S", "M", "L", "XL", "XXL", "3XL", "UNKNOWN")


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    """Return the columns already present in a SQLite table."""
    return {
        str(row["name"])
        for row in connection.execute(f'PRAGMA table_info("{table_name}")')
    }


def _migrate_production_orders(connection: sqlite3.Connection) -> None:
    """Upgrade databases created by pre-v3.1 order builds in place.

    Electron keeps its SQLite file in the application-data directory. Merely
    extracting a newer source ZIP does not replace that database, and `CREATE
    TABLE IF NOT EXISTS` cannot add the columns introduced by v3.1.
    """
    existing = _table_columns(connection, "production_orders")
    if not existing:
        return

    migrations = {
        "carried_counts_json": "TEXT NOT NULL DEFAULT '{}'",
        "baseline_counts_json": "TEXT NOT NULL DEFAULT '{}'",
        "measurement_session_id": "INTEGER",
        "active_started_at": "TEXT NOT NULL DEFAULT ''",
        "ended_at": "TEXT",
        "completed_at": "TEXT",
        "accumulated_minutes": "INTEGER NOT NULL DEFAULT 0",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, declaration in migrations.items():
        if column_name not in existing:
            connection.execute(
                f'ALTER TABLE production_orders ADD COLUMN "{column_name}" {declaration}'
            )

    columns = _table_columns(connection, "production_orders")
    if {"active_started_at", "started_at"}.issubset(columns):
        connection.execute(
            """
            UPDATE production_orders
            SET active_started_at = started_at
            WHERE active_started_at IS NULL OR active_started_at = ''
            """
        )
    if {"updated_at", "created_at"}.issubset(columns):
        connection.execute(
            """
            UPDATE production_orders
            SET updated_at = created_at
            WHERE updated_at IS NULL OR updated_at = ''
            """
        )


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS counting_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS garment_measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                garment_type TEXT NOT NULL,
                size TEXT NOT NULL,
                width_cm REAL NOT NULL,
                length_cm REAL NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES counting_sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_measurements_session
            ON garment_measurements(session_id);

            CREATE INDEX IF NOT EXISTS idx_measurements_created
            ON garment_measurements(created_at DESC);

            CREATE TABLE IF NOT EXISTS production_orders (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL COLLATE NOCASE UNIQUE,
                garment_type TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active', 'paused', 'completed')),
                schedule_json TEXT NOT NULL,
                packed_json TEXT NOT NULL,
                carried_counts_json TEXT NOT NULL,
                baseline_counts_json TEXT NOT NULL,
                measurement_session_id INTEGER,
                created_at TEXT NOT NULL,
                started_at TEXT NOT NULL,
                active_started_at TEXT NOT NULL,
                ended_at TEXT,
                completed_at TEXT,
                accumulated_minutes INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )

        _migrate_production_orders(connection)

        connection.executescript(
            """

            CREATE INDEX IF NOT EXISTS idx_production_orders_created
            ON production_orders(created_at DESC);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_single_active_order
            ON production_orders(status) WHERE status = 'active';

            CREATE TABLE IF NOT EXISTS production_order_counting_sessions (
                order_session_id TEXT NOT NULL,
                counting_session_id INTEGER NOT NULL,
                PRIMARY KEY(order_session_id, counting_session_id),
                FOREIGN KEY(order_session_id)
                    REFERENCES production_orders(id) ON DELETE CASCADE,
                FOREIGN KEY(counting_session_id)
                    REFERENCES counting_sessions(id) ON DELETE CASCADE
            );
            """
        )

        active = connection.execute(
            "SELECT id FROM counting_sessions WHERE is_active = 1 "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()

        if active is None:
            connection.execute(
                "INSERT INTO counting_sessions(started_at, is_active) "
                "VALUES (?, 1)",
                (utc_now(),),
            )


def active_session_id(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT id FROM counting_sessions WHERE is_active = 1 "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if row is None:
        cursor = connection.execute(
            "INSERT INTO counting_sessions(started_at, is_active) VALUES (?, 1)",
            (utc_now(),),
        )
        return int(cursor.lastrowid)

    return int(row["id"])


def row_to_record(row: sqlite3.Row) -> dict:
    return {
        "id": int(row["id"]),
        "session_id": int(row["session_id"]),
        "garment_type": str(row["garment_type"]),
        "size": str(row["size"]),
        "width_cm": float(row["width_cm"]),
        "length_cm": float(row["length_cm"]),
        "confidence": float(row["confidence"]),
        "created_at": str(row["created_at"]),
    }


def save_garment_measurement(
    *,
    garment_type: str,
    size: str,
    width_cm: float,
    length_cm: float,
    confidence: float,
) -> dict:
    with connect() as connection:
        session_id = active_session_id(connection)
        created_at = utc_now()
        cursor = connection.execute(
            """
            INSERT INTO garment_measurements(
                session_id, garment_type, size, width_cm,
                length_cm, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                garment_type,
                size,
                float(width_cm),
                float(length_cm),
                float(confidence),
                created_at,
            ),
        )

        return {
            "id": int(cursor.lastrowid),
            "session_id": session_id,
            "garment_type": garment_type,
            "size": size,
            "width_cm": float(width_cm),
            "length_cm": float(length_cm),
            "confidence": float(confidence),
            "created_at": created_at,
        }


def get_current_session_data(*, history_limit: int = 50) -> dict:
    counts = {
        garment_type: {size: 0 for size in SIZES}
        for garment_type in GARMENT_TYPES
    }

    with connect() as connection:
        session_id = active_session_id(connection)
        grouped = connection.execute(
            """
            SELECT garment_type, size, COUNT(*) AS item_count
            FROM garment_measurements
            WHERE session_id = ?
            GROUP BY garment_type, size
            """,
            (session_id,),
        ).fetchall()

        for row in grouped:
            garment_type = str(row["garment_type"])
            size = str(row["size"])
            if garment_type in counts and size in counts[garment_type]:
                counts[garment_type][size] = int(row["item_count"])

        history_rows = connection.execute(
            """
            SELECT * FROM garment_measurements
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, max(1, int(history_limit))),
        ).fetchall()

    return {
        "session_id": session_id,
        "counts": counts,
        "history": [row_to_record(row) for row in history_rows],
    }


def get_all_measurements(*, limit: int = 100) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM garment_measurements ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 5000)),),
        ).fetchall()
    return [row_to_record(row) for row in rows]


def start_new_session() -> int:
    with connect() as connection:
        connection.execute(
            "UPDATE counting_sessions SET is_active = 0, ended_at = ? "
            "WHERE is_active = 1",
            (utc_now(),),
        )
        cursor = connection.execute(
            "INSERT INTO counting_sessions(started_at, is_active) VALUES (?, 1)",
            (utc_now(),),
        )
        return int(cursor.lastrowid)


def _json_object(value: object, field_name: str) -> dict:
    """Decode one stored JSON object and fail clearly if the row is corrupt."""
    decoded = json.loads(str(value))
    if not isinstance(decoded, dict):
        raise ValueError(f"Stored {field_name} is not a JSON object.")
    return decoded


def order_row_to_record(row: sqlite3.Row) -> dict:
    """Convert a SQLite production-order row to the frontend contract."""
    record = {
        "id": str(row["id"]),
        "orderId": str(row["order_id"]),
        "garmentType": str(row["garment_type"]),
        "status": str(row["status"]),
        "schedule": _json_object(row["schedule_json"], "schedule"),
        "packed": _json_object(row["packed_json"], "packed"),
        "carriedCounts": _json_object(
            row["carried_counts_json"], "carriedCounts"
        ),
        "baselineCounts": _json_object(
            row["baseline_counts_json"], "baselineCounts"
        ),
        "createdAt": str(row["created_at"]),
        "startedAt": str(row["started_at"]),
        "activeStartedAt": str(row["active_started_at"]),
        "accumulatedMinutes": int(row["accumulated_minutes"]),
    }
    optional_fields = {
        "measurementSessionId": "measurement_session_id",
        "endedAt": "ended_at",
        "completedAt": "completed_at",
    }
    for output_name, column_name in optional_fields.items():
        value = row[column_name]
        if value is not None:
            record[output_name] = (
                int(value) if output_name == "measurementSessionId" else str(value)
            )
    return record


def get_production_orders() -> list[dict]:
    """Return every persisted order, newest first."""
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM production_orders ORDER BY created_at DESC"
        ).fetchall()
    return [order_row_to_record(row) for row in rows]


def save_production_order(order: dict) -> dict:
    """Insert or update one complete order/session snapshot atomically."""
    updated_at = utc_now()
    values = (
        str(order["id"]),
        str(order["orderId"]).strip(),
        str(order["garmentType"]).strip(),
        str(order["status"]),
        json.dumps(order["schedule"], separators=(",", ":")),
        json.dumps(order["packed"], separators=(",", ":")),
        json.dumps(order["carriedCounts"], separators=(",", ":")),
        json.dumps(order["baselineCounts"], separators=(",", ":")),
        order.get("measurementSessionId"),
        str(order["createdAt"]),
        str(order["startedAt"]),
        str(order["activeStartedAt"]),
        order.get("endedAt"),
        order.get("completedAt"),
        int(order.get("accumulatedMinutes", 0)),
        updated_at,
    )
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO production_orders(
                id, order_id, garment_type, status, schedule_json,
                packed_json, carried_counts_json, baseline_counts_json,
                measurement_session_id, created_at, started_at,
                active_started_at, ended_at, completed_at,
                accumulated_minutes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                order_id = excluded.order_id,
                garment_type = excluded.garment_type,
                status = excluded.status,
                schedule_json = excluded.schedule_json,
                packed_json = excluded.packed_json,
                carried_counts_json = excluded.carried_counts_json,
                baseline_counts_json = excluded.baseline_counts_json,
                measurement_session_id = excluded.measurement_session_id,
                created_at = excluded.created_at,
                started_at = excluded.started_at,
                active_started_at = excluded.active_started_at,
                ended_at = excluded.ended_at,
                completed_at = excluded.completed_at,
                accumulated_minutes = excluded.accumulated_minutes,
                updated_at = excluded.updated_at
            """,
            values,
        )
        measurement_session_id = order.get("measurementSessionId")
        if measurement_session_id is not None:
            connection.execute(
                """
                INSERT OR IGNORE INTO production_order_counting_sessions(
                    order_session_id, counting_session_id
                ) VALUES (?, ?)
                """,
                (str(order["id"]), int(measurement_session_id)),
            )
        row = connection.execute(
            "SELECT * FROM production_orders WHERE id = ?", (order["id"],)
        ).fetchone()
    if row is None:
        raise RuntimeError("The order was not saved.")
    return order_row_to_record(row)


def delete_production_order(session_id: str) -> dict:
    """Delete one non-active order and its linked measurement records."""
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM production_orders WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            raise KeyError(session_id)
        if str(row["status"]) == "active":
            raise ValueError("End or pause the active order before deleting it.")

        linked_rows = connection.execute(
            """
            SELECT counting_session_id
            FROM production_order_counting_sessions
            WHERE order_session_id = ?
            """,
            (session_id,),
        ).fetchall()
        linked_session_ids = {int(item["counting_session_id"]) for item in linked_rows}
        if row["measurement_session_id"] is not None:
            linked_session_ids.add(int(row["measurement_session_id"]))

        for measurement_session_id in linked_session_ids:
            connection.execute(
                "DELETE FROM garment_measurements WHERE session_id = ?",
                (measurement_session_id,),
            )
            counting_row = connection.execute(
                "SELECT is_active FROM counting_sessions WHERE id = ?",
                (measurement_session_id,),
            ).fetchone()
            if counting_row is not None and not int(counting_row["is_active"]):
                connection.execute(
                    "DELETE FROM counting_sessions WHERE id = ?",
                    (measurement_session_id,),
                )

        connection.execute(
            "DELETE FROM production_orders WHERE id = ?", (session_id,)
        )

    return {
        "deleted": True,
        "id": session_id,
        "orderId": str(row["order_id"]),
    }
