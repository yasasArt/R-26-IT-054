"""FastAPI startup and shutdown lifecycle."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime # type: ignore

from fastapi import FastAPI

from app.config import Settings
from app.db.migrations import initialize_database
from app.vision.model_registry import ModelRegistry
from app.vision.vision_runtime import VisionRuntime

logger = logging.getLogger(__name__)


@asynccontextmanager
async def application_lifespan(app: FastAPI) -> AsyncIterator[None]:

    settings: Settings = app.state.settings
    settings.ensure_directories()

    app.state.started_at = datetime.now(UTC)
    app.state.service_ready = False
    app.state.database_ready = False
    app.state.models_ready = False

    assert settings.database_path is not None
    schema_version = initialize_database(settings.database_path)
    app.state.schema_version = schema_version
    app.state.database_ready = True

    model_registry = ModelRegistry(settings)
    app.state.model_registry = model_registry
    if settings.load_models_on_startup:
        model_status = model_registry.load_all()
        app.state.models_ready = model_status.ready
    vision_runtime = VisionRuntime(settings, model_registry)
    app.state.vision_runtime = vision_runtime
    app.state.service_ready = True

    logger.info(
        "Starting %s version %s in %s mode",
        settings.application_name,
        settings.application_version,
        settings.environment,
    )

    try:
        yield
    finally:
        vision_runtime.stop()
        model_registry.unload()
        app.state.service_ready = False
        app.state.database_ready = False
        app.state.models_ready = False
        logger.info("Garment Counter backend stopped")
