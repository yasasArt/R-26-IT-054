import { useSyncExternalStore } from "react";

import {
  CONTROLLER_DEVICE_NAME,
  CONTROLLER_EVENT_CHARACTERISTIC_UUID,
  CONTROLLER_SERVICE_UUID,
  parseControllerNotification,
  reconnectDelayMilliseconds,
} from "../../shared/bluetooth-policy";
import type { BluetoothControllerState, HardwareButtonEventType } from "../../shared/types";

interface BrowserBluetoothCharacteristic extends EventTarget {
  value: DataView | null;
  startNotifications: () => Promise<BrowserBluetoothCharacteristic>;
  stopNotifications: () => Promise<BrowserBluetoothCharacteristic>;
}

interface BrowserBluetoothService {
  getCharacteristic: (uuid: string) => Promise<BrowserBluetoothCharacteristic>;
}

interface BrowserBluetoothGattServer {
  connected: boolean;
  connect: () => Promise<BrowserBluetoothGattServer>;
  disconnect: () => void;
  getPrimaryService: (uuid: string) => Promise<BrowserBluetoothService>;
}

interface BrowserBluetoothDevice extends EventTarget {
  id: string;
  name?: string;
  gatt?: BrowserBluetoothGattServer;
}

interface BrowserBluetooth {
  requestDevice: (options: {
    acceptAllDevices: true;
    optionalServices: string[];
  }) => Promise<BrowserBluetoothDevice>;
}

interface PreparedController {
  deviceId: string;
  deviceName: string;
}

type ControllerPreparation = (controller: PreparedController) => Promise<void>;

const disconnectedState: BluetoothControllerState = {
  phase: "DISCONNECTED",
  deviceId: null,
  deviceName: null,
  notificationsActive: false,
  reconnectAttempt: 0,
  lastButton: null,
  lastButtonAt: null,
  message: "Connect the physical ESP32-C3 operator controller.",
};

class BluetoothController {
  private state: BluetoothControllerState = disconnectedState;

  private readonly subscribers = new Set<() => void>();

  private device: BrowserBluetoothDevice | null = null;

  private characteristic: BrowserBluetoothCharacteristic | null = null;

  private desiredConnection = false;

  private generation = 0;

  private notificationQueue: Promise<void> = Promise.resolve();

  subscribe = (listener: () => void): (() => void) => {
    this.subscribers.add(listener);
    return () => this.subscribers.delete(listener);
  };

  snapshot = (): BluetoothControllerState => this.state;

  async connect(prepare: ControllerPreparation): Promise<void> {
    const bluetooth = (navigator as Navigator & { bluetooth?: BrowserBluetooth }).bluetooth;

    if (!bluetooth) {
      throw new Error("Bluetooth is unavailable. Enable Bluetooth and open the application in Electron.");
    }

    if (this.state.phase === "CONNECTED" && this.device?.gatt?.connected) return;

    this.desiredConnection = true;
    const currentGeneration = ++this.generation;
    this.update({
      phase: "SCANNING",
      notificationsActive: false,
      reconnectAttempt: 0,
      message: "Looking for GarmentCounter-IoT. Press Button A if the controller is asleep.",
    });

    try {
      // requestDevice must execute directly from the operator's click gesture.
      const device = await bluetooth.requestDevice({
        acceptAllDevices: true,
        optionalServices: [CONTROLLER_SERVICE_UUID],
      });

      if (!device.gatt) {
        throw new Error("The selected device does not provide a Bluetooth connection.");
      }

      if (currentGeneration !== this.generation) return;

      if (this.device && this.device !== device) {
        this.device.removeEventListener("gattserverdisconnected", this.handleDisconnected);
      }

      this.device = device;
      this.device.addEventListener("gattserverdisconnected", this.handleDisconnected);
      this.update({
        phase: "CONNECTING",
        deviceId: device.id,
        deviceName: device.name ?? CONTROLLER_DEVICE_NAME,
        message: "Connecting and subscribing to the operator buttons…",
      });

      await this.openAndSubscribe(currentGeneration, prepare);
    } catch (caughtError) {
      if (currentGeneration !== this.generation) return;

      this.desiredConnection = false;
      const characteristic = this.characteristic;
      this.characteristic = null;
      if (characteristic) {
        characteristic.removeEventListener("characteristicvaluechanged", this.handleNotification);
        await characteristic.stopNotifications().catch(() => undefined);
      }
      if (this.device?.gatt?.connected) this.device.gatt.disconnect();
      this.update({
        phase: "ERROR",
        notificationsActive: false,
        message: describeBluetoothError(caughtError),
      });
      throw new Error(this.state.message);
    }
  }

  async disconnect(reason = "The controller was disconnected from the device setup screen."): Promise<void> {
    this.desiredConnection = false;
    ++this.generation;

    const device = this.device;
    const characteristic = this.characteristic;
    this.characteristic = null;

    if (device && this.state.phase === "CONNECTED") {
      await this.reportConnection(false, reason).catch(() => undefined);
    }

    if (characteristic) {
      characteristic.removeEventListener("characteristicvaluechanged", this.handleNotification);
      await characteristic.stopNotifications().catch(() => undefined);
    }

    if (device) {
      device.removeEventListener("gattserverdisconnected", this.handleDisconnected);
      if (device.gatt?.connected) device.gatt.disconnect();
    }

    this.device = null;
    this.update({
      phase: "DISCONNECTED",
      notificationsActive: false,
      reconnectAttempt: 0,
      message: "The physical controller is disconnected.",
    });
  }

