from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

EXPECTED_CLASS_NAME = "workstation"


@dataclass(frozen=True, slots=True)
class WorkstationLatchUpdate:
    state: str
    available: bool
    failed_rechecks: int
    newly_latched: bool = False
    paused: bool = False
    reacquired: bool = False


class WorkstationLatch:
    """Confirm, latch, periodically recheck and safely reacquire a workstation."""

    SEARCHING = "SEARCHING"
    LATCHED = "LATCHED"
    PAUSED = "PAUSED"

    def __init__(
        self,
        *,
        confirmations_required: int = 3,
        initial_check_interval_seconds: float = 0.5,
        recheck_interval_seconds: float = 5.0,
        allowed_failed_rechecks: int = 2,
    ) -> None:
        if confirmations_required < 1:
            raise ValueError("confirmations_required must be at least 1")
        if initial_check_interval_seconds < 0:
            raise ValueError("initial_check_interval_seconds cannot be negative")
        if recheck_interval_seconds <= 0:
            raise ValueError("recheck_interval_seconds must be positive")
        if allowed_failed_rechecks < 0:
            raise ValueError("allowed_failed_rechecks cannot be negative")
        self.confirmations_required = confirmations_required
        self.initial_check_interval_seconds = initial_check_interval_seconds
        self.recheck_interval_seconds = recheck_interval_seconds
        self.allowed_failed_rechecks = allowed_failed_rechecks
        self.reset()

    def reset(self) -> None:
        self.state = self.SEARCHING
        self.consecutive_detections = 0
        self.failed_rechecks = 0
        self.last_checked_at: datetime | None = None

    @property
    def available(self) -> bool:
        return self.state == self.LATCHED

    def should_check(self, observed_at: datetime) -> bool:
        if self.last_checked_at is None:
            return True
        interval = (
            self.recheck_interval_seconds
            if self.state == self.LATCHED
            else self.initial_check_interval_seconds
        )
        return (observed_at - self.last_checked_at).total_seconds() >= interval

    def observe(self, detected: bool, observed_at: datetime) -> WorkstationLatchUpdate:
        previous_state = self.state
        self.last_checked_at = observed_at

        if self.state == self.LATCHED:
            if detected:
                self.failed_rechecks = 0
            else:
                self.failed_rechecks += 1
                if self.failed_rechecks > self.allowed_failed_rechecks:
                    self.state = self.PAUSED
                    self.consecutive_detections = 0
        elif detected:
            self.consecutive_detections += 1
            if self.consecutive_detections >= self.confirmations_required:
                self.state = self.LATCHED
                self.failed_rechecks = 0
        else:
            self.consecutive_detections = 0

        newly_latched = previous_state == self.SEARCHING and self.state == self.LATCHED
        reacquired = previous_state == self.PAUSED and self.state == self.LATCHED
        paused = previous_state == self.LATCHED and self.state == self.PAUSED
        return WorkstationLatchUpdate(
            state=self.state,
            available=self.available,
            failed_rechecks=self.failed_rechecks,
            newly_latched=newly_latched,
            paused=paused,
            reacquired=reacquired,
        )


class DetectorDependencyError(RuntimeError):
    """Raised when Ultralytics is not installed."""


class DetectorCheckpointError(RuntimeError):
    """Raised when the detector checkpoint is invalid for this application."""


def default_yolo_factory(checkpoint_path: str) -> Any:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise DetectorDependencyError(
            "Ultralytics is required to load the workstation detector"
        ) from exc
    return YOLO(checkpoint_path)


def _normalized_names(names: Any) -> dict[int, str]:
    if isinstance(names, Mapping):
        return {int(index): str(name) for index, name in names.items()}
    if isinstance(names, (list, tuple)):
        return {index: str(name) for index, name in enumerate(names)}
    raise DetectorCheckpointError("YOLO checkpoint does not expose class names")


class WorkstationDetector:
    """Validated single-class YOLO detector wrapper."""

    def __init__(
        self,
        checkpoint_path: Path,
        *,
        device: str,
        yolo_factory: Callable[[str], Any] = default_yolo_factory,
    ) -> None:
        try:
            self.model = yolo_factory(str(checkpoint_path))
        except (DetectorDependencyError, DetectorCheckpointError):
            raise
        except Exception as exc:
            raise DetectorCheckpointError(
                f"Unable to load workstation detector checkpoint: {exc}"
            ) from exc

        self.names = _normalized_names(getattr(self.model, "names", None))
        if self.names != {0: EXPECTED_CLASS_NAME}:
            raise DetectorCheckpointError(
                "YOLO class mapping must be exactly {0: 'workstation'}, "
                f"received {self.names}"
            )

        self.device = device
        if hasattr(self.model, "to"):
            self.model.to(device)
        underlying = getattr(self.model, "model", None)
        if underlying is not None and hasattr(underlying, "eval"):
            underlying.eval()

    def predict(self, image: Any, *, confidence: float = 0.25) -> list[dict[str, Any]]:
        """Return stable, JSON-friendly workstation detections."""

        results = self.model.predict(
            source=image,
            conf=confidence,
            device=self.device,
            verbose=False,
        )
        detections: list[dict[str, Any]] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            xyxy_values = boxes.xyxy.tolist()
            confidence_values = boxes.conf.tolist()
            class_values = boxes.cls.tolist()
            for xyxy, score, class_id in zip(
                xyxy_values, confidence_values, class_values, strict=True
            ):
                class_index = int(class_id)
                detections.append(
                    {
                        "class_id": class_index,
                        "class_name": self.names[class_index],
                        "confidence": float(score),
                        "xyxy": [float(value) for value in xyxy],
                    }
                )
        return detections
