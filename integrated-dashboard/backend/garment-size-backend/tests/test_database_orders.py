"""SQLite order persistence tests that do not load the YOLO model."""

import importlib
import json
import sqlite3
import sys


def load_isolated_database(monkeypatch, tmp_path):
    monkeypatch.setenv("THREADSCAN_DATA_DIR", str(tmp_path))
    sys.modules.pop("database", None)
    module = importlib.import_module("database")
    module.initialize_database()
    return module


def order_payload(measurement_session_id: int) -> dict:
    return {
        "id": "SES-TEST-001",
        "orderId": "ORD-TEST-001",
        "garmentType": "T-Shirt",
        "status": "active",
        "schedule": {
            "garmentType": "T-Shirt",
            "orderId": "ORD-TEST-001",
            "startDate": "2026-08-30",
            "endDate": "2026-08-31",
            "shiftStart": "08:00",
            "shiftEnd": "17:00",
            "targets": {"S": 10, "M": 0, "L": 0, "XL": 0},
            "breaks": [],
        },
        "packed": {"S": 0, "M": 0, "L": 0, "XL": 0},
        "carriedCounts": {"S": 0, "M": 0, "L": 0, "XL": 0},
        "baselineCounts": {"S": 0, "M": 0, "L": 0, "XL": 0},
        "measurementSessionId": measurement_session_id,
        "createdAt": "2026-08-30T00:00:00+00:00",
        "startedAt": "2026-08-30T00:00:00+00:00",
        "activeStartedAt": "2026-08-30T00:00:00+00:00",
        "accumulatedMinutes": 0,
    }


def test_order_create_update_and_database_delete(monkeypatch, tmp_path):
    database = load_isolated_database(monkeypatch, tmp_path)
    counter_session = database.start_new_session()
    order = order_payload(counter_session)

    saved = database.save_production_order(order)
    assert saved["orderId"] == "ORD-TEST-001"

    order["status"] = "paused"
    order["packed"]["S"] = 3
    order["endedAt"] = "2026-08-30T01:00:00+00:00"
    updated = database.save_production_order(order)
    assert updated["packed"]["S"] == 3

    result = database.delete_production_order(order["id"])
    assert result["deleted"] is True
    assert database.get_production_orders() == []


def test_active_order_cannot_be_deleted(monkeypatch, tmp_path):
    database = load_isolated_database(monkeypatch, tmp_path)
    order = order_payload(database.start_new_session())
    database.save_production_order(order)

    try:
        database.delete_production_order(order["id"])
    except ValueError as error:
        assert "active order" in str(error)
    else:
        raise AssertionError("An active order was deleted")


def test_pre_v31_order_database_is_migrated_in_place(monkeypatch, tmp_path):
    database_path = tmp_path / "garment_measurements.db"
    schedule = order_payload(1)["schedule"]
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE production_orders (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL UNIQUE,
                garment_type TEXT NOT NULL,
                status TEXT NOT NULL,
                schedule_json TEXT NOT NULL,
                packed_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO production_orders(
                id, order_id, garment_type, status, schedule_json,
                packed_json, created_at, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "SES-LEGACY",
                "ORD-LEGACY",
                "T-Shirt",
                "paused",
                json.dumps(schedule),
                json.dumps({"S": 2}),
                "2026-08-29T00:00:00+00:00",
                "2026-08-29T00:00:00+00:00",
            ),
        )

    database = load_isolated_database(monkeypatch, tmp_path)
    migrated = database.get_production_orders()[0]
    assert migrated["orderId"] == "ORD-LEGACY"
    assert migrated["activeStartedAt"] == "2026-08-29T00:00:00+00:00"
    assert migrated["carriedCounts"] == {}
