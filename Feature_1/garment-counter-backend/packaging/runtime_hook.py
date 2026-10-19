"""Keep frozen scientific-library caches outside the read-only app bundle."""

from __future__ import annotations

import os
from pathlib import Path

data_directory = os.environ.get("GARMENT_COUNTER_DATA_DIR", "").strip()

if data_directory:
    writable_directory = Path(data_directory)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(writable_directory / "ultralytics"))
    os.environ.setdefault("MPLCONFIGDIR", str(writable_directory / "matplotlib"))

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("PYTHONUNBUFFERED", "1")
