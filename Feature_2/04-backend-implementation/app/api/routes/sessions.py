"""Production-session lifecycle endpoints."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.dependencies import DatabaseDependency
from app.schemas.session import (
    SessionCreate,
    SessionMode,
    SessionReadinessResponse,
    SessionResponse,
)
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["Production sessions"])


@router.get("/readiness", response_model=SessionReadinessResponse)
def session_readiness(
    connection: DatabaseDependency,
    session_mode: Annotated[SessionMode, Query()] = SessionMode.PRODUCTION,
) -> SessionReadinessResponse:
    return SessionService(connection).readiness(session_mode)


@router.get("/active", response_model=SessionResponse | None)
def get_active_session(connection: DatabaseDependency) -> SessionResponse | None:
    return SessionService(connection).active()


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    connection: DatabaseDependency,
) -> SessionResponse:
    return SessionService(connection).create(payload)


@router.get("", response_model=list[SessionResponse])
def list_sessions(connection: DatabaseDependency) -> list[SessionResponse]:
    return SessionService(connection).list()


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: int,
    connection: DatabaseDependency,
) -> SessionResponse:
    return SessionService(connection).get(session_id)


@router.post("/{session_id}/complete", response_model=SessionResponse)
def complete_session(
    session_id: int,
    connection: DatabaseDependency,
) -> SessionResponse:
    return SessionService(connection).complete(session_id)
