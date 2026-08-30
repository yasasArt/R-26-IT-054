"""SQL access for the singleton device-configuration row."""

import sqlite3
from collections.abc import Mapping


class ConfigurationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self) -> dict:
        row = self.connection.execute(
            "SELECT * FROM device_configuration WHERE id = 1"
        ).fetchone()
        if row is None:
            raise LookupError("The singleton device configuration is missing")
        return dict(row)

    def update(self, changes: Mapping[str, object]) -> dict:
        allowed_columns = {
            "camera_index",
            "camera_label",
            "camera_tested",
            "controller_device_id",
            "controller_name",
            "controller_connected",
            "updated_at",
        }
        unknown_columns = set(changes) - allowed_columns
        if unknown_columns:
            raise ValueError(f"Unsupported configuration columns: {sorted(unknown_columns)}")
        if not changes:
            return self.get()

        assignments = ", ".join(f"{column} = ?" for column in changes)
        self.connection.execute(
            f"UPDATE device_configuration SET {assignments} WHERE id = 1",
            list(changes.values()),
        )
        return self.get()
