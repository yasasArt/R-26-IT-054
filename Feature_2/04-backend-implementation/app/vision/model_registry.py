"""Centralized, fault-isolated model discovery and loading."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from app.config import Settings
from app.schemas.model import (
    ModelComponentStatus,
    ModelLoadState,
    ModelRegistryStatus,
)
from app.vision.classifier import (
    CLASS_NAMES,
    ModelDependencyError,
    load_classifier,
)
from app.vision.workstation_detector import (
    DetectorDependencyError,
    WorkstationDetector,
    default_yolo_factory,
)

logger = logging.getLogger(__name__)


class LabelMappingError(RuntimeError):
    """Raised when label indexes differ from the trained classifier."""


def select_device(requested: str = "auto", torch_module: Any | None = None) -> str:
    """Choose CUDA, Apple MPS or CPU without assuming accelerators exist."""

    if requested == "cpu":
        return "cpu"

    if torch_module is None:
        try:
            import torch as torch_module
        except ImportError:
            if requested != "auto":
                raise ModelDependencyError(
                    f"Cannot use {requested}: PyTorch is not installed"
                ) from None
            return "cpu"

    if requested == "cuda":
        if not torch_module.cuda.is_available():
            raise ModelDependencyError("CUDA was requested but is not available")
        return "cuda"

    mps_backend = getattr(getattr(torch_module, "backends", None), "mps", None)
    if requested == "mps":
        if mps_backend is None or not mps_backend.is_available():
            raise ModelDependencyError("Apple MPS was requested but is not available")
        return "mps"

    if torch_module.cuda.is_available():
        return "cuda"
    if mps_backend is not None and mps_backend.is_available():
        return "mps"
    return "cpu"


def load_label_mapping(path: Path) -> dict[int, str]:
    """Accept simple or wrapped JSON, then enforce the final two-class order."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LabelMappingError(f"Unable to read label mapping: {exc}") from exc

    if isinstance(raw, Mapping) and "idx_to_class" in raw:
        raw = raw["idx_to_class"]
    elif isinstance(raw, Mapping) and "class_to_idx" in raw:
        class_to_idx = raw["class_to_idx"]
        if not isinstance(class_to_idx, Mapping):
            raise LabelMappingError("class_to_idx must be a JSON object")
        raw = {str(index): name for name, index in class_to_idx.items()}

    if not isinstance(raw, Mapping):
        raise LabelMappingError("Label mapping must be a JSON object")
    try:
        mapping = {int(index): str(name) for index, name in raw.items()}
    except (TypeError, ValueError) as exc:
        raise LabelMappingError("Label indexes must be integers") from exc

    expected = dict(enumerate(CLASS_NAMES))
    if mapping != expected:
        raise LabelMappingError(
            f"Label mapping must be exactly {expected}, received {mapping}"
        )
    return mapping


def _initial_status(name: str, path: Path) -> ModelComponentStatus:
    return ModelComponentStatus(
        name=name,
        state=ModelLoadState.NOT_LOADED,
        path=str(path),
        loaded=False,
        message="Model loading has not started",
    )


def _missing_status(name: str, path: Path) -> ModelComponentStatus:
    return ModelComponentStatus(
        name=name,
        state=ModelLoadState.MISSING,
        path=str(path),
        loaded=False,
        message=f"Required file is missing: {path}",
    )


def _ready_status(name: str, path: Path, message: str) -> ModelComponentStatus:
    return ModelComponentStatus(
        name=name,
        state=ModelLoadState.READY,
        path=str(path),
        loaded=True,
        message=message,
    )


def _error_status(
    name: str,
    path: Path,
    exc: Exception,
) -> ModelComponentStatus:
    dependency_error = isinstance(exc, (ModelDependencyError, DetectorDependencyError))
    return ModelComponentStatus(
        name=name,
        state=(
            ModelLoadState.DEPENDENCY_MISSING
            if dependency_error
            else ModelLoadState.INVALID
        ),
        path=str(path),
        loaded=False,
        message=str(exc),
    )