  private async openAndSubscribe(
    generation: number,
    prepare?: ControllerPreparation,
  ): Promise<void> {
    const device = this.device;
    if (!device?.gatt) throw new Error("The controller Bluetooth connection is unavailable.");

    const server = device.gatt.connected ? device.gatt : await device.gatt.connect();
    const service = await server.getPrimaryService(CONTROLLER_SERVICE_UUID);
    const characteristic = await service.getCharacteristic(CONTROLLER_EVENT_CHARACTERISTIC_UUID);

    try {
      characteristic.addEventListener("characteristicvaluechanged", this.handleNotification);
      await characteristic.startNotifications();
      if (prepare) {
        await prepare({
          deviceId: device.id,
          deviceName: device.name?.trim() || CONTROLLER_DEVICE_NAME,
        });
      }
    } catch (caughtError) {
      characteristic.removeEventListener("characteristicvaluechanged", this.handleNotification);
      throw caughtError;
    }

    if (generation !== this.generation || !this.desiredConnection) {
      characteristic.removeEventListener("characteristicvaluechanged", this.handleNotification);
      await characteristic.stopNotifications().catch(() => undefined);
      return;
    }

    this.characteristic = characteristic;
    await this.reportConnection(true);

    this.update({
      phase: "CONNECTED",
      deviceId: device.id,
      deviceName: device.name?.trim() || CONTROLLER_DEVICE_NAME,
      notificationsActive: true,
      reconnectAttempt: 0,
      message: "Controller connected. Rework, downtime, and reset buttons are live.",
    });
  }

  private handleNotification = (event: Event): void => {
    const characteristic = event.target as BrowserBluetoothCharacteristic | null;
    if (!characteristic?.value) return;

    const raw = new TextDecoder().decode(characteristic.value);
    const notification = parseControllerNotification(raw);

    if (!notification || notification === "READY") return;

    if (notification === "CONNECT_REQUEST") {
      this.update({ message: "Controller test passed. Button A is responding over Bluetooth." });
      return;
    }

    if (notification === "SHUTDOWN") {
      this.update({ message: "The controller is entering sleep. Press Button A to wake and reconnect." });
      return;
    }

    this.notificationQueue = this.notificationQueue
      .then(() => this.persistButton(notification, raw))
      .catch((caughtError: unknown) => {
        this.update({
          message:
            caughtError instanceof Error
              ? `The controller press could not be stored: ${caughtError.message}`
              : "The controller press could not be stored.",
        });
      });
  };

  private async persistButton(eventType: HardwareButtonEventType, raw: string): Promise<void> {
    const device = this.device;
    if (!device) return;

    await window.garmentDesktop.submitHardwareEvent({
      device_id: device.id,
      device_name: device.name?.trim() || CONTROLLER_DEVICE_NAME,
      event_type: eventType,
      payload: { raw_notification: raw },
    });

    this.update({
      lastButton: eventType,
      lastButtonAt: new Date().toISOString(),
      message:
        eventType === "RESET"
          ? "Reset received. The operator returned to normal production."
          : `${eventType === "REWORK" ? "Rework" : "Downtime"} button received and recorded.`,
    });
  }

  private handleDisconnected = (): void => {
    const characteristic = this.characteristic;
    this.characteristic = null;
    characteristic?.removeEventListener("characteristicvaluechanged", this.handleNotification);

    if (!this.desiredConnection || !this.device) return;

    const generation = this.generation;
    this.update({
      phase: "RECONNECTING",
      notificationsActive: false,
      reconnectAttempt: 0,
      message: "Controller connection lost. Counting is paused while reconnection is attempted.",
    });

    void this.reportConnection(false, "The Bluetooth controller disconnected unexpectedly.")
      .catch(() => undefined)
      .finally(() => void this.reconnect(generation));
  };

  private async reconnect(generation: number): Promise<void> {
    let attempt = 0;

    while (this.desiredConnection && generation === this.generation && this.device) {
      attempt += 1;
      this.update({
        phase: "RECONNECTING",
        reconnectAttempt: attempt,
        message: `Controller disconnected. Reconnection attempt ${attempt}; press Button A to wake it.`,
      });

      await wait(reconnectDelayMilliseconds(attempt));
      if (!this.desiredConnection || generation !== this.generation) return;

      try {
        await this.openAndSubscribe(generation);
        return;
      } catch {
        // Keep production safely paused until both GATT and notifications return.
      }
    }
  }

  private reportConnection(connected: boolean, reason?: string): Promise<unknown> {
    const device = this.device;
    if (!device) return Promise.resolve();

    return window.garmentDesktop.syncIotConnection({
      device_id: device.id,
      device_name: device.name?.trim() || CONTROLLER_DEVICE_NAME,
      connected,
      notifications_active: connected,
      ...(reason ? { reason } : {}),
    });
  }

  private update(patch: Partial<BluetoothControllerState>): void {
    this.state = { ...this.state, ...patch };
    for (const listener of this.subscribers) listener();
  }
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function describeBluetoothError(error: unknown): string {
  const message = error instanceof Error ? error.message : "The operator controller could not connect.";

  if (/user cancelled|cancelled|canceled|no devices/i.test(message)) {
    return "Controller not found. Turn on Bluetooth, press Button A, and try connecting again.";
  }

  if (/permission|authorized|authorised|denied/i.test(message)) {
    return "Bluetooth permission was denied. Allow Garment Counter in the system Bluetooth privacy settings.";
  }

  if (/service|characteristic|gatt/i.test(message)) {
    return "That Bluetooth device is not the garment controller. Select the ESP32-C3 device and try again.";
  }

  return message;
}

export const bluetoothController = new BluetoothController();

export function useBluetoothController(): BluetoothControllerState {
  return useSyncExternalStore(bluetoothController.subscribe, bluetoothController.snapshot);
}
