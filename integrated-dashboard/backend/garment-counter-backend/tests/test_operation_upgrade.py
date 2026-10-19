from datetime import timedelta
from pathlib import Path

import pytest

from app.cycle_time import enrich_session_cycle_status
from app.database import MIGRATIONS, connect, migrate
from app.time_utils import format_utc, parse_utc


@pytest.mark.parametrize("legacy_version", [1, 2])
def test_upgrade_preserves_legacy_history_and_can_run_again(tmp_path: Path, legacy_version: int) -> None:
    connection = connect(tmp_path / "legacy.sqlite3")
    try:
        connection.executescript(MIGRATIONS[0][1])
        connection.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)")
        for version in range(1, legacy_version + 1):
            connection.execute("INSERT INTO schema_migrations VALUES (?)", (version,))
        connection.execute(
            "INSERT INTO employees VALUES (1, 'EMP-01', 'Original operator', 'Line A', 1, '2026-09-01', '2026-09-01')"
        )
        connection.execute(
            "INSERT INTO production_sessions (id, session_code, employee_id, employee_code, employee_name, "
            "sewing_line, workstation_id, camera_id, camera_label, target_pieces, session_mode, "
            "status, total_pieces, average_cycle_seconds, started_at, created_at) "
            "VALUES (1, 'LEGACY-01', 1, 'EMP-01', 'Original operator', 'Line A', 'WS-01', '0', "
            "'Camera', 10, 'VALIDATION', 'COMPLETED', 1, 12, '2026-09-01', '2026-09-01')"
        )
        connection.execute(
            "INSERT INTO piece_events (session_id, piece_number, cycle_seconds, completed_at, event_source, created_at) "
            "VALUES (1, 1, 12, '2026-09-01', 'VALIDATION', '2026-09-01')"
        )

        migrate(connection)
        migrate(connection)

        session = enrich_session_cycle_status(connection.execute("SELECT * FROM production_sessions").fetchone())
        assert session["session_code"] == "LEGACY-01"
        assert session["total_pieces"] == 1
        assert session["average_cycle_seconds"] == 12
        assert session["operation_type"] is None
        assert session["estimated_cycle_time_sec"] is None
        assert session["average_cycle_status"] == "NOT_CONFIGURED"
        assert connection.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 1
        assert connection.execute("SELECT cycle_seconds FROM piece_events").fetchone()[0] == 12
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 3
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_operation_filters_and_cycle_benchmarks(configured_client, validation_session) -> None:
    session_id = validation_session["id"]
    started = parse_utc(validation_session["started_at"])
    for elapsed in (20, 40.1):
        response = configured_client.post(
            f"/api/sessions/{session_id}/pieces",
            json={"completed_at": format_utc(started + timedelta(seconds=elapsed)), "event_source": "VALIDATION"},
        )
        assert response.status_code == 201

    payload = configured_client.get("/api/analytics?operation_type=COLLAR").json()
    assert payload["summary"]["within_estimate_count"] == 1
    assert payload["summary"]["over_estimate_count"] == 1
    assert payload["summary"]["cycle_compliance_percent"] == 50
    assert [event["cycle_status"] for event in payload["piece_events"]] == ["WITHIN_ESTIMATE", "OVER_ESTIMATE"]
    assert configured_client.get("/api/analytics?operation_type=POCKET").json()["sessions"] == []
