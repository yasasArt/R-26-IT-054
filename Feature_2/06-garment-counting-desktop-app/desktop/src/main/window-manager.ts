import { app, BrowserWindow } from "electron";
import path from "node:path";

import {
  BluetoothControllerApproval,
  describeDiscoveredBluetoothDevice,
  sortDiscoveredBluetoothDevices,
} from "../shared/bluetooth-policy";
import { IPC_CHANNELS } from "../shared/ipc-channels";
import type { DiscoveredBluetoothDevice } from "../shared/types";
import { APP_ORIGIN, isTrustedRendererUrl, registerPackagedRendererProtocol } from "./protocol";

interface PendingBluetoothSelection {
  callback: (deviceId: string) => void;
  devices: Map<string, DiscoveredBluetoothDevice>;
  timeout: NodeJS.Timeout;
}

let mainWindow: BrowserWindow | null = null;
const controllerApproval = new BluetoothControllerApproval();
let pendingBluetoothSelection: PendingBluetoothSelection | null = null;

export function hasApprovedBluetoothController(deviceId: string): boolean {
  return controllerApproval.isApproved(deviceId);
}

export function bindApprovedBluetoothController(deviceId: string): boolean {
  return controllerApproval.bindRuntimeDevice(deviceId);
}

export function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}

export function selectBluetoothController(deviceId: string): void {
  const pending = pendingBluetoothSelection;
  if (!pending) throw new Error("Bluetooth device discovery is no longer active. Search again.");

  const device = pending.devices.get(deviceId);
  if (!device) {
    throw new Error("Select one of the available Bluetooth devices.");
  }

  controllerApproval.select(device.deviceId);
  clearBluetoothSelection(device.deviceId);
}

export function cancelBluetoothControllerSelection(): void {
  clearBluetoothSelection("");
}

function clearBluetoothSelection(deviceId: string): void {
  const pending = pendingBluetoothSelection;
  if (!pending) return;

  pendingBluetoothSelection = null;
  clearTimeout(pending.timeout);
  pending.callback(deviceId);
}

function protectWindowNavigation(window: BrowserWindow): void {
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));

  window.webContents.on("will-navigate", (event, destinationUrl) => {
    if (!isTrustedRendererUrl(destinationUrl, MAIN_WINDOW_WEBPACK_ENTRY)) {
      event.preventDefault();
    }
  });

  window.webContents.on("will-attach-webview", (event) => {
    event.preventDefault();
  });

  window.webContents.on("select-bluetooth-device", (event, devices, callback) => {
    event.preventDefault();

    if (!isTrustedRendererUrl(window.webContents.getURL(), MAIN_WINDOW_WEBPACK_ENTRY)) {
      callback("");
      return;
    }

    if (!pendingBluetoothSelection) {
      pendingBluetoothSelection = {
        callback,
        devices: new Map<string, DiscoveredBluetoothDevice>(),
        timeout: setTimeout(() => clearBluetoothSelection(""), 30_000),
      };
    }

    for (const candidate of devices) {
      pendingBluetoothSelection.devices.set(
        candidate.deviceId,
        describeDiscoveredBluetoothDevice(candidate.deviceId, candidate.deviceName),
      );
    }

    const discovered = sortDiscoveredBluetoothDevices(pendingBluetoothSelection.devices.values());
    window.webContents.send(IPC_CHANNELS.iotDiscoveredDevices, discovered);
  });

  window.webContents.session.setPermissionRequestHandler((contents, permission, callback, details) => {
    const trustedWindow =
      contents.id === window.webContents.id &&
      isTrustedRendererUrl(contents.getURL(), MAIN_WINDOW_WEBPACK_ENTRY);
    const mediaTypes = "mediaTypes" in details ? details.mediaTypes : undefined;
    const cameraOnly =
      permission === "media" &&
      mediaTypes?.includes("video") === true &&
      mediaTypes?.includes("audio") !== true;

    callback(trustedWindow && cameraOnly);
  });
}

export async function createMainWindow(): Promise<BrowserWindow> {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.focus();
    return mainWindow;
  }

  mainWindow = new BrowserWindow({
    title: "Garment Counter",
    width: 1480,
    height: 980,
    minWidth: 1060,
    minHeight: 720,
    show: false,
    icon: path.join(
      app.isPackaged ? process.resourcesPath : path.resolve(app.getAppPath(), "..", "resources"),
      "branding",
      "icon.png",
    ),
    backgroundColor: "#f4f6fa",
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "hidden",
    trafficLightPosition: process.platform === "darwin" ? { x: 19, y: 18 } : undefined,
    webPreferences: {
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  });

  protectWindowNavigation(mainWindow);

  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
  });

  mainWindow.on("closed", () => {
    clearBluetoothSelection("");
    controllerApproval.clear();
    mainWindow = null;
  });

  if (app.isPackaged) {
    registerPackagedRendererProtocol(MAIN_WINDOW_WEBPACK_ENTRY);
    await mainWindow.loadURL(`${APP_ORIGIN}/main_window/index.html`);
  } else {
    await mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);
  }

  return mainWindow;
}
