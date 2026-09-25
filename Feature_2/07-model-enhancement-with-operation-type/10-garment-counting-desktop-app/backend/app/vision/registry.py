from __future__ import annotations

import os
import logging
import threading
from dataclasses import asdict, dataclass
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ModelStatus:
    state: str = "NOT_LOADED"
    message: str = "The trained model has not been loaded yet."
    device: str | None = None


class VisionModelRegistry:
    """Load and warm both genuine checkpoints without delaying FastAPI startup."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.detector: Any | None = None
        self.classifier: Any | None = None
        self._detector_status = ModelStatus()
        self._classifier_status = ModelStatus()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            detector = asdict(self._detector_status)
            classifier = asdict(self._classifier_status)
        return {
            "detector": detector,
            "classifier": classifier,
            "ready": detector["state"] == "READY" and classifier["state"] == "READY",
        }

    @property
    def ready(self) -> bool:
        return bool(self.snapshot()["ready"])

    def install_models(self, detector: Any, classifier: Any, device: str = "cpu") -> None:
        """Allow a controlled test harness to install equivalent model doubles."""

        with self._lock:
            self.detector = detector
            self.classifier = classifier
            self._detector_status = ModelStatus("READY", "The workstation detector is ready.", device)
            self._classifier_status = ModelStatus("READY", "The garment classifier is ready.", device)

    def start_loading(self) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.snapshot()
            if self.detector is not None and self.classifier is not None:
                return self.snapshot()
            self._detector_status = ModelStatus("LOADING", "Loading the trained workstation detector…")
            self._classifier_status = ModelStatus("LOADING", "Loading the trained garment classifier…")
            self._thread = threading.Thread(
                target=self._load_models,
                name="garment-model-loader",
                daemon=True,
            )
            self._thread.start()
            return self.snapshot()

    def _load_models(self) -> None:
        config_directory = self.settings.data_directory / "ultralytics"
        config_directory.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(config_directory))

        try:
            from app.vision.detector import WorkstationDetector

            detector = WorkstationDetector(self.settings.model_directory / "best.pt")
            detector.warmup()
            with self._lock:
                self.detector = detector
                self._detector_status = ModelStatus(
                    "READY", "The real trained workstation detector is loaded and verified."
                )
        except Exception as error:
            logger.exception("The trained workstation detector could not be loaded")
            with self._lock:
                self.detector = None
                self._detector_status = ModelStatus("FAILED", self._safe_error("Workstation detector", error))

        try:
            from app.vision.classifier import GarmentClassifier

            classifier = GarmentClassifier(
                self.settings.model_directory / "best_model.pt",
                self.settings.model_directory / "label_mapping.json",
            )
            classifier.warmup()
            with self._lock:
                self.classifier = classifier
                self._classifier_status = ModelStatus(
                    "READY",
                    "The real temporal garment classifier is loaded and verified.",
                    str(classifier.device),
                )
        except Exception as error:
            logger.exception("The trained garment classifier could not be loaded")
            with self._lock:
                self.classifier = None
                self._classifier_status = ModelStatus("FAILED", self._safe_error("Garment classifier", error))

    @staticmethod
    def _safe_error(component: str, error: Exception) -> str:
        if isinstance(error, ModuleNotFoundError):
            return (
                f"{component} requires the missing Python package '{error.name}'. "
                "Install the Phase 3 backend vision dependencies and restart the desktop app."
            )
        if isinstance(error, FileNotFoundError):
            return str(error)
        message = str(error).splitlines()[0][:220]
        return f"{component} could not be verified: {message}"
