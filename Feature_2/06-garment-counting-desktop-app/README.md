# Garment Counter Desktop — Production Release 1.0.3

An offline, single-workstation macOS/Windows desktop application for automatic
garment counting, sewing-cycle measurement, ESP32-C3 operator events, and
factory-ready production analytics.

The final operator-facing application includes **Device Setup**, **New
Session**, **Live Production**, **Analytics**, and **Settings**. Research-only
model evaluation is intentionally excluded from the shipping product.

## What the finished desktop application does

- Detects the real sewing workstation, then latches the valid environment so
  brief operator-hand occlusions cannot repeatedly interrupt the classifier.
- Uses the supplied genuine temporal MobileNetV3 checkpoint with its original
  training-compatible `ReLU` activation and confirms one garment for each
  completed `SEWING → IDLE_SETUP` production transition.
- Preserves the first garment's cycle time, excludes between-garment idle time
  from average cycle calculations, and presents cycle/remaining-target charts.
- Connects to the physical ESP32-C3 using a fixed-height Bluetooth device
  picker and records real `REWORK`, `DOWNTIME`, and `RESET` operator events.
- Supports a real live camera and OpenCV-decoded workstation test videos.
- Keeps the complete historical session list available in Analytics, including
  session details and professionally formatted, understated filtered Excel
  exports with factory-facing output, targets, cycle times, interruption
  metrics, and employee-performance summaries.
- Provides protected session-history deletion in Settings with typed explicit
  confirmation, active-session protection, and preservation of employee and
  workstation-device records.
- Keeps production preflight collapsed by default, makes the sidebar safe for
  macOS window controls, and removes unnecessary post-connection button tests.
- Bundles Electron, React, FastAPI, SQLite, Python, PyTorch, OpenCV,
  Ultralytics, both genuine checkpoints, and required model resources into a
  self-contained desktop installation. Factory operators do not install
  Python, npm, or developer dependencies.
- Repairs frozen PyTorch compatibility before packaging and refuses to create
  an installer unless both actual trained AI checkpoints successfully load.
- Includes matching professionally designed macOS, Windows, and in-app icons.

## Developer setup

Recommended: Node.js 22.12+, Python 3.11 or 3.12, and a matching host operating
system/CPU architecture for the desktop application you intend to release.

macOS:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev,release]'
python -m pytest

cd ../desktop
npm install
npm run verify
npm start
```

Windows PowerShell:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,release]"
python -m pytest

cd ..\desktop
npm install
npm run verify
npm start
```

The first installation downloads platform-native Electron and scientific Python
dependencies. On macOS, if Electron remains at `Downloading Electron binary...`,
run `node node_modules/electron/install.js` inside `desktop`, then retry.

## Create the customer installation

Run the release build on the **same operating system and processor
architecture** that will run the installed application:

```bash
cd desktop
npm run release:plan
npm run release:doctor
npm run release
```

`npm run release` performs all production steps automatically:

1. Checks every genuine model resource and Python release dependency.
2. Builds a standalone platform-native Python/AI service using PyInstaller.
3. Records SHA-256 integrity checksums for every supplied model resource.
4. Starts the bundled service in an isolated temporary database, verifies its
   authenticated localhost API, confirms anonymous requests are rejected, and
   loads/warms both genuine production AI models before packaging continues.
5. Runs TypeScript, lint, desktop-policy tests, and production Webpack builds.
6. Packages Electron together with the standalone service and trained models.
7. Produces the target-platform customer distribution.

macOS outputs:

```text
desktop/out/Garment Counter-darwin-arm64/Garment Counter.app
desktop/out/make/zip/darwin/arm64/*.zip
desktop/out/make/dmg/arm64/Garment-Counter-1.0.3-macOS-arm64.dmg
```

Windows output:

```text
desktop/out/make/squirrel.windows/x64/GarmentCounterSetup.exe
```

The CPU directory changes to `x64` when building for an Intel Mac. Build a
Windows installer on Windows; do not reuse a macOS PyInstaller sidecar for it.

Useful release commands:

```bash
npm run release:plan       # Show release layout and verify model files.
npm run release:doctor     # Verify Python and every packaging dependency.
npm run release:prepare    # Build and smoke-test only the frozen Python service.
npm run release:smoke      # Re-run service, security, SQLite, and real AI checks.
npm run package            # Package Electron after release:prepare.
npm run make               # Create installer formats after release:prepare.
npm run release:dmg        # Rebuild the macOS DMG from an existing packaged app.
```

## Optional signed and notarized macOS release

Unsigned builds are useful for internal testing. For external factory
distribution, configure an installed Developer ID certificate and Apple
notarization credentials before the release command:

```bash
export GARMENT_COUNTER_MAC_SIGNING_IDENTITY="Developer ID Application: Your Company (TEAMID)"
export GARMENT_COUNTER_APPLE_ID="release-account@example.com"
export GARMENT_COUNTER_APPLE_APP_PASSWORD="your-app-specific-password"
export GARMENT_COUNTER_APPLE_TEAM_ID="TEAMID"
npm run release
```

Secrets are read only from the current environment and are never embedded in
source code. The release includes macOS camera/Bluetooth usage descriptions,
hardened-runtime entitlements, an offline localhost-only application service,
and isolated per-installation SQLite storage.

## Operator workflow

1. Open **Device Setup**. Scan the sewing camera and select **Test camera**.
2. Select **Connect controller**, choose the physical ESP32-C3 in the Bluetooth
   popup, and wait for the live connection confirmation.
3. Add employees and their assigned sewing lines from **Settings**.
4. Create a session, choose the employee, and manually enter the target pieces;
   the employee's sewing line fills automatically.
5. Monitor the camera, confirmed garments, cycle times, remaining target,
   operator status, and live hardware events from **Live Production**.
6. Use **Test workflow video** when validating a recorded sewing workflow.
7. End the session and open **Analytics** to review all historical sessions,
   inspect an individual session, filter by employee/date/line, and export a
   professional Excel workbook.

## Project structure

```text
garment-counter-desktop-phase-06/
├── backend/
│   ├── app/                  FastAPI, SQLite, AI inference, analytics, exports
│   ├── packaging/            Standalone PyInstaller entry point and frozen spec
│   └── tests/                Backend behavior and release-entry tests
├── desktop/
│   ├── packaging/            macOS production entitlements
│   ├── scripts/              Release builder, frozen smoke test, DMG creation
│   ├── src/                  Electron, preload bridge, React application
│   └── tests/                Desktop policy, security, and release tests
├── docs/                     Architecture, behavior, deployment, acceptance
├── firmware/                 ESP32-C3 Bluetooth operator-controller sketch
└── resources/
    ├── branding/             Production SVG, PNG, macOS ICNS, and Windows ICO
    └── models/               Both trained checkpoints and model metadata
```

For deployment, signing, permissions, backups, and handover details, read
`docs/15-final-production-deployment-guide.md` and
`docs/16-final-release-acceptance-checklist.md`.