ClassifierLoader = Callable[[Path, str], Any]


class ModelRegistry:
    """Own loaded models and expose one immutable status snapshot."""

    def __init__(
        self,
        settings: Settings,
        *,
        classifier_loader: ClassifierLoader = load_classifier,
        yolo_factory: Callable[[str], Any] = default_yolo_factory,
        torch_module: Any | None = None,
    ) -> None:
        self.settings = settings
        self._classifier_loader = classifier_loader
        self._yolo_factory = yolo_factory
        self._torch_module = torch_module
        self.classifier: Any | None = None
        self.workstation_detector: WorkstationDetector | None = None
        self.labels: dict[int, str] | None = None

        assert settings.classifier_checkpoint_path is not None
        assert settings.label_mapping_path is not None
        assert settings.workstation_checkpoint_path is not None
        self.classifier_path = settings.classifier_checkpoint_path
        self.label_mapping_path = settings.label_mapping_path
        self.workstation_path = settings.workstation_checkpoint_path
        self.device = "cpu"
        self._status = ModelRegistryStatus(
            ready=False,
            device=self.device,
            classifier=_initial_status("garment_classifier", self.classifier_path),
            label_mapping=_initial_status("classifier_labels", self.label_mapping_path),
            workstation_detector=_initial_status(
                "workstation_detector", self.workstation_path
            ),
        )

    @property
    def status(self) -> ModelRegistryStatus:
        return self._status.model_copy(deep=True)

    def load_all(self) -> ModelRegistryStatus:
        """Attempt every component and report failures instead of propagating them."""

        try:
            self.device = select_device(
                self.settings.model_device, torch_module=self._torch_module
            )
        except ModelDependencyError as exc:
            self.device = self.settings.model_device
            logger.warning("Model device selection failed: %s", exc)

        label_status = self._load_labels()
        classifier_status = self._load_classifier()
        detector_status = self._load_detector()
        ready = all(
            status.loaded
            for status in (label_status, classifier_status, detector_status)
        )
        self._status = ModelRegistryStatus(
            ready=ready,
            device=self.device,
            classifier=classifier_status,
            label_mapping=label_status,
            workstation_detector=detector_status,
        )
        return self.status

    def _load_labels(self) -> ModelComponentStatus:
        if not self.label_mapping_path.is_file():
            return _missing_status("classifier_labels", self.label_mapping_path)
        try:
            self.labels = load_label_mapping(self.label_mapping_path)
        except LabelMappingError as exc:
            self.labels = None
            return _error_status("classifier_labels", self.label_mapping_path, exc)
        return _ready_status(
            "classifier_labels",
            self.label_mapping_path,
            "Label indexes validated: 0=IDLE_SETUP, 1=SEWING",
        )

    def _load_classifier(self) -> ModelComponentStatus:
        if not self.classifier_path.is_file():
            return _missing_status("garment_classifier", self.classifier_path)
        try:
            self.classifier = self._classifier_loader(self.classifier_path, self.device)
        except Exception as exc:  # noqa: BLE001 - status must contain loader failures.
            self.classifier = None
            return _error_status("garment_classifier", self.classifier_path, exc)
        return _ready_status(
            "garment_classifier",
            self.classifier_path,
            "TemporalMobileNetV3Small architecture and checkpoint validated",
        )

    def _load_detector(self) -> ModelComponentStatus:
        if not self.workstation_path.is_file():
            return _missing_status("workstation_detector", self.workstation_path)
        try:
            self.workstation_detector = WorkstationDetector(
                self.workstation_path,
                device=self.device,
                yolo_factory=self._yolo_factory,
            )
        except Exception as exc:  # noqa: BLE001 - status must contain loader failures.
            self.workstation_detector = None
            return _error_status("workstation_detector", self.workstation_path, exc)
        return _ready_status(
            "workstation_detector",
            self.workstation_path,
            "YOLO workstation class mapping validated",
        )

    def unload(self) -> None:
        """Release registry-owned references during application shutdown."""

        self.classifier = None
        self.workstation_detector = None
        self.labels = None
