# ESP32-C3 Firmware

Flash the included `GarmentCounterIoT.ino` before testing this desktop build.
It enables NimBLE-Arduino v2 scan response so macOS can reliably display the
full `GarmentCounter-IoT` name while the 128-bit controller service remains in
the primary advertisement. Wiring and Arduino IDE instructions remain in
`ORIGINAL_FIRMWARE_README.md`.

| Control | GPIO | Desktop behaviour |
| --- | ---: | --- |
| Button A, short press | 2 | Start/restart BLE advertising; confirm connection when already connected. |
| Button A, long press | 2 | Send shutdown and enter deep sleep; the desktop safely pauses production. |
| Button B | 3 | Persist a real `REWORK` event and pause garment counting. |
| Button C | 4 | Persist a real `DOWNTIME` event and pause garment counting. |
| Button D | 5 | Persist a real `RESET` event and return to normal without resetting counts. |
| Built-in status LED | 8 | Show advertising, connection, rework, downtime, and shutdown patterns. |

The popup shows nearby devices and lets the operator choose one. The desktop
then verifies the firmware service UUID
`7d2ea28a-f7bd-485a-bd9d-92ad6ecfe93e` and notification characteristic
`8f42b2f3-6d57-4f8b-8b66-7b6dfc3dd98a` before accepting it as a garment
controller. This service-level verification remains reliable even if macOS
temporarily reports an empty or cached Bluetooth name.
