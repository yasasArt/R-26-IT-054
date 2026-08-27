"""Device-selection rules and safe connection-state resets."""

import sqlite3

from app.db.transaction import transaction
from app.errors import ConflictError, InvalidOperationError
from app.repositories.configuration_repository import ConfigurationRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.configuration import (
    DeviceConfigurationResponse,
    DeviceConfigurationUpdate,
)
from app.time_utils import utc_now_iso


class ConfigurationService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.repository = ConfigurationRepository(connection)

    def get(self) -> DeviceConfigurationResponse:
        return DeviceConfigurationResponse.model_validate(self.repository.get())

    def update(
        self,
        payload: DeviceConfigurationUpdate,
    ) -> DeviceConfigurationResponse:
        with transaction(self.connection):
            if SessionRepository(self.connection).find_active() is not None:
                raise ConflictError(
                    "Device configuration cannot change during an active session"
                )

            current = self.repository.get()
            changes = payload.model_dump(exclude_unset=True)
            supplied = payload.model_fields_set

            camera_changed = bool({"camera_index", "camera_label"} & supplied)
            if camera_changed:
                effective_index = changes.get("camera_index", current["camera_index"])
                effective_label = changes.get("camera_label", current["camera_label"])

                if effective_index is None:
                    changes["camera_label"] = None
                elif effective_label is None:
                    raise InvalidOperationError(
                        "A camera label is required when a camera index is selected"
                    )

                changes["camera_tested"] = 0

            controller_changed = bool(
                {"controller_device_id", "controller_name"} & supplied
            )
            if controller_changed:
                effective_id = changes.get(
                    "controller_device_id", current["controller_device_id"]
                )
                effective_name = changes.get(
                    "controller_name", current["controller_name"]
                )

                if effective_id is None:
                    changes["controller_name"] = None
                elif effective_name is None:
                    raise InvalidOperationError(
                        "A controller name is required when a controller is selected"
                    )

                changes["controller_connected"] = 0

            changes["updated_at"] = utc_now_iso()
            record = self.repository.update(changes)

        return DeviceConfigurationResponse.model_validate(record)
