from __future__ import annotations

from fastapi.testclient import TestClient


def test_backend_rejects_missing_authentication(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Authorization": ""})
    assert response.status_code == 401


def test_backend_rejects_an_incorrect_authentication_token(client: TestClient) -> None:
    response = client.get("/api/employees", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_database_health_and_initial_migration(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ready"
    assert response.json()["schema_version"] == 1


def test_employee_creation_normalizes_codes_and_supports_dropdowns(client: TestClient) -> None:
    response = client.post(
        "/api/employees",
        json={"employee_code": "emp-002", "full_name": "Nadeesha Silva", "sewing_line": "Line B"},
    )
    assert response.status_code == 201
    assert response.json()["employee_code"] == "EMP-002"
    assert response.json()["sewing_line"] == "Line B"
    assert client.get("/api/employees").json()[0]["full_name"] == "Nadeesha Silva"


def test_duplicate_employee_codes_are_rejected(client: TestClient) -> None:
    payload = {"employee_code": "EMP-007", "full_name": "First Operator", "sewing_line": "Line A"}
    assert client.post("/api/employees", json=payload).status_code == 201
    assert client.post("/api/employees", json=payload).status_code == 409


def test_inactive_employees_are_hidden_from_session_dropdowns(
    configured_client: TestClient, employee: dict
) -> None:
    response = configured_client.put(
        f"/api/employees/{employee['id']}",
        json={
            "employee_code": employee["employee_code"],
            "full_name": employee["full_name"],
            "sewing_line": "Line C",
            "active": False,
        },
    )
    assert response.status_code == 200
    assert configured_client.get("/api/employees").json() == []
    assert len(configured_client.get("/api/employees?include_inactive=true").json()) == 1


def test_session_preserves_employee_and_line_snapshots(
    configured_client: TestClient, employee: dict, validation_session: dict
) -> None:
    configured_client.put(
        f"/api/employees/{employee['id']}",
        json={
            "employee_code": "EMP-001",
            "full_name": "Kavindi Fernando",
            "sewing_line": "Line Z",
            "active": True,
        },
    )
    stored_session = configured_client.get(f"/api/sessions/{validation_session['id']}").json()
    assert stored_session["employee_name"] == "Kavindi Perera"
    assert stored_session["sewing_line"] == "Line A"
