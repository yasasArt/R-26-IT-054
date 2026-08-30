from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import numpy as np

from app.vision.camera_manager import CaptureDependencyError

JpegEncoder = Callable[[np.ndarray, int], bytes]


def encode_jpeg(frame: np.ndarray, quality: int) -> bytes:
    try:
        import cv2
    except (ImportError, RuntimeError) as exc:
        raise CaptureDependencyError("OpenCV is required for preview encoding") from exc
    success, encoded = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), quality],
    )
    if not success:
        raise RuntimeError("Unable to encode preview frame")
    return bytes(encoded)


class FramePublisher:
    """Keep only the latest JPEG so slow preview clients cannot block inference."""

    def __init__(
        self,
        *,
        jpeg_quality: int = 80,
        encoder: JpegEncoder = encode_jpeg,
    ) -> None:
        self.jpeg_quality = jpeg_quality
        self._encoder = encoder
        self._condition = threading.Condition()
        self._latest: bytes | None = None
        self._sequence = 0
        self._subscribers = 0
        self._preview_attached = False
        self._closed = False

    @property
    def subscriber_count(self) -> int:
        with self._condition:
            return self._subscribers

    @property
    def preview_ready(self) -> bool:
        with self._condition:
            return self._latest is not None

    @property
    def preview_attached(self) -> bool:
        with self._condition:
            return self._preview_attached

    def reset(self) -> None:
        with self._condition:
            if self._subscribers:
                raise RuntimeError(
                    "Cannot reset preview while subscribers are attached"
                )
            self._latest = None
            self._sequence = 0
            self._preview_attached = False
            self._closed = False
            self._condition.notify_all()

    def publish(self, frame: np.ndarray) -> int:
        return self.publish_jpeg(self._encoder(frame, self.jpeg_quality))

    def publish_jpeg(self, jpeg: bytes) -> int:
        if not jpeg:
            raise ValueError("Preview JPEG cannot be empty")
        with self._condition:
            if self._closed:
                return self._sequence
            self._latest = bytes(jpeg)
            self._sequence += 1
            self._condition.notify_all()
            return self._sequence

    def latest_jpeg(self) -> bytes | None:
        """Return a copy of the current frame for authenticated IPC polling."""

        with self._condition:
            return bytes(self._latest) if self._latest is not None else None

    def mark_preview_attached(self) -> None:
        """Record that a trusted preview consumer displayed or requested a frame."""

        with self._condition:
            if self._closed:
                raise RuntimeError("Preview stream is closed")
            self._preview_attached = True
            self._condition.notify_all()

    def wait_for_attachment(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._closed and not self._preview_attached:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return not self._closed and self._preview_attached

    def wait_for_subscriber(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._closed and self._subscribers == 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return not self._closed and self._subscribers > 0

    @contextmanager
    def subscriber(self) -> Iterator[None]:
        with self._condition:
            if self._closed:
                raise RuntimeError("Preview stream is closed")
            self._subscribers += 1
            self._preview_attached = True
            self._condition.notify_all()
        try:
            yield
        finally:
            with self._condition:
                self._subscribers = max(0, self._subscribers - 1)
                self._condition.notify_all()

    def _wait_for_frame(
        self,
        after_sequence: int,
        timeout: float,
    ) -> tuple[int, bytes | None, bool]:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._closed and self._sequence <= after_sequence:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return self._sequence, None, False
                self._condition.wait(remaining)
            if self._closed and self._sequence <= after_sequence:
                return self._sequence, None, True
            return self._sequence, self._latest, self._closed

    def iter_mjpeg(self) -> Iterator[bytes]:
        sequence = -1
        with self.subscriber():
            while True:
                sequence, jpeg, closed = self._wait_for_frame(sequence, 1.0)
                if jpeg is not None:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Cache-Control: no-store\r\n\r\n" + jpeg + b"\r\n"
                    )
                if closed:
                    return

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
