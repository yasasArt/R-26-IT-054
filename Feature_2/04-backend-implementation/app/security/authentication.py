from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies import SettingsDependency
from app.errors import ServiceUnavailableError, UnauthorizedError

bearer_scheme = HTTPBearer(auto_error=False)


def require_api_token(
    settings: SettingsDependency,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ] = None,
) -> None:
    """Accept only the private token injected into Electron's backend process.

    ``compare_digest`` avoids content-dependent comparison timing. The token is
    never returned by the API and is never made available to the renderer.
    """

    configured = settings.api_token
    if configured is None:
        raise ServiceUnavailableError("API authentication is not configured")
    expected = configured.get_secret_value()

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not hmac.compare_digest(credentials.credentials, expected)
    ):
        raise UnauthorizedError("A valid private API token is required")
