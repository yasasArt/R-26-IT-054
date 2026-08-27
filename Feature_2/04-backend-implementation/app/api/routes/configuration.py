"""User-editable camera and controller selection endpoints."""

from fastapi import APIRouter

from app.api.dependencies import DatabaseDependency
from app.schemas.configuration import (
    DeviceConfigurationResponse,
    DeviceConfigurationUpdate,
)
from app.services.configuration_service import ConfigurationService

router = APIRouter(prefix="/configuration", tags=["Device configuration"])


@router.get("", response_model=DeviceConfigurationResponse)
def get_configuration(connection: DatabaseDependency) -> DeviceConfigurationResponse:
    return ConfigurationService(connection).get()


@router.put("", response_model=DeviceConfigurationResponse)
def update_configuration(
    payload: DeviceConfigurationUpdate,
    connection: DatabaseDependency,
) -> DeviceConfigurationResponse:
    return ConfigurationService(connection).update(payload)
