import sqlite3

from app.db.transaction import transaction
from app.errors import ConflictError, ResourceNotFoundError
from app.repositories.configuration_repository import ConfigurationRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.session import (
    SessionCreate,
    SessionMode,
    SessionReadinessResponse,
    SessionResponse,
)
from app.time_utils import utc_now_iso


class SessionService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.sessions = SessionRepository(connection)
        self.employees = EmployeeRepository(connection)
        self.configuration = ConfigurationRepository(connection)

    @staticmethod
    def _device_readiness(
        session_mode: SessionMode,
        configuration: dict,
        *,
        no_active_session: bool,
    ) -> SessionReadinessResponse:
        camera_ready = bool(
            configuration["camera_index"] is not None
            and configuration["camera_label"]
            and configuration["camera_tested"]
        )
        controller_required = session_mode is SessionMode.PRODUCTION
        controller_ready = bool(
            configuration["controller_device_id"]
            and configuration["controller_name"]
            and configuration["controller_connected"]
        )

        blockers: list[str] = []
        if not no_active_session:
            blockers.append("Complete the current active session first")
        if not camera_ready:
            blockers.append("Select and successfully test the sewing camera")
        if controller_required and not controller_ready:
            blockers.append("Connect and verify the operator controller")

        return SessionReadinessResponse(
            session_mode=session_mode,
            ready=not blockers,
            no_active_session=no_active_session,
            camera_ready=camera_ready,
            controller_required=controller_required,
            controller_ready=controller_ready,
            blockers=blockers,
        )

    def readiness(self, session_mode: SessionMode) -> SessionReadinessResponse:
        return self._device_readiness(
            session_mode,
            self.configuration.get(),
            no_active_session=self.sessions.find_active() is None,
        )

    def create(self, payload: SessionCreate) -> SessionResponse:

        try:
            with transaction(self.connection):
                if self.sessions.find_active() is not None:
                    raise ConflictError("Another production session is already active")

                employee = self.employees.find_by_id(payload.employee_id)
                if employee is None:
                    raise ResourceNotFoundError(
                        f"Employee {payload.employee_id} was not found"
                    )
                if not employee["is_active"]:
                    raise ConflictError("Select an active employee")

                configuration = self.configuration.get()
                readiness = self._device_readiness(
                    payload.session_mode,
                    configuration,
                    no_active_session=True,
                )
                if not readiness.ready:
                    raise ConflictError("; ".join(readiness.blockers))

                timestamp = utc_now_iso()
                record = self.sessions.create(
                    employee=employee,
                    configuration=configuration,
                    target_pieces=payload.target_pieces,
                    session_mode=payload.session_mode.value,
                    timestamp=timestamp,
                )
        except sqlite3.IntegrityError as error:
            if "production_sessions.status" in str(error):
                raise ConflictError("Another production session is already active") from error
            raise

        return SessionResponse.model_validate(record)

    def get(self, session_id: int) -> SessionResponse:
        record = self.sessions.find_by_id(session_id)
        if record is None:
            raise ResourceNotFoundError(f"Session {session_id} was not found")
        return SessionResponse.model_validate(record)

    def active(self) -> SessionResponse | None:
        record = self.sessions.find_active()
        return SessionResponse.model_validate(record) if record is not None else None

    def list(self) -> list[SessionResponse]:
        return [
            SessionResponse.model_validate(record)
            for record in self.sessions.list()
        ]

    def complete(self, session_id: int) -> SessionResponse:
        with transaction(self.connection):
            existing = self.sessions.find_by_id(session_id)
            if existing is None:
                raise ResourceNotFoundError(f"Session {session_id} was not found")
            if existing["status"] != "ACTIVE":
                raise ConflictError("Only an active session can be completed")

            record = self.sessions.complete_active(session_id, utc_now_iso())
            if record is None:
                raise ConflictError("The session is no longer active")

        return SessionResponse.model_validate(record)
