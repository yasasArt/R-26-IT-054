import sqlite3
from datetime import timedelta

from app.schemas.analytics import AnalyticsFilters


class AnalyticsRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_sessions(self, filters: AnalyticsFilters) -> list[dict]:
        conditions: list[str] = []
        parameters: list[object] = []

        if filters.session_id is not None:
            conditions.append("id = ?")
            parameters.append(filters.session_id)
        if filters.employee_id is not None:
            conditions.append("employee_id = ?")
            parameters.append(filters.employee_id)
        if filters.date_from is not None:
            conditions.append("started_at >= ?")
            parameters.append(f"{filters.date_from.isoformat()}T00:00:00.000Z")
        if filters.date_to is not None:
            exclusive_end = filters.date_to + timedelta(days=1)
            conditions.append("started_at < ?")
            parameters.append(f"{exclusive_end.isoformat()}T00:00:00.000Z")
        if filters.session_status is not None:
            conditions.append("status = ?")
            parameters.append(filters.session_status.value)
        if filters.session_mode is not None:
            conditions.append("session_mode = ?")
            parameters.append(filters.session_mode.value)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.connection.execute(
            f"""
            SELECT * FROM production_sessions
            {where_clause}
            ORDER BY started_at DESC, id DESC
            """,
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]

    def list_piece_events(self, session_id: int) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT * FROM piece_events
            WHERE session_id = ?
            ORDER BY piece_number ASC
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_iot_events(self, session_id: int) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT * FROM iot_events
            WHERE session_id = ?
            ORDER BY occurred_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def child_counts(self, session_id: int) -> tuple[int, int]:
        piece_count = self.connection.execute(
            "SELECT COUNT(*) FROM piece_events WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        iot_count = self.connection.execute(
            "SELECT COUNT(*) FROM iot_events WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        return int(piece_count), int(iot_count)

    def delete_piece_events(self, session_id: int) -> int:
        cursor = self.connection.execute(
            "DELETE FROM piece_events WHERE session_id = ?",
            (session_id,),
        )
        return cursor.rowcount

    def delete_iot_events(self, session_id: int) -> int:
        cursor = self.connection.execute(
            "DELETE FROM iot_events WHERE session_id = ?",
            (session_id,),
        )
        return cursor.rowcount

    def delete_session(self, session_id: int) -> int:
        cursor = self.connection.execute(
            "DELETE FROM production_sessions WHERE id = ?",
            (session_id,),
        )
        return cursor.rowcount

