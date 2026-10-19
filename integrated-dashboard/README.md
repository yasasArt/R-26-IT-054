# Garment Intelligence 3.1

Garment Intelligence is one Electron desktop application that integrates four independently owned research components while preserving each member's frontend, backend, trained model, and database boundaries.

## Feature mapping

| Selection card | Research component | Source integrated | Runtime data |
|---|---|---|---|
| Production Monitoring | Garment-piece counting and cycle-time analysis | Existing Garment Intelligence project | `features/garment-counter/` |
| Rework Counter | Good/rework garment-piece counting | `garment-rework-counter-desktop` | `features/garment-rework/` |
| Garment Style and Colour Detection | Style recognition and dominant-colour extraction | `garment-style-detection` | `features/garment-style-colour/` |
| Garment Size Detection | Camera-based garment measurement and size recommendation | `garment-size-detection` | `features/garment-size/` |

The four backends do not call each other. Electron starts the service needed by the selected card, exposes only an allow-listed IPC API to the renderer, and keeps writable databases outside the installed application.

Version 3.1 fixes native camera selection in Production Monitoring, restores the
style/colour vision-service launcher, makes the Size Detection sidebar fully
interactive inside Electron's frameless window, and adds one consistent centered
startup experience for every feature. See `docs/22-version-3.1-fixes.md`.

The style-detection accuracy update replaces the live style capture rule with a
settled-garment engine (empty-table learning, hand and motion gates, tight
640 px crops, multi-frame voting, lock until removed), adds operator style
correction and named chart axes, and orders the features as Production
Monitoring, Rework Counter, Style and Colour, Size Detection. See
`docs/24-style-detection-accuracy-update.md`.

The included corrective update also adds validated, SQLite-backed Garment Size
orders, fresh new-order/reset behaviour, and individual database deletion from
Production History. See `docs/23-size-order-database-fixes.md`.

## Ownership structure

```text
garment-intelligence-platform/
├── frontend/
│   ├── node_modules/                    One shared install (created locally)
│   ├── src/                             Electron shell, selection page, IPC
│   ├── garment-rework-frontend/         Rework Counter owner
│   ├── garment-counter-frontend/        Production Monitoring owner
│   ├── garment-style-colour-frontend/   Style/colour owner
│   └── garment-size-frontend/           Size owner
├── backend/
│   ├── .venv/                           One shared Python environment (created locally)
│   ├── garment-rework-backend/
│   ├── garment-counter-backend/
│   ├── garment-style-colour-backend/
│   └── garment-size-backend/
├── models/
│   ├── garment-rework/
│   ├── garment-counter/
│   ├── garment-style-colour/
│   └── garment-size/
├── resources/branding/
├── firmware/
└── docs/
```

`node_modules` and `.venv` are deliberately not stored in the source ZIP because they contain platform-specific binaries and can exceed several gigabytes. The lockfile and setup script reproducibly create exactly one of each at the locations shown above. Production installers bundle feature sidecars, so operators do not install Python or Node.js.

## Development setup

Requirements: Python 3.12, Node.js 22.12 or newer, and npm.

macOS or Linux:

```bash
python3.12 backend/setup_shared_environment.py
cd frontend
npm ci
npm start
```

Windows PowerShell:

```powershell
py -3.12 backend\setup_shared_environment.py
cd frontend
npm ci
npm start
```

Verify everything before a demonstration:

```bash
backend/.venv/bin/python backend/setup_shared_environment.py --check
cd frontend
npm run verify
npm run release:plan
```

On Windows, use `backend\.venv\Scripts\python.exe` for the environment check.

## Production build

Build an installer on the same operating system and CPU architecture on which it will be presented:

```bash
cd frontend
npm run release:doctor
npm run release
```

The release pipeline builds isolated executable sidecars for all four services, validates all required model files and branding, compiles the renderer, and creates the platform installer. See `docs/20-production-release-guide.md` for signing, notarization, hardware checks, and distribution details.

## Important operating notes

- Allow camera access when the operating system asks. Rework, style/colour, and size features need it.
- Only one camera-heavy feature should be active at a time. Switching cards stops the outgoing camera/session first.
- Production Monitoring can connect to its ESP32-C3 controller by Bluetooth.
- Seed databases remain in their owning backend folders; working copies live under Electron's user-data directory so an application update cannot overwrite research results.
- The Style/Colour backend intentionally keeps its original FastAPI and vision-service split, while sharing the common Python environment and model directory.

For architecture, paths, ports, API isolation, and member handover instructions, read `docs/18-integrated-platform-guide.md`.
