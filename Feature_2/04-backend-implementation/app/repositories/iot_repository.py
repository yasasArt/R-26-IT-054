"""IoT/operator-event SQL statements."""

import sqlite3


class IoTRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_by_event_key(self, session_id: int, event_key: str) -> dict | None:
        row = self.connection.execute(
            """
            SELECT * FROM iot_events
            WHERE session_id = ? AND event_key = ?
            """,
            (session_id, event_key),
        ).fetchone()
        return dict(row) if row is not None else None

    def find_by_id(self, event_id: int) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM iot_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def latest_for_session(self, session_id: int) -> dict | None:
        row = self.connection.execute(
            """
            SELECT * FROM iot_events
            WHERE session_id = ?
            ORDER BY occurred_at DESC, id DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def previous_for_event(self, event: dict) -> dict | None:
        row = self.connection.execute(
            """
            SELECT * FROM iot_events
            WHERE session_id = ?
              AND (occurred_at < ? OR (occurred_at = ? AND id < ?))
            ORDER BY occurred_at DESC, id DESC
            LIMIT 1
            """,
            (
                event["session_id"],
                event["occurred_at"],
                event["occurred_at"],
                event["id"],
            ),
        ).fetchone()
        return dict(row) if row is not None else None

    def list_for_session(self, session_id: int) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT * FROM iot_events
            WHERE session_id = ?
            ORDER BY occurred_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def insert(
        self,
        *,
        session_id: int,
        employee_id: int,
        event_key: str,
        event_type: str,
        mode_before: str,
        mode_after: str,
        device_name: str | None,
        device_id: str | None,
        event_source: str,
        occurred_at: str,
        created_at: str,
    ) -> dict:
        cursor = self.connection.execute(
            """
            INSERT INTO iot_events (
                session_id, employee_id, event_key, event_type,
                mode_before, mode_after, device_name, device_id,
                event_source, occurred_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                employee_id,
                event_key,
                event_type,
                mode_before,
                mode_after,
                device_name,
                device_id,
                event_source,
                occurred_at,
                created_at,
            ),
        )
        record = self.find_by_id(int(cursor.lastrowid))
        if record is None:
            raise LookupError("IoT event was not found after database write")
        return record

