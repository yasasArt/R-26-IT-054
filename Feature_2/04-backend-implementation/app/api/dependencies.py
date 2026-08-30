import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.db.connection import connect_database


def get_request_settings(request: Request) -> Settings:

    return request.app.state.settings


SettingsDependency = Annotated[Settings, Depends(get_request_settings)]


def get_database_connection(request: Request) -> Iterator[sqlite3.Connection]:

    settings = get_request_settings(request)
    assert settings.database_path is not None
    connection = connect_database(settings.database_path)
    try:
        yield connection
    finally:
        connection.close()


DatabaseDependency = Annotated[
    sqlite3.Connection,
    Depends(get_database_connection),
]
