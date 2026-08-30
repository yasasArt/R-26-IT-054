from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta # type: ignore
from pathlib import Path
from typing import Any

import numpy as np

from app.schemas.vision import VisionSourceType


class CaptureDependencyError(RuntimeError):
    """Raised when OpenCV is not installed."""


class CaptureOpenError(RuntimeError):
    """Raised when a camera or video cannot be opened or decoded."""


def _opencv() -> Any:
    try:
        import cv2
    except (ImportError, RuntimeError) as exc:
        raise CaptureDependencyError(
            "OpenCV is required for camera and video capture"
        ) from exc
    return cv2


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    image: np.ndarray
    index: int
    observed_at: datetime
    source_position_seconds: float


CaptureFactory = Callable[[int | str], Any]


class CameraManager:
    """Own exactly one VideoCapture and release it idempotently."""

    def __init__(
        self,
        *,
        source_type: VisionSourceType,
        camera_index: int | None = None,
        video_path: Path | None = None,
        capture_factory: CaptureFactory | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if source_type == VisionSourceType.CAMERA and camera_index is None:
            raise ValueError("camera_index is required for a camera source")
        if source_type == VisionSourceType.VIDEO and video_path is None:
            raise ValueError("video_path is required for a video source")
        self.source_type = source_type
        self.camera_index = camera_index
        self.video_path = video_path
        self._capture_factory = capture_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._capture: Any | None = None
        self._frame_index = 0
        self._fps = 30.0
        self._opened_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self._capture is not None

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def source_label(self) -> str:
        if self.source_type == VisionSourceType.CAMERA:
            return f"camera:{self.camera_index}"
        assert self.video_path is not None
        return f"video:{self.video_path.name}"

    def open(self) -> None:
        if self._capture is not None:
            raise CaptureOpenError("Capture source is already open")
        cv2 = _opencv()
        source: int | str
        if self.source_type == VisionSourceType.CAMERA:
            assert self.camera_index is not None
            source = self.camera_index
        else:
            assert self.video_path is not None
            if not self.video_path.is_file():
                raise CaptureOpenError(f"Video file does not exist: {self.video_path}")
            source = str(self.video_path)

        factory = self._capture_factory or cv2.VideoCapture
        capture = factory(source)
        if capture is None or not capture.isOpened():
            if capture is not None and hasattr(capture, "release"):
                capture.release()
            raise CaptureOpenError(f"Unable to open {self.source_label}")

        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        self._fps = fps if 0.1 <= fps <= 240.0 else 30.0
        self._capture = capture
        self._opened_at = self._clock().astimezone(UTC)
        self._frame_index = 0

    def read(self) -> CapturedFrame | None:
        if self._capture is None or self._opened_at is None:
            raise CaptureOpenError("Capture source is not open")
        success, image = self._capture.read()
        if not success or image is None:
            return None

        if self.source_type == VisionSourceType.VIDEO:
            cv2 = _opencv()
            reported = float(self._capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
            calculated = self._frame_index / self._fps
            position = max(0.0, reported if reported > 0.0 else calculated)
            observed_at = self._opened_at + timedelta(seconds=position)
        else:
            observed_at = self._clock().astimezone(UTC)
            position = max(0.0, (observed_at - self._opened_at).total_seconds())

        frame = CapturedFrame(
            image=np.asarray(image),
            index=self._frame_index,
            observed_at=observed_at,
            source_position_seconds=position,
        )
        self._frame_index += 1
        return frame

    def close(self) -> None:
        capture, self._capture = self._capture, None
        if capture is not None:
            capture.release()
