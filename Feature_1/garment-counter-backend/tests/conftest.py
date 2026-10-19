from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_application

TEST_TOKEN = "phase-two-local-test-token-0123456789"


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    model_directory = tmp_path / "models"
    model_directory.mkdir()
    (model_directory / "best_model.pt").touch()
    (model_directory / "best.pt").touch()

    settings = Settings(
        auth_token=TEST_TOKEN,
        data_directory=tmp_path / "data",
        model_directory=model_directory,
        environment="test",
    )

    with TestClient(create_application(settings)) as application_client:
        application_client.headers.update({"Authorization": f"Bearer {TEST_TOKEN}"})
        yield application_client


@pytest.fixture()
def configured_client(client: TestClient) -> TestClient:
    response = client.put(
        "/api/device-configuration",
        json={
            "camera_id": "camera-01",
            "camera_label": "Overhead workstation camera",
            "camera_tested": True,
            "iot_mode": "SIMULATED",
            "iot_device_name": "Validation controller",
            "simulation_approved": True,
        },
    )
    assert response.status_code == 200
    return client


@pytest.fixture()
def employee(configured_client: TestClient) -> dict:
    response = configured_client.post(
        "/api/employees",
        json={"employee_code": "EMP-001", "full_name": "Kavindi Perera", "sewing_line": "Line A"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def validation_session(configured_client: TestClient, employee: dict) -> dict:
    response = configured_client.post(
        "/api/sessions",
        json={
            "employee_id": employee["id"],
            "target_pieces": 12,
            "workstation_id": "WS-04",
            "session_mode": "VALIDATION",
        },
    )
    assert response.status_code == 201
    return response.json()
