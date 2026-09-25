from __future__ import annotations

import threading
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

import app.vision.runtime as runtime_module
from app.database import connect, transaction
from app.vision.decoding import GarmentCycleDecoder
from app.vision.detector import WorkstationDetection


class TestWorkstationDetector:
    def detect(self, frame: np.ndarray) -> WorkstationDetection:
        visible = float(frame.mean()) > 10
        return WorkstationDetection(
            visible=visible,
            confidence=0.97 if visible else 0.0,
            bbox=(4, 4, 56, 42) if visible else None,
            label="workstation" if visible else None,
            message="Sewing workstation verified." if visible else "Workstation not visible.",
        )


class TestGarmentClassifier:
    def predict(self, frames: list[np.ndarray]) -> dict:
        sewing = float(frames[-1].mean()) > 110
        return {
            "label": "SEWING" if sewing else "IDLE_SETUP",
            "confidence": 0.98,
            "probabilities": {"IDLE_SETUP": 0.02 if sewing else 0.98, "SEWING": 0.98 if sewing else 0.02},
        }


def create_validation_video(destination: Path, levels: list[int] | None = None) -> None:
    writer = cv2.VideoWriter(
        str(destination), cv2.VideoWriter_fourcc(*"MJPG"), 55.0, (64, 48)
    )
    assert writer.isOpened()
    for level in levels or [40] * 14 + [185] * 45 + [40] * 37:
        writer.write(np.full((48, 64, 3), level, dtype=np.uint8))
    writer.release()


def install_test_models(client: TestClient) -> None:
    client.app.state.vision_registry.install_models(TestWorkstationDetector(), TestGarmentClassifier())


def accelerate_validation_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(runtime_module, "PREDICTION_INTERVAL_SECONDS", 0.018)
    monkeypatch.setattr(runtime_module, "WORKSTATION_RECHECK_INTERVAL_SECONDS", 0.04)
    monkeypatch.setattr(runtime_module, "WORKSTATION_FAILED_RECHECK_LIMIT", 2)
    monkeypatch.setattr(
        runtime_module,
        "GarmentCycleDecoder",
        lambda: GarmentCycleDecoder(
            minimum_sewing_seconds=0.10,
            minimum_idle_seconds=0.08,
            cooldown_seconds=0.05,
        ),
    )


def connect_video_preview(client: TestClient, session_id: int) -> None:
    """Mirror the desktop MJPEG request without consuming an endless stream."""

    client.app.state.vision._preview_connected.set()


def test_vision_routes_require_the_desktop_sidecar_token(client: TestClient) -> None:
    assert client.get("/api/vision/models", headers={"Authorization": ""}).status_code == 401


def test_model_readiness_reflects_genuine_loaded_runtime_components(
    configured_client: TestClient,
) -> None:
    install_test_models(configured_client)
    readiness = configured_client.get("/api/readiness").json()
    components = {component["id"]: component for component in readiness["components"]}
    assert components["workstation_detector"]["status"] == "ready"
    assert components["garment_classifier"]["status"] == "ready"
    assert readiness["model_resources"]["classifier_runtime_ready"] is True
    assert readiness["model_resources"]["workstation_runtime_ready"] is True
    assert readiness["productionReady"] is False


def test_camera_monitoring_rejects_legacy_browser_camera_identifiers(
    configured_client: TestClient, validation_session: dict
) -> None:
    install_test_models(configured_client)
    response = configured_client.post(
        "/api/vision/start", json={"session_id": validation_session["id"], "source_type": "camera"}
    )
    assert response.status_code == 409
    assert "Scan and test cameras again" in response.json()["detail"]


def test_pipeline_cannot_start_before_both_trained_models_are_loaded(
    configured_client: TestClient, validation_session: dict
) -> None:
    response = configured_client.post(
        "/api/vision/start", json={"session_id": validation_session["id"], "source_type": "camera"}
    )
    assert response.status_code == 409
    assert "Both trained AI models" in response.json()["detail"]


