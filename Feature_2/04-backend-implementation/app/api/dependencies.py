from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings


def get_request_settings(request: Request) -> Settings:

    return request.app.state.settings


SettingsDependency = Annotated[Settings, Depends(get_request_settings)]
