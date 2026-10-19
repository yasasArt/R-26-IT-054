# Rework Counter frontend

This is the integrated React source from `garment-rework-counter-desktop`.

- Card: **Rework Counter**
- Root UI: `ReworkApp.jsx`
- Desktop adapter: `ReworkWorkspace.tsx`
- Backend: `../../backend/garment-rework-backend/`
- Model: `../../models/garment-rework/best.pt`

Backend calls use the typed Electron bridge. The live MJPEG feed uses the registered `garmentrework:` protocol, and the camera is stopped before switching features.