def test_recorded_video_in_production_persists_confirmed_garment_counts(
    configured_client: TestClient,
    validation_session: dict,
    monkeypatch,
    tmp_path: Path,
) -> None:
    install_test_models(configured_client)
    accelerate_validation_pipeline(monkeypatch)
    connection = connect(configured_client.app.state.settings.database_path)
    try:
        with transaction(connection):
            connection.execute(
                "UPDATE production_sessions SET session_mode = 'PRODUCTION', simulated_iot = 0 WHERE id = ?",
                (validation_session["id"],),
            )
    finally:
        connection.close()

    video = tmp_path / "production-test-workflow.avi"
    create_validation_video(video)
    response = configured_client.post(
        "/api/vision/start",
        json={
            "session_id": validation_session["id"],
            "source_type": "video",
            "video_path": str(video),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["test_workflow"] is False
    connect_video_preview(configured_client, validation_session["id"])

    deadline = time.monotonic() + 8.0
    current: dict = {}
    while time.monotonic() < deadline:
        current = configured_client.get(
            f"/api/vision/status/{validation_session['id']}"
        ).json()
        if current["phase"] in {"VIDEO_COMPLETE", "ERROR"}:
            break
        time.sleep(0.025)

    assert current["phase"] == "VIDEO_COMPLETE", current
    dashboard = configured_client.get(
        f"/api/sessions/{validation_session['id']}/dashboard"
    ).json()
    assert dashboard["session"]["total_pieces"] >= 1
    assert dashboard["piece_events"][0]["piece_number"] == 1
    assert dashboard["piece_events"][0]["event_source"] == "VISION"
    assert dashboard["piece_events"][0]["cycle_seconds"] > 0


def test_live_stream_is_unavailable_before_monitoring_starts(
    configured_client: TestClient, validation_session: dict
) -> None:
    response = configured_client.get(f"/api/vision/stream/{validation_session['id']}")
    assert response.status_code == 409


def test_validation_video_executes_camera_pipeline_and_persists_first_real_cycle(
    configured_client: TestClient,
    validation_session: dict,
    monkeypatch,
    tmp_path: Path,
) -> None:
    install_test_models(configured_client)
    accelerate_validation_pipeline(monkeypatch)
    video = tmp_path / "real-camera-pipeline.avi"
    create_validation_video(video)
    response = configured_client.post(
        "/api/vision/start",
        json={
            "session_id": validation_session["id"],
            "source_type": "video",
            "video_path": str(video),
        },
    )
    assert response.status_code == 200
    assert response.json()["running"] is True
    connect_video_preview(configured_client, validation_session["id"])

    deadline = time.monotonic() + 8.0
    current: dict = {}
    while time.monotonic() < deadline:
        current = configured_client.get(f"/api/vision/status/{validation_session['id']}").json()
        if current["phase"] in {"VIDEO_COMPLETE", "ERROR"}:
            break
        time.sleep(0.025)

    assert current["phase"] == "VIDEO_COMPLETE", current
    assert current["frames_processed"] == 96
    dashboard = configured_client.get(
        f"/api/sessions/{validation_session['id']}/dashboard"
    ).json()
    assert dashboard["session"]["total_pieces"] >= 1
    assert dashboard["piece_events"][0]["piece_number"] == 1
    assert dashboard["piece_events"][0]["cycle_seconds"] > 0
    assert dashboard["piece_events"][0]["event_source"] == "VALIDATION"
    assert dashboard["inference"]["models"]["ready"] is True


def test_invalid_workstation_view_cancels_pending_cycle_before_idle_returns(
    configured_client: TestClient,
    validation_session: dict,
    monkeypatch,
    tmp_path: Path,
) -> None:
    install_test_models(configured_client)
    accelerate_validation_pipeline(monkeypatch)
    video = tmp_path / "interrupted-workstation.avi"
    create_validation_video(video, [40] * 14 + [185] * 42 + [0] * 18 + [40] * 35)
    response = configured_client.post(
        "/api/vision/start",
        json={
            "session_id": validation_session["id"],
            "source_type": "video",
            "video_path": str(video),
        },
    )
    assert response.status_code == 200
    connect_video_preview(configured_client, validation_session["id"])

    deadline = time.monotonic() + 8.0
    current: dict = {}
    while time.monotonic() < deadline:
        current = configured_client.get(f"/api/vision/status/{validation_session['id']}").json()
        if current["phase"] in {"VIDEO_COMPLETE", "ERROR"}:
            break
        time.sleep(0.025)

    assert current["phase"] == "VIDEO_COMPLETE", current
    dashboard = configured_client.get(
        f"/api/sessions/{validation_session['id']}/dashboard"
    ).json()
    assert dashboard["session"]["total_pieces"] == 0
    assert dashboard["piece_events"] == []


def test_completing_session_safely_stops_active_camera_runtime(
    configured_client: TestClient, validation_session: dict
) -> None:
    response = configured_client.post(f"/api/sessions/{validation_session['id']}/complete")
    assert response.status_code == 200
    assert configured_client.app.state.vision.status(validation_session["id"])["running"] is False


def test_recorded_video_waits_for_visible_preview_before_inference(
    configured_client: TestClient,
    validation_session: dict,
    tmp_path: Path,
) -> None:
    detector_entered = threading.Event()
    detector_release = threading.Event()

    class BlockingDetector(TestWorkstationDetector):
        def detect(self, frame: np.ndarray) -> WorkstationDetection:
            detector_entered.set()
            detector_release.wait(timeout=2.0)
            return super().detect(frame)

    configured_client.app.state.vision_registry.install_models(
        BlockingDetector(), TestGarmentClassifier()
    )
    video = tmp_path / "preview-first.avi"
    create_validation_video(video, [40] * 12)

    response = configured_client.post(
        "/api/vision/start",
        json={
            "session_id": validation_session["id"],
            "source_type": "video",
            "video_path": str(video),
        },
    )
    assert response.status_code == 200

    time.sleep(0.15)
    waiting = configured_client.get(
        f"/api/vision/status/{validation_session['id']}"
    ).json()
    assert waiting["phase"] == "STARTING"
    assert waiting["frames_processed"] == 0
    assert waiting["preview_ready"] is False
    assert detector_entered.is_set() is False

    connect_video_preview(configured_client, validation_session["id"])
    assert detector_entered.wait(timeout=2.0)
    during_inference = configured_client.get(
        f"/api/vision/status/{validation_session['id']}"
    ).json()
    assert during_inference["preview_ready"] is True
    assert configured_client.app.state.vision._latest_jpeg is not None

    detector_release.set()
    configured_client.post(f"/api/vision/stop/{validation_session['id']}")
