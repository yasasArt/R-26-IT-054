from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.time_utils import format_utc, parse_utc


def test_phase_two_reports_backend_ready_but_models_not_runtime_loaded(
    configured_client: TestClient,
) -> None:
    readiness = configured_client.get("/api/readiness").json()
    components = {component["id"]: component for component in readiness["components"]}
    assert components["backend"]["status"] == "ready"
    assert components["camera"]["status"] == "ready"
    assert components["garment_classifier"]["status"] == "attention"
    assert readiness["productionReady"] is False
    assert readiness["validationReady"] is True


def test_production_remains_blocked_without_real_models_and_iot(
    configured_client: TestClient, employee: dict
) -> None:
    response = configured_client.post(
        "/api/sessions",
        json={"employee_id": employee["id"], "target_pieces": 50, "session_mode": "PRODUCTION"},
    )
    assert response.status_code == 409
    assert "blockers" in response.json()["detail"]


def test_validation_requires_an_explicitly_approved_simulated_controller(
    configured_client: TestClient, employee: dict
) -> None:
    configured_client.put(
        "/api/device-configuration",
        json={
            "camera_id": "camera-01", "camera_label": "Overhead", "camera_tested": True,
            "iot_mode": "SIMULATED", "simulation_approved": False,
        },
    )
    response = configured_client.post(
        "/api/sessions",
        json={"employee_id": employee["id"], "target_pieces": 50, "session_mode": "VALIDATION"},
    )
    assert response.status_code == 409


def test_only_one_session_can_be_active(
    configured_client: TestClient, employee: dict, validation_session: dict
) -> None:
    response = configured_client.post(
        "/api/sessions",
        json={"employee_id": employee["id"], "target_pieces": 20, "session_mode": "VALIDATION"},
    )
    assert validation_session["status"] == "ACTIVE"
    assert response.status_code == 409


def test_first_piece_has_a_real_cycle_duration_and_appears_in_dashboard(
    configured_client: TestClient, validation_session: dict
) -> None:
    started = parse_utc(validation_session["started_at"]) + timedelta(seconds=4)
    completed = started + timedelta(seconds=18.75)
    response = configured_client.post(
        f"/api/sessions/{validation_session['id']}/pieces",
        json={
            "sewing_started_at": format_utc(started),
            "completed_at": format_utc(completed),
            "confidence": 0.97,
            "event_source": "VALIDATION",
        },
    )
    assert response.status_code == 201
    assert response.json()["piece_number"] == 1
    assert response.json()["cycle_seconds"] == 18.75

    dashboard = configured_client.get(f"/api/sessions/{validation_session['id']}/dashboard").json()
    assert dashboard["piece_events"][0]["cycle_seconds"] == 18.75
    assert dashboard["target_series"] == [
        {"piece_number": 0, "remaining_pieces": 12},
        {"piece_number": 1, "remaining_pieces": 11},
    ]


def test_second_piece_uses_the_previous_completion_as_cycle_reference(
    configured_client: TestClient, validation_session: dict
) -> None:
    started = parse_utc(validation_session["started_at"])

    for seconds in (12, 32):
        response = configured_client.post(
            f"/api/sessions/{validation_session['id']}/pieces",
            json={"completed_at": format_utc(started + timedelta(seconds=seconds)), "event_source": "VALIDATION"},
        )
        assert response.status_code == 201

    events = configured_client.get(f"/api/sessions/{validation_session['id']}/pieces").json()
    assert [event["cycle_seconds"] for event in events] == [12.0, 20.0]


def test_each_actual_sewing_start_excludes_idle_gaps_from_average_cycle_time(
    configured_client: TestClient, validation_session: dict
) -> None:
    session_started = parse_utc(validation_session["started_at"])

    for start_offset, completion_offset in ((4, 14), (40, 58), (130, 142)):
        response = configured_client.post(
            f"/api/sessions/{validation_session['id']}/pieces",
            json={
                "sewing_started_at": format_utc(
                    session_started + timedelta(seconds=start_offset)
                ),
                "completed_at": format_utc(
                    session_started + timedelta(seconds=completion_offset)
                ),
                "event_source": "VALIDATION",
            },
        )
        assert response.status_code == 201, response.text

    dashboard = configured_client.get(
        f"/api/sessions/{validation_session['id']}/dashboard"
    ).json()
    assert [event["cycle_seconds"] for event in dashboard["piece_events"]] == [
        10.0,
        18.0,
        12.0,
    ]
    assert dashboard["session"]["average_cycle_seconds"] == 13.333

    analytics = configured_client.get(
        f"/api/analytics?session_id={validation_session['id']}"
    ).json()
    assert analytics["summary"]["average_cycle_seconds"] == 13.333


