import sqlite3


class SessionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_by_id(self, session_id: int) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM production_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def require_by_id(self, session_id: int) -> dict:
        record = self.find_by_id(session_id)
        if record is None:
            raise LookupError(f"Session {session_id} was not found after database write")
        return record

    def find_active(self) -> dict | None:
        row = self.connection.execute(
            """
            SELECT * FROM production_sessions
            WHERE status = 'ACTIVE'
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row is not None else None

    def find_active_for_employee(self, employee_id: int) -> dict | None:
        row = self.connection.execute(
            """
            SELECT * FROM production_sessions
            WHERE employee_id = ? AND status = 'ACTIVE'
            LIMIT 1
            """,
            (employee_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def list(self) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT * FROM production_sessions
            ORDER BY started_at DESC, id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def create(
        self,
        *,
        employee: dict,
        configuration: dict,
        target_pieces: int,
        session_mode: str,
        timestamp: str,
    ) -> dict:
        cursor = self.connection.execute(
            """
            INSERT INTO production_sessions (
                employee_id,
                employee_number_snapshot,
                employee_name_snapshot,
                sewing_line_snapshot,
                target_pieces,
                session_mode,
                status,
                operator_mode,
                camera_index_snapshot,
                camera_label_snapshot,
                controller_device_id_snapshot,
                controller_name_snapshot,
                total_pieces,
                started_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', 'NORMAL', ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                employee["id"],
                employee["employee_number"],
                employee["name"],
                employee["sewing_line"],
                target_pieces,
                session_mode,
                configuration["camera_index"],
                configuration["camera_label"],
                configuration["controller_device_id"],
                configuration["controller_name"],
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        return self.require_by_id(int(cursor.lastrowid)) # type: ignore

    def complete_active(self, session_id: int, timestamp: str) -> dict | None:
        cursor = self.connection.execute(
            """
            UPDATE production_sessions
            SET status = 'COMPLETED', ended_at = ?, updated_at = ?
            WHERE id = ? AND status = 'ACTIVE'
            """,
            (timestamp, timestamp, session_id),
        )
        if cursor.rowcount != 1:
            return None
        return self.require_by_id(session_id)

    def set_first_sewing_started_if_missing(
        self,
        session_id: int,
        timestamp: str,
    ) -> dict:
        """Latch the first sewing timestamp once; later detector flicker cannot reset it."""

        self.connection.execute(
            """
            UPDATE production_sessions
            SET first_sewing_started_at = ?, updated_at = ?
            WHERE id = ? AND first_sewing_started_at IS NULL
            """,
            (timestamp, timestamp, session_id),
        )
        return self.require_by_id(session_id)

    def update_production_summary(
        self,
        session_id: int,
        *,
        total_pieces: int,
        average_cycle_seconds: float | None,
        timestamp: str,
    ) -> dict:
        self.connection.execute(
            """
            UPDATE production_sessions
            SET total_pieces = ?, average_cycle_seconds = ?, updated_at = ?
            WHERE id = ?
            """,
            (total_pieces, average_cycle_seconds, timestamp, session_id),
        )
        return self.require_by_id(session_id)
