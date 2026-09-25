from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    auth_token: str
    data_directory: Path
    model_directory: Path
    application_name: str = "Garment Counter"
    environment: str = "desktop"

    @property
    def database_path(self) -> Path:
        return self.data_directory / "garment-counter.sqlite3"

    @classmethod
    def from_environment(cls) -> "Settings":
        auth_token = os.environ.get("GARMENT_COUNTER_AUTH_TOKEN", "").strip()

        if len(auth_token) < 24:
            raise RuntimeError(
                "GARMENT_COUNTER_AUTH_TOKEN must be a randomly generated value "
                "with at least 24 characters. Start the service through Electron."
            )

        data_directory = os.environ.get("GARMENT_COUNTER_DATA_DIR", "").strip()

        if not data_directory:
            raise RuntimeError("GARMENT_COUNTER_DATA_DIR was not provided by Electron.")

        model_directory = os.environ.get("GARMENT_COUNTER_MODEL_DIR", "").strip()

        if not model_directory:
            raise RuntimeError("GARMENT_COUNTER_MODEL_DIR was not provided by Electron.")

        return cls(
            auth_token=auth_token,
            data_directory=Path(data_directory).expanduser().resolve(),
            model_directory=Path(model_directory).expanduser().resolve(),
            environment=os.environ.get("GARMENT_COUNTER_ENVIRONMENT", "desktop"),
        )
