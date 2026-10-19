from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

import app.vision.runtime as vision_runtime
from app.config import Settings
from app.database import connect
from app.main import create_application


DEVICE_ID = "macos-private-controller-id-001"
DEVICE_NAME = "GarmentCounter-IoT"


def install_test_models(client: TestClient) -> None:
    client.app.state.vision_registry.install_models(object(), object())


def configure_real_controller(client: TestClient) -> dict:
    response = client.put(
        "/api/device-configuration",
        json={
            "camera_id": "0",
            "camera_label": "Factory sewing camera",
            "camera_tested": True,
            "iot_mode": "REAL",
            "iot_device_name": DEVICE_NAME,
            "iot_device_id": DEVICE_ID,
            "simulation_approved": False,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def set_connection(client: TestClient, connected: bool, **overrides: object):
    return client.post(
        "/api/iot/connection",
        json={
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME,
            "connected": connected,
            "notifications_active": connected,
            **overrides,
        },
    )


def enable_real_production(client: TestClient) -> None:
    configure_real_controller(client)
    install_test_models(client)
    client.app.state.vision._camera_preflight["0"] = {
        "camera_id": "0",
        "camera_ready": True,
        "workstation_checked": True,
        "workstation_visible": True,
    }
    response = set_connection(client, True)
    assert response.status_code == 200, response.text


def create_production(client: TestClient, employee: dict) -> dict:
    response = client.post(
        "/api/sessions",
        json={"employee_id": employee["id"], "target_pieces": 25, "session_mode": "PRODUCTION"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_real_controller_only_becomes_ready_after_notifications_are_active(
    configured_client: TestClient, employee: dict
) -> None:
    configure_real_controller(configured_client)
    install_test_models(configured_client)
    configured_client.app.state.vision._camera_preflight["0"] = {
        "workstation_visible": True, "workstation_checked": True
    }

    pending = configured_client.get("/api/readiness").json()
    assert pending["productionReady"] is False

    incomplete = set_connection(configured_client, True, notifications_active=False)
    assert incomplete.status_code == 200
    assert configured_client.get("/api/readiness").json()["productionReady"] is False

    ready = set_connection(configured_client, True)
    assert ready.status_code == 200
    assert ready.json()["event"]["event_type"] == "RECONNECTED"
    assert configured_client.get("/api/readiness").json()["productionReady"] is True
    assert create_production(configured_client, employee)["session_mode"] == "PRODUCTION"


def test_tested_camera_can_start_production_before_workstation_visibility_is_checked(
    configured_client: TestClient, employee: dict
) -> None:
    configure_real_controller(configured_client)
    install_test_models(configured_client)
    configured_client.app.state.vision._camera_preflight["0"] = {
        "camera_id": "0",
        "camera_ready": True,
        "workstation_checked": True,
        "workstation_visible": False,
    }
    assert set_connection(configured_client, True).status_code == 200

    readiness = configured_client.get("/api/readiness").json()
    assert readiness["productionReady"] is True
    assert len(readiness["components"]) == 6
    assert "workstation_view" not in {
        component["id"] for component in readiness["components"]
    }
    assert create_production(configured_client, employee)["session_mode"] == "PRODUCTION"


def test_connection_updates_reject_unknown_or_impossible_controller_states(
    configured_client: TestClient,
) -> None:
    assert set_connection(configured_client, True).status_code == 409
    configure_real_controller(configured_client)

    unknown = set_connection(configured_client, True, device_id="another-device")
    assert unknown.status_code == 409

    impossible = set_connection(configured_client, False, notifications_active=True)
    assert impossible.status_code == 422


def test_real_controller_connection_transitions_are_idempotent(
    configured_client: TestClient,
) -> None:
    configure_real_controller(configured_client)

    first = set_connection(configured_client, True).json()
    second = set_connection(configured_client, True).json()
    assert first["event"]["event_type"] == "RECONNECTED"
    assert first["event"]["session_id"] is None
    assert second["event"] is None

    disconnected = set_connection(configured_client, False).json()
    duplicate = set_connection(configured_client, False).json()
    assert disconnected["event"]["event_type"] == "DISCONNECTED"
    assert duplicate["event"] is None


def test_hardware_buttons_attach_to_the_active_employee_and_pause_counting(
    configured_client: TestClient, employee: dict
) -> None:
    enable_real_production(configured_client)
    session = create_production(configured_client, employee)

    response = configured_client.post(
        "/api/iot-events",
        json={"event_type": "REWORK", "event_source": "HARDWARE", "device_name": DEVICE_NAME},
    )

    assert response.status_code == 201
    event = response.json()
    assert event["session_id"] == session["id"]
    assert event["employee_id"] == employee["id"]
    assert event["event_source"] == "HARDWARE"
    assert event["mode_before"] == "NORMAL"
    assert event["mode_after"] == "REWORK"

    blocked = configured_client.post(
        f"/api/sessions/{session['id']}/pieces", json={"event_source": "VISION"}
    )
    assert blocked.status_code == 409

    reset = configured_client.post(
        "/api/iot-events", json={"event_type": "RESET", "event_source": "HARDWARE"}
    )
    assert reset.json()["mode_after"] == "NORMAL"
    current = configured_client.get(f"/api/sessions/{session['id']}").json()
    assert current["operator_mode"] == "NORMAL"


def test_physical_button_test_is_saved_without_requiring_a_session(
    configured_client: TestClient,
) -> None:
    configure_real_controller(configured_client)
    set_connection(configured_client, True)

    event = configured_client.post(
        "/api/iot-events", json={"event_type": "RESET", "event_source": "HARDWARE"}
    )
    assert event.status_code == 201
    assert event.json()["session_id"] is None
    assert event.json()["event_source"] == "HARDWARE"


def test_disconnection_is_separate_from_downtime_and_reconnection_restores_production(
    configured_client: TestClient, employee: dict
) -> None:
    enable_real_production(configured_client)
    session = create_production(configured_client, employee)

    disconnected = set_connection(
        configured_client, False, reason="The controller moved outside Bluetooth range."
    )
    assert disconnected.status_code == 200
    assert disconnected.json()["event"]["event_type"] == "DISCONNECTED"
    assert disconnected.json()["event"]["session_id"] == session["id"]
    assert disconnected.json()["event"]["mode_after"] == "NORMAL"

    blocked = configured_client.post(
        f"/api/sessions/{session['id']}/pieces", json={"event_source": "VISION"}
    )
    assert blocked.status_code == 409

    reconnected = set_connection(configured_client, True)
    assert reconnected.json()["event"]["event_type"] == "RECONNECTED"
    recovered = configured_client.post(
        f"/api/sessions/{session['id']}/pieces", json={"event_source": "VISION"}
    )
    assert recovered.status_code == 201

    dashboard = configured_client.get(f"/api/sessions/{session['id']}/dashboard").json()
    assert dashboard["iot_metrics"]["disconnect_count"] == 1
    assert dashboard["iot_metrics"]["downtime_count"] == 0


def test_hardware_events_require_live_notification_delivery(
    configured_client: TestClient,
) -> None:
    configure_real_controller(configured_client)
    rejected = configured_client.post(
        "/api/iot-events", json={"event_type": "REWORK", "event_source": "HARDWARE"}
    )
    assert rejected.status_code == 409

    set_connection(configured_client, True)
    forged_lifecycle = configured_client.post(
        "/api/iot-events", json={"event_type": "DISCONNECTED", "event_source": "HARDWARE"}
    )
    assert forged_lifecycle.status_code == 409


def test_switching_physical_controller_identity_invalidates_previous_connection(
    configured_client: TestClient,
) -> None:
    configure_real_controller(configured_client)
    set_connection(configured_client, True)

    replacement = configured_client.put(
        "/api/device-configuration",
        json={
            "camera_id": "0", "camera_label": "Factory sewing camera", "camera_tested": True,
            "iot_mode": "REAL", "iot_device_name": DEVICE_NAME,
            "iot_device_id": "replacement-controller-id", "simulation_approved": False,
        },
    ).json()

    assert replacement["iot_connected"] is False
    assert replacement["iot_notifications_active"] is False


def test_database_connection_can_follow_fastapi_between_worker_threads(tmp_path: Path) -> None:
    connection = connect(tmp_path / "threaded.sqlite3")
    results: list[int] = []

    def use_connection() -> None:
        results.append(connection.execute("SELECT 42").fetchone()[0])

    worker = threading.Thread(target=use_connection)
    worker.start()
    worker.join(timeout=5)
    connection.close()

    assert results == [42]


def test_restart_invalidates_stale_hardware_connection_and_preserves_active_session(
    configured_client: TestClient, employee: dict
) -> None:
    enable_real_production(configured_client)
    session = create_production(configured_client, employee)
    settings: Settings = configured_client.app.state.settings

    with TestClient(create_application(settings)) as restarted:
        restarted.headers.update({"Authorization": configured_client.headers["authorization"]})
        configuration = restarted.get("/api/device-configuration").json()
        assert configuration["iot_connected"] is False
        assert configuration["iot_notifications_active"] is False
        assert restarted.get("/api/sessions/active").json()["id"] == session["id"]

        events = restarted.get(f"/api/iot-events?session_id={session['id']}").json()
        assert events[0]["event_type"] == "DISCONNECTED"
        assert "reconnect" in events[0]["payload_json"].lower()


def test_camera_scan_receives_browser_detected_camera_count(
    configured_client: TestClient, monkeypatch
) -> None:
    seen: list[int | None] = []

    def scan(expected_count: int | None) -> list[dict]:
        seen.append(expected_count)
        return []

    monkeypatch.setattr(configured_client.app.state.vision, "scan_cameras", scan)
    response = configured_client.get("/api/vision/cameras?expected_count=2")
    assert response.status_code == 200
    assert seen == [2]
    assert configured_client.get("/api/vision/cameras?expected_count=8").status_code == 422


def test_camera_warmup_retries_empty_frames_before_accepting_a_usable_image(monkeypatch) -> None:
    frame = np.full((8, 10, 3), 120, dtype=np.uint8)

    class WarmingCamera:
        def __init__(self) -> None:
            self.calls = 0

        def read(self):
            self.calls += 1
            return (False, None) if self.calls < 3 else (True, frame)

    monkeypatch.setattr(vision_runtime, "CAMERA_FRAME_RETRY_SECONDS", 0.0)
    camera = WarmingCamera()
    received = vision_runtime.read_usable_camera_frame(camera, timeout_seconds=0.2)

    assert received is frame
    assert camera.calls == 3


def test_mac_camera_open_prefers_the_native_avfoundation_backend(monkeypatch) -> None:
    opened: list[tuple[int, ...]] = []

    class NativeCapture:
        def isOpened(self) -> bool:
            return True

    class NativeOpenCv:
        CAP_AVFOUNDATION = 1200

        @staticmethod
        def VideoCapture(*arguments: int) -> NativeCapture:
            opened.append(arguments)
            return NativeCapture()

    monkeypatch.setattr(vision_runtime.sys, "platform", "darwin")
    capture = vision_runtime.open_camera_capture(NativeOpenCv(), 1)

    assert capture.isOpened() is True
    assert opened == [(1, 1200)]


def test_camera_test_reopens_device_after_the_first_empty_capture(
    configured_client: TestClient, monkeypatch
) -> None:
    opened: list[object] = []
    captured = np.full((12, 18, 3), 100, dtype=np.uint8)

    class RecoveringCapture:
        def __init__(self) -> None:
            self.released = False

        def isOpened(self) -> bool:
            return True

        def release(self) -> None:
            self.released = True

    class FakeOpenCv:
        @staticmethod
        def VideoCapture(_index: int) -> RecoveringCapture:
            capture = RecoveringCapture()
            opened.append(capture)
            return capture

    def warmup(_capture: object, timeout_seconds: float = 3.0):
        return None if len(opened) == 1 else captured

    monkeypatch.setattr(vision_runtime, "get_opencv", lambda: FakeOpenCv())
    monkeypatch.setattr(vision_runtime, "read_usable_camera_frame", warmup)
    monkeypatch.setattr(vision_runtime.time, "sleep", lambda _seconds: None)

    result = configured_client.post("/api/vision/cameras/test", json={"camera_id": "0"})

    assert result.status_code == 200, result.text
    assert result.json()["width"] == 18
    assert result.json()["height"] == 12
    assert len(opened) == 2
    assert all(capture.released for capture in opened)
