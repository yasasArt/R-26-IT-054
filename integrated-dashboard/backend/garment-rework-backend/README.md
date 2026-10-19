# Rework Counter backend

This is the supplied FastAPI/OpenCV/Ultralytics rework-counting service. It owns good/rework tracking, inspection history, camera/video input, and its SQLite data.

Electron supplies `GARMENT_REWORK_MODEL_PATH`, `GARMENT_REWORK_DATA_DIR`, and a loopback `GARMENT_FEATURE_PORT`. Development and release builds use the shared environment at `../.venv`; this backend does not import or call another feature backend.

