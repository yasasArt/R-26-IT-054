import sqlite3


class PieceRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_by_event_key(self, session_id: int, event_key: str) -> dict | None:
        row = self.connection.execute(
            """
            SELECT * FROM piece_events
            WHERE session_id = ? AND event_key = ?
            """,
            (session_id, event_key),
        ).fetchone()
        return dict(row) if row is not None else None

    def list_for_session(self, session_id: int) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT * FROM piece_events
            WHERE session_id = ?
            ORDER BY piece_number ASC
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def latest_for_session(self, session_id: int) -> dict | None:
        row = self.connection.execute(
            """
            SELECT * FROM piece_events
            WHERE session_id = ?
            ORDER BY piece_number DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def next_piece_number(self, session_id: int) -> int:
        row = self.connection.execute(
            """
            SELECT COALESCE(MAX(piece_number), 0) + 1 AS next_number
            FROM piece_events
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        return int(row["next_number"])

    def insert(
        self,
        *,
        session_id: int,
        employee_id: int,
        piece_number: int,
        event_key: str,
        sewing_started_at: str,
        cycle_seconds: float,
        confidence: float | None,
        event_source: str,
        completed_at: str,
        created_at: str,
    ) -> dict:
        cursor = self.connection.execute(
            """
            INSERT INTO piece_events (
                session_id, employee_id, piece_number, event_key,
                sewing_started_at, cycle_seconds, confidence, event_source,
                completed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                employee_id,
                piece_number,
                event_key,
                sewing_started_at,
                cycle_seconds,
                confidence,
                event_source,
                completed_at,
                created_at,
            ),
        )
        row = self.connection.execute(
            "SELECT * FROM piece_events WHERE id = ?",
            (int(cursor.lastrowid),), # type: ignore
        ).fetchone()
        if row is None:
            raise LookupError("Piece event was not found after database write")
        return dict(row)

    def aggregate(self, session_id: int) -> dict:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS total_pieces,
                   AVG(cycle_seconds) AS average_cycle_seconds,
                   MAX(completed_at) AS latest_piece_at
            FROM piece_events
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        return dict(row)
