"""Cross-platform camera discovery and OpenCV capture helpers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

import cv2


def _capture_backends() -> tuple[int, ...]:
    if sys.platform == "win32":
        preferred = (
            getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY),
            getattr(cv2, "CAP_MSMF", cv2.CAP_ANY),
            cv2.CAP_ANY,
        )
    elif sys.platform == "darwin":
        preferred = (
            getattr(cv2, "CAP_AVFOUNDATION", cv2.CAP_ANY),
            cv2.CAP_ANY,
        )
    else:
        preferred = (
            getattr(cv2, "CAP_V4L2", cv2.CAP_ANY),
            cv2.CAP_ANY,
        )

    return tuple(dict.fromkeys(preferred))


def open_camera(index: int) -> Any:
    """Open a device using the native capture backend, with a safe fallback."""
    for backend in _capture_backends():
        try:
            capture = (
                cv2.VideoCapture(index)
                if backend == cv2.CAP_ANY
                else cv2.VideoCapture(index, backend)
            )
        except Exception:
            continue

        if capture.isOpened():
            return capture

        capture.release()

    raise RuntimeError(f"Could not open camera index {index} on {sys.platform}.")


def _windows_camera_names() -> list[str]:
    try:
        from pygrabber.dshow_graph import FilterGraph

        return [str(name) for name in FilterGraph().get_input_devices()]
    except Exception:
        return []


def _macos_camera_names() -> list[str]:
    try:
        result = subprocess.run(
            ["system_profiler", "SPCameraDataType", "-json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        payload = json.loads(result.stdout)
        devices = payload.get("SPCameraDataType", [])
        return [
            str(device["_name"])
            for device in devices
            if isinstance(device, dict) and device.get("_name")
        ]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []


def enumerate_cameras(active_index: int | None = None) -> list[dict[str, Any]]:
    """Return indices compatible with the capture backend used by ThreadScan."""
    if sys.platform == "win32":
        names = _windows_camera_names()
    elif sys.platform == "darwin":
        names = _macos_camera_names()
    else:
        names = []

    if names:
        devices = [{"index": index, "name": name} for index, name in enumerate(names)]
        if active_index is not None and active_index >= len(devices):
            devices.append({"index": active_index, "name": f"Camera {active_index}"})
        return devices

    try:
        probe_count = max(1, min(16, int(os.environ.get("THREADSCAN_CAMERA_PROBE_COUNT", "6"))))
    except ValueError:
        probe_count = 6

    devices = []
    for index in range(max(probe_count, (active_index or 0) + 1)):
        if active_index == index:
            devices.append({"index": index, "name": f"Camera {index}"})
            continue

        try:
            capture = open_camera(index)
        except RuntimeError:
            continue

        capture.release()
        devices.append({"index": index, "name": f"Camera {index}"})

    return devices
