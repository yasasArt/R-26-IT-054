from __future__ import annotations

import hmac
import json
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any, Iterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from app import __version__
from app.analytics import build_analytics, calculate_event_intervals
from app.config import Settings
from app.database import connect, migrate, transaction
from app.excel_export import build_workbook
from app.production import persist_piece_event
from app.schemas import (
    CameraTest,
    DeviceConfigurationUpdate,
    EmployeeCreate,
    EmployeeUpdate,
    IoTConnectionUpdate,
    IoTEventCreate,
    PieceCreate,
    SessionCreate,
    SessionDataDelete,
    SewingStart,
    VisionStart,
)
from app.time_utils import format_utc, utc_now
from app.vision.registry import VisionModelRegistry
from app.vision.runtime import VisionRuntime


def database_connection(request: Request) -> Iterator[sqlite3.Connection]:
    settings: Settings = request.app.state.settings
    connection = connect(settings.database_path)

    try:
        yield connection
    finally:
        connection.close()


Database = Annotated[sqlite3.Connection, Depends(database_connection)]


def serialize_employee(row: sqlite3.Row) -> dict[str, Any]:
    employee = dict(row)
    employee["active"] = bool(employee["active"])
    return employee


def serialize_configuration(row: sqlite3.Row) -> dict[str, Any]:
    configuration = dict(row)

    for field in (
        "camera_tested",
        "iot_connected",
        "iot_notifications_active",
        "simulation_approved",
    ):
        configuration[field] = bool(configuration[field])

    return configuration


def serialize_session(row: sqlite3.Row) -> dict[str, Any]:
    session = dict(row)
    session["simulated_iot"] = bool(session["simulated_iot"])
    session["remaining_pieces"] = max(0, session["target_pieces"] - session["total_pieces"])
    session["achievement_percent"] = round(
        session["total_pieces"] / session["target_pieces"] * 100, 2
    )
    return session


def require_session(connection: sqlite3.Connection, session_id: int) -> sqlite3.Row:
    session = connection.execute(
        "SELECT * FROM production_sessions WHERE id = ?", (session_id,)
    ).fetchone()

    if session is None:
        raise HTTPException(status_code=404, detail="The requested production session was not found.")

    return session


