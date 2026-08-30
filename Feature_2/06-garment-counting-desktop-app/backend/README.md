# Garment Counter Python Sidecar

The desktop application starts this FastAPI service automatically. It owns the
local SQLite database, employee records, production sessions, garment-piece
events, operator IoT events, analytics, styled Excel exports, real OpenCV camera
capture, YOLO workstation detection, temporal MobileNetV3 inference, and
production-safe automatic counting.

## Development setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Windows PowerShell activation:

```powershell
.venv\Scripts\Activate.ps1
```

Installation includes PyTorch, torchvision, OpenCV, and Ultralytics. Both
supplied checkpoint files, `label_mapping.json`, and `data.yaml` must remain in
`../resources/models/`.

The Electron main process supplies a random localhost port, a per-launch bearer
token, the writable application-data directory, and the packaged model path.
Never expose this service to the network or place its token in the renderer.

## Vision pipeline

1. Load and warm `best.pt`; require its trained `workstation` class.
2. Strictly load `best_model.pt` into the exact `576 → 1024 → 2` temporal
   MobileNetV3 classifier with the original training-compatible `ReLU` classifier activation.
3. Read a live camera or codec-independent recorded workflow test using OpenCV.
4. Verify a real workstation before processing eight fresh 224 × 224 frames.
5. Smooth predictions and confirm a full `SEWING → IDLE_SETUP` transition.
6. Recheck session, controller, and operator mode inside a SQLite transaction.
7. Persist the completed garment, including the real first-piece cycle time.
8. Stream annotated MJPEG only through authenticated Electron-owned requests.

## Physical controller integration

Phase 4 uses Electron Web Bluetooth to select the existing ESP32-C3 controller,
subscribe to its notification characteristic, and forward approved hardware
messages through dedicated, validated Electron IPC channels. The authenticated
sidecar owns production readiness, physical connection state, operator modes,
active-session association, event timestamps, employee attribution, and SQLite
persistence.

- `POST /api/iot/connection` atomically updates Bluetooth availability and
  records a `DISCONNECTED` or `RECONNECTED` event only when readiness changes.
- Physical `REWORK`, `DOWNTIME`, and `RESET` notifications are accepted only
  while the configured real controller has an active notification subscription.
- Hardware presses automatically attach to the current active production
  session and employee; setup-screen button tests are retained without a session.
- Application restart invalidates stale Bluetooth readiness and records a safe
  disconnection for any previously active production session.
- SQLite connections are request-owned but allow FastAPI's legitimate worker
  thread hand-offs; write transactions remain serialized by `BEGIN IMMEDIATE`.

Explicit validation simulation remains separate and can never satisfy physical
production readiness.
