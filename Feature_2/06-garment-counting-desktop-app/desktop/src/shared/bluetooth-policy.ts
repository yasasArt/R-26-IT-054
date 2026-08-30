export const CONTROLLER_DEVICE_NAME = "GarmentCounter-IoT";
export const CONTROLLER_SERVICE_UUID = "7d2ea28a-f7bd-485a-bd9d-92ad6ecfe93e";
export const CONTROLLER_EVENT_CHARACTERISTIC_UUID = "8f42b2f3-6d57-4f8b-8b66-7b6dfc3dd98a";

export const HARDWARE_BUTTON_EVENTS = ["REWORK", "DOWNTIME", "RESET"] as const;

export type HardwareButtonEvent = (typeof HARDWARE_BUTTON_EVENTS)[number];
export type ControllerNotification = HardwareButtonEvent | "CONNECT_REQUEST" | "SHUTDOWN" | "READY";

/**
 * Chromium intentionally exposes different Bluetooth identifiers to Electron's
 * native chooser and the origin-scoped Web Bluetooth API on some platforms.
 * Bind the first verified GATT connection to an explicit operator selection,
 * then reject every other runtime device until a new selection is made.
 */
export class BluetoothControllerApproval {
  private selectedDeviceId: string | null = null;

  private runtimeDeviceId: string | null = null;

  select(deviceId: string): void {
    this.selectedDeviceId = deviceId.trim() || null;
    this.runtimeDeviceId = null;
  }

  bindRuntimeDevice(deviceId: string): boolean {
    const normalized = deviceId.trim();
    if (!this.selectedDeviceId || !normalized) return false;

    if (!this.runtimeDeviceId) {
      this.runtimeDeviceId = normalized;
    }

    return this.runtimeDeviceId === normalized;
  }

  isApproved(deviceId: string): boolean {
    const normalized = deviceId.trim();
    return Boolean(normalized) && this.runtimeDeviceId === normalized;
  }

  clear(): void {
    this.selectedDeviceId = null;
    this.runtimeDeviceId = null;
  }
}

export function isSupportedControllerName(name: string | undefined | null): boolean {
  return name?.trim() === CONTROLLER_DEVICE_NAME;
}

export function describeDiscoveredBluetoothDevice(
  deviceId: string,
  deviceName: string | undefined | null,
): DiscoveredBluetoothDevice {
  const name = deviceName?.trim() || "Unnamed Bluetooth device";
  return { deviceId, deviceName: name, compatible: isSupportedControllerName(name) };
}

export function sortDiscoveredBluetoothDevices(
  devices: Iterable<DiscoveredBluetoothDevice>,
): DiscoveredBluetoothDevice[] {
  return [...devices].sort((left, right) =>
    Number(right.compatible) - Number(left.compatible) || left.deviceName.localeCompare(right.deviceName),
  );
}

export function parseControllerNotification(value: string): ControllerNotification | null {
  const normalized = value.replace(/\0/g, "").trim().toUpperCase();

  if (
    normalized === "REWORK" ||
    normalized === "DOWNTIME" ||
    normalized === "RESET" ||
    normalized === "CONNECT_REQUEST" ||
    normalized === "SHUTDOWN" ||
    normalized === "READY"
  ) {
    return normalized;
  }

  return null;
}

export function reconnectDelayMilliseconds(attempt: number): number {
  return Math.min(15_000, 1_000 * 2 ** Math.max(0, attempt - 1));
}
import type { DiscoveredBluetoothDevice } from "./types";
