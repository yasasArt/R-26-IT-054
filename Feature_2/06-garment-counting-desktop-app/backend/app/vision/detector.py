from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkstationDetection:
    visible: bool
    confidence: float = 0.0
    bbox: tuple[int, int, int, int] | None = None
    label: str | None = None
    message: str = "The sewing workstation is not visible."

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.bbox is not None:
            payload["bbox"] = list(self.bbox)
        return payload


class WorkstationDetector:
    def __init__(
        self,
        checkpoint_path: Path,
        threshold: float = 0.5,
        image_size: int = 640,
        device: str = "auto",
    ) -> None:
        if not checkpoint_path.is_file():
            raise FileNotFoundError("The trained workstation checkpoint best.pt is missing.")

        from ultralytics import YOLO

        self.threshold = threshold
        self.image_size = image_size
        self.device = None if device == "auto" else device
        self.model = YOLO(str(checkpoint_path), task="detect")
        names = getattr(self.model, "names", {})
        normalized = {str(value).strip().lower() for value in names.values()}
        if "workstation" not in normalized:
            raise ValueError("The YOLO checkpoint does not contain the required workstation class.")

    def warmup(self) -> None:
        import numpy as np

        self.detect(np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8))

    def detect(self, frame: Any) -> WorkstationDetection:
        results = self.model.predict(
            source=frame,
            imgsz=self.image_size,
            conf=self.threshold,
            device=self.device,
            verbose=False,
            save=False,
        )
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return WorkstationDetection(False)

        boxes = results[0].boxes
        names = getattr(results[0], "names", getattr(self.model, "names", {}))
        candidates: list[tuple[float, int, str]] = []
        for index in range(len(boxes)):
            class_id = int(boxes.cls[index].detach().cpu().item())
            label = str(names.get(class_id, ""))
            confidence = float(boxes.conf[index].detach().cpu().item())
            if label.strip().lower() == "workstation" and confidence >= self.threshold:
                candidates.append((confidence, index, label))

        if not candidates:
            return WorkstationDetection(False)

        confidence, index, label = max(candidates, key=lambda candidate: candidate[0])
        coordinates = boxes.xyxy[index].detach().cpu().tolist()
        bbox = tuple(int(round(value)) for value in coordinates)
        return WorkstationDetection(
            visible=True,
            confidence=confidence,
            bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
            label=label,
            message="The sewing workstation is visible and verified.",
        )

