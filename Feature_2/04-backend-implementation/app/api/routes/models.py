from fastapi import APIRouter, Request

from app.schemas.model import ModelRegistryStatus

router = APIRouter(prefix="/models", tags=["Models"])


@router.get(
    "/status",
    response_model=ModelRegistryStatus,
    summary="Report classifier and detector loading status",
)
def model_status(request: Request) -> ModelRegistryStatus:

    return request.app.state.model_registry.status
