from fastapi import APIRouter

from app.api.routes.configuration import router as configuration_router
from app.api.routes.employees import router as employees_router
from app.api.routes.health import router as health_router
from app.api.routes.piece_events import router as piece_events_router
from app.api.routes.sessions import router as sessions_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(employees_router)
api_router.include_router(configuration_router)
api_router.include_router(sessions_router)
api_router.include_router(piece_events_router)
