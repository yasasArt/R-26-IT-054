import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict # type: ignore


def default_models_dir() -> Path:
    """Use PyInstaller's extraction directory when running a bundled binary."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundle_root:
        return Path(bundle_root) / "models"
    return Path("./models")


class Settings(BaseSettings):

    application_name: str = "Garment Counter Backend"
    application_version: str = "1.0.0"
    environment: Literal["development", "test", "production"] = "development"

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    app_data_dir: Path = Path("./data")
    database_path: Path | None = None
    models_dir: Path = Field(default_factory=default_models_dir)
    minimum_piece_gap_seconds: float = Field(default=1.0, ge=0.1, le=60.0)

    load_models_on_startup: bool = True
    model_device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    classifier_checkpoint_path: Path | None = None
    label_mapping_path: Path | None = None
    workstation_checkpoint_path: Path | None = None

    vision_probability_window: int = Field(default=5, ge=1, le=60)
    vision_confidence_threshold: float = Field(default=0.70, ge=0.5, le=1.0)
    vision_minimum_probability_margin: float = Field(default=0.15, ge=0.0, le=1.0)
    vision_state_confirmation_frames: int = Field(default=3, ge=1, le=60)
    vision_minimum_sewing_seconds: float = Field(default=1.0, gt=0.0, le=600.0)
    vision_minimum_idle_seconds: float = Field(default=0.5, ge=0.0, le=60.0)
    vision_cooldown_seconds: float = Field(default=1.5, ge=0.0, le=60.0)
    vision_clip_seconds: float = Field(default=1.5, gt=0.0, le=10.0)
    vision_inference_interval_seconds: float = Field(default=0.3, gt=0.0, le=10.0)
    workstation_initial_confirmations: int = Field(default=3, ge=1, le=20)
    workstation_initial_check_interval_seconds: float = Field(
        default=0.5, ge=0.0, le=30.0
    )
    workstation_recheck_interval_seconds: float = Field(
        default=5.0, gt=0.0, le=300.0
    )
    workstation_allowed_failed_rechecks: int = Field(default=2, ge=0, le=20)
    vision_preview_wait_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    vision_preview_jpeg_quality: int = Field(default=80, ge=30, le=100)
    vision_video_realtime_playback: bool = True
    vision_upload_max_bytes: int = Field(
        default=2 * 1024 * 1024 * 1024,
        ge=1024,
        le=20 * 1024 * 1024 * 1024,
    )

    api_token: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_prefix="GARMENT_COUNTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("api_token")
    @classmethod
    def validate_api_token(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        length = len(value.get_secret_value())
        if length < 32:
            raise ValueError("API token must contain at least 32 characters")
        if length > 512:
            raise ValueError("API token cannot exceed 512 characters")
        return value

    @model_validator(mode="after")
    def normalize_paths(self) -> "Settings":

        if self.environment == "production" and self.host != "127.0.0.1":
            raise ValueError("Production backend must bind to 127.0.0.1")

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
        self.video_upload_dir.mkdir(parents=True, exist_ok=True)
        assert self.database_path is not None
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def video_upload_dir(self) -> Path:
        """Private directory for validation videos uploaded through the API."""

        return self.app_data_dir / "video_uploads"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one cached settings object for the running process."""

    return Settings()


def clear_settings_cache() -> None:
    """Clear cached settings, mainly for tests that change environment values."""

    get_settings.cache_clear()
