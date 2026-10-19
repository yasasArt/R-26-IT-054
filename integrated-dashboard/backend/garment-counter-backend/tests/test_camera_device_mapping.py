from __future__ import annotations

import threading

import numpy as np

from app.vision import runtime


class FakeCapture:
    def __init__(self, index: int) -> None:
        self.index = index
        self.released = False

    def isOpened(self) -> bool:  # noqa: N802 - mirrors OpenCV
        return True

    def read(self):
        return True, np.zeros((480, 640, 3), dtype=np.uint8)

    def release(self) -> None:
        self.released = True


class FakeCv2:
    CAP_ANY = 0
    CAP_DSHOW = 700
    CAP_MSMF = 1400
    CAP_AVFOUNDATION = 1200
    CAP_V4L2 = 200

    def __init__(self) -> None:
        self.opened: list[tuple[int, int | None]] = []

    def VideoCapture(self, index: int, backend: int | None = None):  # noqa: N802
        self.opened.append((index, backend))
        return FakeCapture(index)


def test_windows_camera_capture_prefers_directshow(monkeypatch) -> None:
    fake_cv2 = FakeCv2()
    monkeypatch.setattr(runtime.sys, "platform", "win32")

    capture = runtime.open_camera_capture(fake_cv2, 2)

    assert capture.index == 2
    assert fake_cv2.opened == [(2, fake_cv2.CAP_DSHOW)]


def test_camera_labels_and_indices_come_from_the_same_native_order(monkeypatch) -> None:
    fake_cv2 = FakeCv2()
    monkeypatch.setattr(runtime, "get_opencv", lambda: fake_cv2)
    monkeypatch.setattr(runtime, "native_camera_names", lambda: ["Integrated Camera", "USB Workstation Camera"])

    vision = object.__new__(runtime.VisionRuntime)
    vision._thread = None
    vision._stop = threading.Event()
    cameras = vision.scan_cameras(expected_count=2)

    assert [camera["camera_id"] for camera in cameras] == ["0", "1"]
    assert cameras[0]["label"].startswith("Integrated Camera · Camera 1")
    assert cameras[1]["label"].startswith("USB Workstation Camera · Camera 2")
