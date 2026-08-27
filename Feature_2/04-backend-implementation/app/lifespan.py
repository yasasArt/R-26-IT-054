"""FastAPI startup and shutdown lifecycle."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.config import Settings
from app.db.migrations import initialize_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def application_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare process resources and release them during shutdown.

    Database initialization and model loading will be added to this lifecycle
    in later phases. Keeping those responsibilities here prevents import-time
    side effects and makes application tests easy to isolate.
    """

    settings: Settings = app.state.settings
    settings.ensure_directories()

    app.state.started_at = datetime.now(UTC)
    app.state.service_ready = False
    app.state.database_ready = False

    assert settings.database_path is not None
    schema_version = initialize_database(settings.database_path)
    app.state.schema_version = schema_version
    app.state.database_ready = True
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
        app.state.service_ready = False
        app.state.database_ready = False
        logger.info("Garment Counter backend stopped")
