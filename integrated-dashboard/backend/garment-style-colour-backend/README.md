# Garment Style and Colour Detection backend

This directory preserves ThreadScan's independent FastAPI data service and Flask/OpenCV vision service. It owns garment history, settings, analytics, downtime, style inference, dominant-colour extraction, camera selection, and SQLite data.

Electron starts the two loopback services when the Style and Colour card opens. `THREADSCAN_MODEL_PATH` points to `../../models/garment-style-colour/best.pt`, and `THREADSCAN_DATA_DIR` points to the feature's isolated writable directory. Both processes use the common `backend/.venv` in development.

Live style decisions are made by `style_engine.py` (see
`docs/24-style-detection-accuracy-update.md`): the garment is located against a
learned picture of the empty folding zone, classified as a tight 640 px crop
once it has settled with no hand covering it, voted on over several frames,
and the zone stays locked until the garment is removed. Run
`python -m pytest tests` for the engine tests and
`python tools/replay_style_video.py <video> --calibrate-at <seconds>` to
evaluate on a recorded video.
