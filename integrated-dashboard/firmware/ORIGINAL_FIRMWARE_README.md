# GarmentCounterIoT Firmware - ESP32-C3 SuperMini

This firmware is for the garment counting IoT controller with four push buttons and the built-in LED on GPIO 8.

## Board

- ESP32-C3 SuperMini
- Arduino IDE
- NimBLE-Arduino library by h2zero

This version is patched for NimBLE-Arduino v2.x callback signatures.

## Buttons

| Button | GPIO | Behavior |
|---|---:|---|
| A | GPIO 2 | Short press: start/restart BLE advertising or send CONNECT_REQUEST when connected. Long press: send SHUTDOWN and enter deep sleep. |
| B | GPIO 3 | Send REWORK event. |
| C | GPIO 4 | Send DOWNTIME event. |
| D | GPIO 5 | Send RESET event. |
| LED | GPIO 8 | Built-in status LED. |

Each button should connect the GPIO pin to GND. The sketch uses INPUT_PULLUP.

```txt
GPIO ---- Button ---- GND
```

Pressed = LOW, released = HIGH.

## BLE

Device name:

```txt
GarmentCounter-IoT
```

Service UUID:

```txt
7d2ea28a-f7bd-485a-bd9d-92ad6ecfe93e
```

Notify characteristic UUID:

```txt
8f42b2f3-6d57-4f8b-8b66-7b6dfc3dd98a
```

Events sent:

```txt
CONNECT_REQUEST
REWORK
DOWNTIME
RESET
SHUTDOWN
```

## LED Patterns

| State | Pattern |
|---|---|
| Boot | 3 quick blinks |
| BLE advertising/searching | Fast blink |
| Connected/normal | Small heartbeat blink every 3 seconds |
| Rework mode | Double blink |
| Downtime mode | Long warning blink |
| Reset | One long confirmation blink |
| Shutdown | Slow blinking pulses before deep sleep |

## Deep Sleep Note

Long press on Button A enters ESP32-C3 deep sleep. Your MT3608 boost converter can still draw current, so this is not a true complete hardware power cut. For full power off, add a MOSFET-based power latch circuit and connect it to `POWER_LATCH_OFF_PIN` in the sketch.