def test_iot_button_events_are_persisted_and_pause_counting(
    configured_client: TestClient, validation_session: dict
) -> None:
    response = configured_client.post(
        "/api/iot-events",
        json={"session_id": validation_session["id"], "event_type": "REWORK", "event_source": "VALIDATION"},
    )
    assert response.status_code == 201
    assert response.json()["mode_before"] == "NORMAL"
    assert response.json()["mode_after"] == "REWORK"
    assert response.json()["employee_id"] == validation_session["employee_id"]

    blocked = configured_client.post(
        f"/api/sessions/{validation_session['id']}/pieces", json={"event_source": "VALIDATION"}
    )
    assert blocked.status_code == 409


def test_reset_returns_to_normal_without_resetting_garment_count(
    configured_client: TestClient, validation_session: dict
) -> None:
    configured_client.post(
        f"/api/sessions/{validation_session['id']}/pieces", json={"event_source": "VALIDATION"}
    )
    for event_type in ("DOWNTIME", "RESET"):
        response = configured_client.post(
            "/api/iot-events",
            json={"session_id": validation_session["id"], "event_type": event_type, "event_source": "VALIDATION"},
        )
        assert response.status_code == 201

    current = configured_client.get(f"/api/sessions/{validation_session['id']}").json()
    assert current["operator_mode"] == "NORMAL"
    assert current["total_pieces"] == 1


def test_entering_rework_cancels_an_unfinished_sewing_cycle(
    configured_client: TestClient, validation_session: dict
) -> None:
    response = configured_client.post(
        f"/api/sessions/{validation_session['id']}/sewing-start",
        json={"started_at": validation_session["started_at"]},
    )
    assert response.status_code == 200
    assert response.json()["first_sewing_started_at"] is not None

    configured_client.post(
        "/api/iot-events",
        json={"session_id": validation_session["id"], "event_type": "REWORK", "event_source": "VALIDATION"},
    )
    current = configured_client.get(f"/api/sessions/{validation_session['id']}").json()
    assert current["first_sewing_started_at"] is None


def test_disconnection_is_not_downtime_and_blocks_new_counts(
    configured_client: TestClient, validation_session: dict
) -> None:
    response = configured_client.post(
        "/api/iot-events",
        json={"session_id": validation_session["id"], "event_type": "DISCONNECTED", "event_source": "VALIDATION"},
    )
    assert response.status_code == 201
    assert response.json()["mode_after"] == "NORMAL"

    blocked = configured_client.post(
        f"/api/sessions/{validation_session['id']}/pieces", json={"event_source": "VALIDATION"}
    )
    assert blocked.status_code == 409

    configured_client.post(
        "/api/iot-events",
        json={"session_id": validation_session["id"], "event_type": "RECONNECTED", "event_source": "VALIDATION"},
    )
    recovered = configured_client.post(
        f"/api/sessions/{validation_session['id']}/pieces", json={"event_source": "VALIDATION"}
    )
    assert recovered.status_code == 201


def test_validation_session_rejects_unlabelled_vision_events(
    configured_client: TestClient, validation_session: dict
) -> None:
    response = configured_client.post(
        f"/api/sessions/{validation_session['id']}/pieces", json={"event_source": "VISION"}
    )
    assert response.status_code == 409


def test_controller_can_be_tested_without_creating_a_production_session(
    configured_client: TestClient,
) -> None:
    response = configured_client.post(
        "/api/iot-events",
        json={"event_type": "RESET", "event_source": "VALIDATION"},
    )

    assert response.status_code == 201
    assert response.json()["session_id"] is None
    assert response.json()["mode_after"] == "NORMAL"


def test_completing_a_session_preserves_counts_and_closes_active_slot(
    configured_client: TestClient, validation_session: dict
) -> None:
    configured_client.post(
        f"/api/sessions/{validation_session['id']}/pieces", json={"event_source": "VALIDATION"}
    )
    response = configured_client.post(f"/api/sessions/{validation_session['id']}/complete")
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["total_pieces"] == 1
    assert configured_client.get("/api/sessions/active").json() is None
