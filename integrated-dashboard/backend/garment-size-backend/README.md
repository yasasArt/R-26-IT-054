# Garment Size Detection backend

This is the supplied FastAPI/Ultralytics measurement service. It owns camera calibration, measurements, size-chart rules, order records, and SQLite data.

Electron supplies `GARMENT_MODEL_PATH`, `THREADSCAN_DATA_DIR`, and a dynamic loopback `GARMENT_FEATURE_PORT`. The trained model remains isolated under `../../models/garment-size/`, and development uses the common `backend/.venv`.