def delete_session_descendants(connection: sqlite3.Connection) -> None:
    """Delete every row that depends on production history, including legacy tables."""

    tables = {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    protected = {"employees", "device_configuration", "schema_migrations"}
    relationships: dict[str, list[tuple[str, str, str]]] = {}

    for child_table in tables:
        if child_table in protected:
            continue
        for foreign_key in connection.execute(
            f'PRAGMA foreign_key_list("{child_table.replace(chr(34), chr(34) * 2)}")'
        ).fetchall():
            parent_table = str(foreign_key["table"])
            child_column = str(foreign_key["from"])
            parent_column = str(foreign_key["to"] or "id")
            relationships.setdefault(parent_table, []).append(
                (child_table, child_column, parent_column)
            )

    def quoted(identifier: str) -> str:
        return f'"{identifier.replace(chr(34), chr(34) * 2)}"'

    def delete_children(parent_table: str, parent_where: str, ancestry: frozenset[str]) -> None:
        for child_table, child_column, parent_column in relationships.get(parent_table, []):
            if child_table in protected or child_table in ancestry:
                continue
            child_where = (
                f"{quoted(child_column)} IN ("
                f"SELECT {quoted(parent_column)} FROM {quoted(parent_table)} WHERE {parent_where}"
                ")"
            )
            delete_children(child_table, child_where, ancestry | {child_table})
            connection.execute(
                f"DELETE FROM {quoted(child_table)} WHERE {child_where}"
            )

    delete_children("production_sessions", "1 = 1", frozenset({"production_sessions"}))


def get_configuration(connection: sqlite3.Connection) -> sqlite3.Row:
    configuration = connection.execute("SELECT * FROM device_configuration WHERE id = 1").fetchone()

    if configuration is None:
        raise RuntimeError("The device-configuration record was not initialized.")

    return configuration


def readiness_payload(
    connection: sqlite3.Connection,
    settings: Settings,
    vision: VisionRuntime | None = None,
) -> dict[str, Any]:
    configuration = serialize_configuration(get_configuration(connection))
    classifier_exists = (settings.model_directory / "best_model.pt").is_file()
    detector_exists = (settings.model_directory / "best.pt").is_file()
    models = vision.registry.snapshot() if vision else None
    detector_model = models["detector"] if models else {"state": "NOT_LOADED", "message": ""}
    classifier_model = models["classifier"] if models else {"state": "NOT_LOADED", "message": ""}
    def model_readiness(exists: bool, model: dict[str, Any], filename: str) -> tuple[str, str]:
        if not exists:
            return "blocked", f"The trained checkpoint {filename} is missing."
        if model["state"] == "READY":
            return "ready", model["message"]
        if model["state"] == "FAILED":
            return "blocked", model["message"]
        if model["state"] == "LOADING":
            return "pending", model["message"]
        return "attention", "Checkpoint found. Start or retry trained-model loading."

    detector_status, detector_detail = model_readiness(detector_exists, detector_model, "best.pt")
    classifier_status, classifier_detail = model_readiness(
        classifier_exists, classifier_model, "best_model.pt"
    )
    real_iot_ready = (
        configuration["iot_mode"] == "REAL"
        and configuration["iot_connected"]
        and configuration["iot_notifications_active"]
    )
    validation_iot_ready = (
        configuration["iot_mode"] == "SIMULATED"
        and configuration["simulation_approved"]
        and configuration["iot_connected"]
        and configuration["iot_notifications_active"]
    )
    components = [
        {
            "id": "desktop",
            "label": "Desktop runtime",
            "description": "Secure Electron main, preload, and renderer",
            "status": "ready",
            "detail": "The desktop application is active.",
        },
        {
            "id": "backend",
            "label": "Local application service",
            "description": "Authenticated FastAPI and SQLite sidecar",
            "status": "ready",
            "detail": "The local database and application service are available.",
        },
        {
            "id": "workstation_detector",
            "label": "Workstation detector",
            "description": "YOLO workstation-visibility validation",
            "status": detector_status,
            "detail": detector_detail,
        },
        {
            "id": "garment_classifier",
            "label": "Garment classifier",
            "description": "Two-state temporal sewing classifier",
            "status": classifier_status,
            "detail": classifier_detail,
        },
        {
            "id": "camera",
            "label": "Sewing camera",
            "description": configuration["camera_label"] or "No camera selected",
            "status": "ready" if configuration["camera_tested"] else "pending",
            "detail": (
                "The selected camera was successfully tested."
                if configuration["camera_tested"]
                else "Select and test a camera before continuing."
            ),
        },
        {
            "id": "iot_controller",
            "label": "Operator controller",
            "description": configuration["iot_device_name"] or "ESP32-C3 Bluetooth controller",
            "status": "ready" if real_iot_ready else "attention" if validation_iot_ready else "pending",
            "detail": (
                "The physical controller is connected and notifications are active."
                if real_iot_ready
                else "Validation simulation is active; production remains blocked."
                if validation_iot_ready
                else "Connect the physical controller or explicitly enable validation simulation."
            ),
        },
    ]
    ready_count = sum(component["status"] == "ready" for component in components)

    return {
        "checkedAt": format_utc(utc_now()),
        "components": components,
        "productionReady": all(component["status"] == "ready" for component in components),
        "completionPercent": round(ready_count / len(components) * 100),
        "validationReady": bool(configuration["camera_tested"] and validation_iot_ready),
        "model_resources": {
            "classifier_checkpoint_exists": classifier_exists,
            "workstation_checkpoint_exists": detector_exists,
            "classifier_runtime_ready": classifier_model["state"] == "READY",
            "workstation_runtime_ready": detector_model["state"] == "READY",
        },
        "vision_models": models,
    }


def create_application(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_environment()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> Iterator[None]:
        connection = connect(resolved_settings.database_path)

        try:
            migrate(connection)
            connection.execute(
                "INSERT OR IGNORE INTO device_configuration(id, updated_at) VALUES (1, ?)",
                (format_utc(utc_now()),),
            )
            previous_configuration = get_configuration(connection)
            if previous_configuration["iot_mode"] == "REAL" and (
                previous_configuration["iot_connected"]
                or previous_configuration["iot_notifications_active"]
            ):
                timestamp = format_utc(utc_now())
                active = connection.execute(
                    "SELECT * FROM production_sessions WHERE status = 'ACTIVE' LIMIT 1"
                ).fetchone()
                with transaction(connection):
                    connection.execute(
                        "UPDATE device_configuration SET iot_connected = 0, "
                        "iot_notifications_active = 0, updated_at = ? WHERE id = 1",
                        (timestamp,),
                    )
                    if active is not None and active["session_mode"] == "PRODUCTION":
                        connection.execute(
                            "INSERT INTO iot_events(session_id, employee_id, event_type, "
                            "mode_before, mode_after, device_name, event_source, payload_json, "
                            "occurred_at, created_at) VALUES (?, ?, 'DISCONNECTED', ?, ?, ?, "
                            "'HARDWARE', ?, ?, ?)",
                            (
                                active["id"], active["employee_id"], active["operator_mode"],
                                active["operator_mode"], previous_configuration["iot_device_name"],
                                json.dumps({"reason": "Application restarted; reconnect the controller."}),
                                timestamp, timestamp,
                            ),
                        )
        finally:
            connection.close()

        application.state.settings = resolved_settings
        application.state.vision_registry = VisionModelRegistry(resolved_settings)
        application.state.vision = VisionRuntime(
            resolved_settings, application.state.vision_registry
        )
        if resolved_settings.environment != "test":
            application.state.vision_registry.start_loading()

        try:
            yield
        finally:
            application.state.vision.stop()

    application = FastAPI(
        title="Garment Counter Desktop Sidecar",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @application.middleware("http")
    async def authenticate_local_request(request: Request, call_next: Any) -> Response:
        expected = f"Bearer {resolved_settings.auth_token}"
        provided = request.headers.get("authorization", "")

        if not hmac.compare_digest(provided.encode(), expected.encode()):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "A valid desktop sidecar authorization token is required."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)

    @application.get("/api/health")
    def health(connection: Database) -> dict[str, Any]:
        database_version = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        return {
            "status": "ok",
            "application": resolved_settings.application_name,
            "version": __version__,
            "database": "ready",
            "schema_version": database_version,
        }

    @application.get("/api/readiness")
    def get_readiness(connection: Database) -> dict[str, Any]:
        return readiness_payload(connection, resolved_settings, application.state.vision)

    @application.get("/api/vision/models")
    def vision_models() -> dict[str, Any]:
        return application.state.vision_registry.snapshot()

    @application.post("/api/vision/models/load")
    def load_vision_models() -> dict[str, Any]:
        return application.state.vision_registry.start_loading()

    @application.get("/api/vision/cameras")
    def vision_cameras(expected_count: int | None = Query(default=None, ge=1, le=5)) -> list[dict[str, Any]]:
        try:
            return application.state.vision.scan_cameras(expected_count)
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/api/vision/cameras/test")
    def test_vision_camera(payload: CameraTest) -> dict[str, Any]:
        try:
            return application.state.vision.test_camera(payload.camera_id)
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/api/vision/start")
    def start_vision(payload: VisionStart) -> dict[str, Any]:
        try:
            return application.state.vision.start(
                payload.session_id, payload.source_type, payload.video_path
            )
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post("/api/vision/stop/{session_id}")
    def stop_vision(session_id: int) -> dict[str, Any]:
        try:
            return application.state.vision.stop(session_id)
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.get("/api/vision/status/{session_id}")
    def vision_status(session_id: int, connection: Database) -> dict[str, Any]:
        require_session(connection, session_id)
        return application.state.vision.status(session_id)

    @application.get("/api/vision/stream/{session_id}")
    def vision_stream(session_id: int, connection: Database) -> StreamingResponse:
        require_session(connection, session_id)
        current = application.state.vision.status(session_id)
        if not current["running"]:
            raise HTTPException(status_code=409, detail="Start live monitoring before opening the camera stream.")
        return StreamingResponse(
            application.state.vision.stream(session_id),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    @application.get("/api/employees")
    def list_employees(connection: Database, include_inactive: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM employees"

        if not include_inactive:
            query += " WHERE active = 1"

        query += " ORDER BY full_name COLLATE NOCASE, employee_code"
        return [serialize_employee(row) for row in connection.execute(query).fetchall()]

    @application.post("/api/employees", status_code=status.HTTP_201_CREATED)
    def create_employee(payload: EmployeeCreate, connection: Database) -> dict[str, Any]:
        timestamp = format_utc(utc_now())

        try:
            with transaction(connection):
                cursor = connection.execute(
                    "INSERT INTO employees(employee_code, full_name, sewing_line, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        payload.employee_code.upper(), payload.full_name,
                        payload.sewing_line, timestamp, timestamp,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="This employee code is already in use.") from error

        employee = connection.execute("SELECT * FROM employees WHERE id = ?", (cursor.lastrowid,)).fetchone()
        assert employee is not None
        return serialize_employee(employee)

    @application.put("/api/employees/{employee_id}")
    def update_employee(employee_id: int, payload: EmployeeUpdate, connection: Database) -> dict[str, Any]:
        employee = connection.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()

        if employee is None:
            raise HTTPException(status_code=404, detail="The selected employee was not found.")

        try:
            with transaction(connection):
                connection.execute(
                    "UPDATE employees SET employee_code = ?, full_name = ?, sewing_line = ?, "
                    "active = ?, updated_at = ? WHERE id = ?",
                    (
                        payload.employee_code.upper(), payload.full_name, payload.sewing_line,
                        int(payload.active), format_utc(utc_now()), employee_id,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="This employee code is already in use.") from error

        updated = connection.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
        assert updated is not None
        return serialize_employee(updated)

    @application.get("/api/device-configuration")
    def device_configuration(connection: Database) -> dict[str, Any]:
        return serialize_configuration(get_configuration(connection))

    @application.put("/api/device-configuration")
    def update_configuration(
        payload: DeviceConfigurationUpdate, connection: Database
    ) -> dict[str, Any]:
        previous = get_configuration(connection)
        timestamp = format_utc(utc_now())
        camera_tested = bool(payload.camera_tested and payload.camera_id and payload.camera_label)
        simulation_active = payload.iot_mode == "SIMULATED" and payload.simulation_approved

        if payload.iot_mode == "REAL":
            same_physical_device = bool(
                payload.iot_device_id
                and previous["iot_device_id"] == payload.iot_device_id
                and previous["iot_mode"] == "REAL"
            )
            connected = bool(previous["iot_connected"] and same_physical_device)
            notifications = bool(
                previous["iot_notifications_active"] and same_physical_device
            )
        else:
            connected = simulation_active
            notifications = simulation_active

        with transaction(connection):
            connection.execute(
                "UPDATE device_configuration SET camera_id = ?, camera_label = ?, camera_tested = ?, "
                "camera_tested_at = ?, iot_mode = ?, iot_device_name = ?, iot_device_id = ?, "
                "iot_connected = ?, iot_notifications_active = ?, simulation_approved = ?, "
                "updated_at = ? WHERE id = 1",
                (
                    payload.camera_id, payload.camera_label, int(camera_tested),
                    timestamp if camera_tested else None, payload.iot_mode,
                    payload.iot_device_name, payload.iot_device_id, int(connected),
                    int(notifications), int(payload.simulation_approved), timestamp,
                ),
            )

        return serialize_configuration(get_configuration(connection))

    @application.post("/api/iot/connection")
    def update_iot_connection(
        payload: IoTConnectionUpdate, connection: Database
    ) -> dict[str, Any]:
        configuration = serialize_configuration(get_configuration(connection))

        if configuration["iot_mode"] != "REAL":
            raise HTTPException(
                status_code=409,
                detail="Choose the physical ESP32-C3 controller before reporting Bluetooth status.",
            )
        if configuration["iot_device_id"] != payload.device_id:
            raise HTTPException(
                status_code=409,
                detail="Bluetooth status was received from an unrecognised controller.",
            )
        if payload.notifications_active and not payload.connected:
            raise HTTPException(
                status_code=422,
                detail="Bluetooth notifications cannot remain active while the device is disconnected.",
            )

        was_ready = bool(configuration["iot_connected"] and configuration["iot_notifications_active"])
        is_ready = bool(payload.connected and payload.notifications_active)
        timestamp = format_utc(utc_now())
        active = connection.execute(
            "SELECT * FROM production_sessions WHERE status = 'ACTIVE' LIMIT 1"
        ).fetchone()
        event: dict[str, Any] | None = None

        with transaction(connection):
            connection.execute(
                "UPDATE device_configuration SET iot_device_name = ?, iot_connected = ?, "
                "iot_notifications_active = ?, updated_at = ? WHERE id = 1",
                (
                    payload.device_name, int(payload.connected),
                    int(payload.notifications_active), timestamp,
                ),
            )

            if was_ready != is_ready:
                event_type = "RECONNECTED" if is_ready else "DISCONNECTED"
                current_mode = active["operator_mode"] if active is not None else "NORMAL"
                detail = {"device_id": payload.device_id}
                if payload.reason:
                    detail["reason"] = payload.reason
                cursor = connection.execute(
                    "INSERT INTO iot_events(session_id, employee_id, event_type, mode_before, "
                    "mode_after, device_name, event_source, payload_json, occurred_at, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'HARDWARE', ?, ?, ?)",
                    (
                        active["id"] if active is not None else None,
                        active["employee_id"] if active is not None else None,
                        event_type, current_mode, current_mode, payload.device_name,
                        json.dumps(detail, separators=(",", ":")), timestamp, timestamp,
                    ),
                )
                recorded = connection.execute(
                    "SELECT * FROM iot_events WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
                assert recorded is not None
                event = dict(recorded)

        return {"configuration": serialize_configuration(get_configuration(connection)), "event": event}

    @application.get("/api/sessions/active")
    def active_session(connection: Database) -> dict[str, Any] | None:
        session = connection.execute(
            "SELECT * FROM production_sessions WHERE status = 'ACTIVE' LIMIT 1"
        ).fetchone()
        return serialize_session(session) if session else None

    @application.get("/api/sessions")
    def list_sessions(connection: Database, employee_id: int | None = None) -> list[dict[str, Any]]:
        if employee_id is None:
            rows = connection.execute(
                "SELECT * FROM production_sessions ORDER BY started_at DESC, id DESC"
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM production_sessions WHERE employee_id = ? "
                "ORDER BY started_at DESC, id DESC", (employee_id,)
            ).fetchall()

        return [serialize_session(row) for row in rows]

    @application.post("/api/sessions/delete-history")
    def delete_session_history(payload: SessionDataDelete, connection: Database) -> dict[str, Any]:
        # Validate the explicit confirmation at the API boundary as well as in
        # the desktop dialog. BEGIN IMMEDIATE prevents a concurrent new session
        # from appearing between the safety check and the destructive operation.
        assert payload.confirmation == "DELETE SESSION DATA"

        with transaction(connection):
            active = connection.execute(
                "SELECT id FROM production_sessions WHERE status = 'ACTIVE' LIMIT 1"
            ).fetchone()

            if active is not None:
                raise HTTPException(
                    status_code=409,
                    detail="End the active session before deleting stored session data.",
                )

            deleted_sessions = int(
                connection.execute("SELECT COUNT(*) FROM production_sessions").fetchone()[0]
            )
            deleted_piece_events = int(
                connection.execute("SELECT COUNT(*) FROM piece_events").fetchone()[0]
            )
            deleted_iot_events = int(
                connection.execute(
                    "SELECT COUNT(*) FROM iot_events WHERE session_id IS NOT NULL"
                ).fetchone()[0]
            )

            # Delete all current and legacy tables that depend on session
            # history in foreign-key order. Standalone device tests, employees,
            # and workstation configuration remain untouched.
            delete_session_descendants(connection)
            connection.execute("DELETE FROM production_sessions")

        return {
            "deleted_sessions": deleted_sessions,
            "deleted_piece_events": deleted_piece_events,
            "deleted_iot_events": deleted_iot_events,
            "message": "Session history was permanently deleted. Employees and device settings were preserved.",
        }

    @application.post("/api/sessions", status_code=status.HTTP_201_CREATED)
    def create_session(payload: SessionCreate, connection: Database) -> dict[str, Any]:
        if active_session(connection) is not None:
            raise HTTPException(status_code=409, detail="Another session is already active.")

        employee = connection.execute(
            "SELECT * FROM employees WHERE id = ? AND active = 1", (payload.employee_id,)
        ).fetchone()

        if employee is None:
            raise HTTPException(status_code=404, detail="Select an active employee before starting a session.")

        configuration = serialize_configuration(get_configuration(connection))

        if not configuration["camera_tested"] or not configuration["camera_id"]:
            raise HTTPException(status_code=409, detail="Select and successfully test a camera first.")

        if payload.session_mode == "PRODUCTION":
            readiness = readiness_payload(connection, resolved_settings, application.state.vision)

            if not readiness["productionReady"]:
                blockers = [
                    component["label"]
                    for component in readiness["components"]
                    if component["status"] != "ready"
                ]
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Production cannot start until every required component is ready.",
                        "blockers": blockers,
                    },
                )
        elif not (
            configuration["iot_mode"] == "SIMULATED"
            and configuration["simulation_approved"]
            and configuration["iot_connected"]
            and configuration["iot_notifications_active"]
        ):
            raise HTTPException(
                status_code=409,
                detail="Validation requires an explicitly approved, connected IoT simulation.",
            )

        now = utc_now()
        timestamp = format_utc(now)
        session_code = f"GC-{now.strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

        try:
            with transaction(connection):
                cursor = connection.execute(
                    "INSERT INTO production_sessions(session_code, employee_id, employee_code, employee_name, "
                    "sewing_line, workstation_id, camera_id, camera_label, target_pieces, session_mode, "
                    "simulated_iot, started_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        session_code, employee["id"], employee["employee_code"], employee["full_name"],
                        employee["sewing_line"], payload.workstation_id, configuration["camera_id"],
                        configuration["camera_label"], payload.target_pieces, payload.session_mode,
                        int(payload.session_mode == "VALIDATION"), timestamp, timestamp,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="Another session is already active.") from error

        return serialize_session(require_session(connection, int(cursor.lastrowid)))

    @application.get("/api/sessions/{session_id}")
    def get_session(session_id: int, connection: Database) -> dict[str, Any]:
        return serialize_session(require_session(connection, session_id))

    @application.post("/api/sessions/{session_id}/complete")
    def complete_session(session_id: int, connection: Database) -> dict[str, Any]:
        session = require_session(connection, session_id)

        if session["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="This session has already been completed.")

        application.state.vision.stop(session_id)
        with transaction(connection):
            connection.execute(
                "UPDATE production_sessions SET status = 'COMPLETED', ended_at = ? WHERE id = ?",
                (format_utc(utc_now()), session_id),
            )

        return serialize_session(require_session(connection, session_id))

    @application.post("/api/sessions/{session_id}/sewing-start")
    def record_sewing_start(session_id: int, payload: SewingStart, connection: Database) -> dict[str, Any]:
        session = require_session(connection, session_id)

        if session["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="The selected session is no longer active.")

        started_at = format_utc(payload.started_at or utc_now())

        with transaction(connection):
            connection.execute(
                "UPDATE production_sessions SET first_sewing_started_at = COALESCE(first_sewing_started_at, ?) "
                "WHERE id = ?", (started_at, session_id)
            )

        return serialize_session(require_session(connection, session_id))

    @application.get("/api/sessions/{session_id}/pieces")
    def list_pieces(session_id: int, connection: Database) -> list[dict[str, Any]]:
        require_session(connection, session_id)
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM piece_events WHERE session_id = ? ORDER BY piece_number", (session_id,)
            ).fetchall()
        ]

    @application.post("/api/sessions/{session_id}/pieces", status_code=status.HTTP_201_CREATED)
    def record_piece(session_id: int, payload: PieceCreate, connection: Database) -> dict[str, Any]:
        return persist_piece_event(connection, session_id, payload)

    @application.get("/api/iot-events")
    def list_iot_events(connection: Database, session_id: int | None = None) -> list[dict[str, Any]]:
        if session_id is None:
            rows = connection.execute("SELECT * FROM iot_events ORDER BY occurred_at DESC, id DESC").fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM iot_events WHERE session_id = ? ORDER BY occurred_at DESC, id DESC",
                (session_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    @application.post("/api/iot-events", status_code=status.HTTP_201_CREATED)
    def create_iot_event(payload: IoTEventCreate, connection: Database) -> dict[str, Any]:
        configuration = serialize_configuration(get_configuration(connection))
        if payload.event_source == "HARDWARE":
            if payload.event_type not in {"REWORK", "DOWNTIME", "RESET"}:
                raise HTTPException(
                    status_code=409,
                    detail="Physical connection changes must use the verified controller-status route.",
                )
            if not (
                configuration["iot_mode"] == "REAL"
                and configuration["iot_connected"]
                and configuration["iot_notifications_active"]
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Physical button events require a connected controller with active notifications.",
                )

        session = require_session(connection, payload.session_id) if payload.session_id else None
        if session is None and payload.event_source == "HARDWARE":
            session = connection.execute(
                "SELECT * FROM production_sessions WHERE status = 'ACTIVE' LIMIT 1"
            ).fetchone()
        session_id = session["id"] if session is not None else None

        if session is not None and session["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="IoT events require an active session.")
        if payload.event_source == "VALIDATION" and not (
            configuration["iot_mode"] == "SIMULATED" and configuration["simulation_approved"]
        ):
            raise HTTPException(status_code=409, detail="Validation IoT simulation has not been approved.")
        if session is not None and session["session_mode"] == "PRODUCTION" and payload.event_source != "HARDWARE":
            raise HTTPException(status_code=409, detail="Production sessions cannot accept simulated IoT events.")

        previous_mode = session["operator_mode"] if session else "NORMAL"
        next_mode = previous_mode

        if payload.event_type in {"REWORK", "DOWNTIME"}:
            next_mode = payload.event_type
        elif payload.event_type == "RESET":
            next_mode = "NORMAL"

        timestamp = format_utc(utc_now())
        occurred_at = format_utc(payload.occurred_at or utc_now())

        with transaction(connection):
            cursor = connection.execute(
                "INSERT INTO iot_events(session_id, employee_id, event_type, mode_before, mode_after, "
                "device_name, event_source, payload_json, occurred_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id, session["employee_id"] if session else None,
                    payload.event_type, previous_mode, next_mode,
                    payload.device_name or configuration["iot_device_name"], payload.event_source,
                    json.dumps(payload.payload, separators=(",", ":")) if payload.payload else None,
                    occurred_at, timestamp,
                ),
            )

            if session is not None and payload.event_type in {"REWORK", "DOWNTIME", "RESET"}:
                connection.execute(
                    "UPDATE production_sessions SET operator_mode = ?, "
                    "first_sewing_started_at = CASE WHEN ? IN ('REWORK', 'DOWNTIME') "
                    "THEN NULL ELSE first_sewing_started_at END WHERE id = ?",
                    (next_mode, payload.event_type, session_id),
                )

            if payload.event_type == "DISCONNECTED":
                connection.execute(
                    "UPDATE device_configuration SET iot_connected = 0, iot_notifications_active = 0, "
                    "updated_at = ? WHERE id = 1", (timestamp,)
                )
            elif payload.event_type == "RECONNECTED":
                connection.execute(
                    "UPDATE device_configuration SET iot_connected = 1, iot_notifications_active = 1, "
                    "updated_at = ? WHERE id = 1", (timestamp,)
                )

        event = connection.execute("SELECT * FROM iot_events WHERE id = ?", (cursor.lastrowid,)).fetchone()
        assert event is not None
        return dict(event)

    @application.get("/api/sessions/{session_id}/dashboard")
    def session_dashboard(session_id: int, connection: Database) -> dict[str, Any]:
        session = serialize_session(require_session(connection, session_id))
        pieces = list_pieces(session_id, connection)
        iot_events = list_iot_events(connection, session_id)
        ordered_iot = list(reversed(iot_events))
        metrics = calculate_event_intervals(
            ordered_iot, session.get("ended_at") or format_utc(utc_now())
        )

        return {
            "session": session,
            "piece_events": pieces,
            "iot_events": iot_events,
            "iot_metrics": metrics,
            "target_series": [
                {"piece_number": 0, "remaining_pieces": session["target_pieces"]},
                *[
                    {
                        "piece_number": event["piece_number"],
                        "remaining_pieces": max(0, session["target_pieces"] - event["piece_number"]),
                    }
                    for event in pieces
                ],
            ],
            "device_configuration": serialize_configuration(get_configuration(connection)),
            "inference": application.state.vision.status(session_id),
        }

    @application.get("/api/analytics")
    def analytics(
        connection: Database,
        employee_id: int | None = None,
        session_id: int | None = None,
        sewing_line: str | None = None,
        start_date: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
        end_date: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
        session_mode: Annotated[str | None, Query(pattern=r"^(PRODUCTION|VALIDATION)$")] = None,
    ) -> dict[str, Any]:
        return build_analytics(
            connection, employee_id=employee_id, session_id=session_id,
            sewing_line=sewing_line, start_date=start_date, end_date=end_date,
            session_mode=session_mode,
        )

    @application.get("/api/analytics/export.xlsx")
    def export_analytics(
        connection: Database,
        employee_id: int | None = None,
        session_id: int | None = None,
        sewing_line: str | None = None,
        start_date: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
        end_date: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
        session_mode: Annotated[str | None, Query(pattern=r"^(PRODUCTION|VALIDATION)$")] = None,
    ) -> Response:
        payload = build_analytics(
            connection, employee_id=employee_id, session_id=session_id,
            sewing_line=sewing_line, start_date=start_date, end_date=end_date,
            session_mode=session_mode,
        )
        filename = f"Garment_Production_Analytics_{utc_now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return Response(
            content=build_workbook(payload),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return application


def run() -> None:
    import uvicorn

    port = int(os.environ.get("GARMENT_COUNTER_PORT", "0"))

    if not 1024 <= port <= 65535:
        raise RuntimeError("GARMENT_COUNTER_PORT must contain the allocated localhost port.")

    uvicorn.run(
        create_application(),
        host="127.0.0.1",
        port=port,
        access_log=False,
        log_level="warning",
        server_header=False,
        date_header=False,
    )


if __name__ == "__main__":
    run()
