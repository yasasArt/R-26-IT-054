from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict #type:ignore


class Settings(BaseSettings):

    application_name: str = "Garment Counter Backend"
    application_version: str = "1.0.0"
    environment: Literal["development", "test", "production"] = "development"

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    app_data_dir: Path = Path("./data")
    database_path: Path | None = None
    models_dir: Path = Path("./models")
    minimum_piece_gap_seconds: float = Field(default=1.0, ge=0.1, le=60.0)

    load_models_on_startup: bool = True
    model_device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    classifier_checkpoint_path: Path | None = None
    label_mapping_path: Path | None = None
    workstation_checkpoint_path: Path | None = None

    # Authentication is implemented in Phase 11. We define the value now so
    # Electron can eventually provide a private token without changing Settings.
    api_token: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="GARMENT_COUNTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def normalize_paths(self) -> "Settings":

        self.app_data_dir = self.app_data_dir.expanduser().resolve()
        self.models_dir = self.models_dir.expanduser().resolve()

        if self.classifier_checkpoint_path is None:
            self.classifier_checkpoint_path = (
                self.models_dir / "final_idle_cycle" / "best_model.pt"
            )
        else:
            self.classifier_checkpoint_path = (
                self.classifier_checkpoint_path.expanduser().resolve()
            )

        if self.label_mapping_path is None:
            self.label_mapping_path = (
                self.models_dir / "final_idle_cycle" / "label_mapping.json"
            )
        else:
            self.label_mapping_path = self.label_mapping_path.expanduser().resolve()

        if self.workstation_checkpoint_path is None:
            self.workstation_checkpoint_path = (
                self.models_dir / "workstation_detector" / "best.pt"
            )
        else:
            self.workstation_checkpoint_path = (
                self.workstation_checkpoint_path.expanduser().resolve()
            )

        if self.database_path is None:
            self.database_path = self.app_data_dir / "garment_counter.db"
        else:
            self.database_path = self.database_path.expanduser().resolve()

        return self

    def ensure_directories(self) -> None:

        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        assert self.database_path is not None
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:

    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
