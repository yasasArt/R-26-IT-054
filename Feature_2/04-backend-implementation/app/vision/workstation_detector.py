from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

EXPECTED_CLASS_NAME = "workstation"


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
