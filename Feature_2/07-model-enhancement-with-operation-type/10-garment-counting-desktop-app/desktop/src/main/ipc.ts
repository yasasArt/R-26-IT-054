import { BrowserWindow, dialog, ipcMain, type IpcMainInvokeEvent } from "electron";
import { writeFile } from "node:fs/promises";
import path from "node:path";

import { IPC_CHANNELS } from "../shared/ipc-channels";
import { allowsRendererBackendRequest } from "../shared/ipc-policy";
import { HARDWARE_BUTTON_EVENTS } from "../shared/bluetooth-policy";
import type {
  BackendRequest,
  ExportResult,
  HardwareConnectionInput,
  HardwareConnectionResult,
  HardwareEventInput,
  IotEvent,
  SystemReadiness,
  ValidationVideoResult,
  WindowState,
} from "../shared/types";
import { backendManager } from "./backend-manager";
import { isTrustedRendererUrl, STREAM_PROTOCOL } from "./protocol";
import { checkPhaseOneReadiness, getDesktopAppInfo } from "./readiness-service";
import {
  bindApprovedBluetoothController,
  cancelBluetoothControllerSelection,
  hasApprovedBluetoothController,
  selectBluetoothController,
} from "./window-manager";

type WindowResolver = () => BrowserWindow | null;

function assertTrustedSender(event: IpcMainInvokeEvent, resolveWindow: WindowResolver): BrowserWindow {
  const window = resolveWindow();

  if (!window || window.isDestroyed()) {
    throw new Error("The desktop application window is unavailable.");
  }

  if (event.sender.id !== window.webContents.id) {
    throw new Error("IPC request rejected: unknown renderer.");
  }

  const senderUrl = event.senderFrame?.url || event.sender.getURL();

  if (!isTrustedRendererUrl(senderUrl, MAIN_WINDOW_WEBPACK_ENTRY)) {
    throw new Error("IPC request rejected: untrusted renderer origin.");
  }

  return window;
}

export function registerDesktopIpc(resolveWindow: WindowResolver): void {
  let activeHardwareDeviceId: string | null = null;

  ipcMain.handle(IPC_CHANNELS.appInfo, (event) => {
    assertTrustedSender(event, resolveWindow);
    return getDesktopAppInfo();
  });

  ipcMain.handle(IPC_CHANNELS.readiness, async (event) => {
    assertTrustedSender(event, resolveWindow);

    if (backendManager.getStatus().state !== "ready") {
      return checkPhaseOneReadiness();
    }

    return backendManager.request<SystemReadiness>({ method: "GET", path: "/api/readiness" });
  });

  ipcMain.handle(IPC_CHANNELS.backendStatus, (event) => {
    assertTrustedSender(event, resolveWindow);
    return backendManager.getStatus();
  });

  ipcMain.handle(IPC_CHANNELS.backendRequest, async (event, request: BackendRequest) => {
    assertTrustedSender(event, resolveWindow);

    if (!request || typeof request !== "object" || typeof request.path !== "string") {
      throw new Error("Invalid local application-service request.");
    }

    if (!allowsRendererBackendRequest(request)) {
      throw new Error("The desktop interface cannot impersonate a physical controller or vision engine.");
    }

    return backendManager.request(request);
  });

  ipcMain.handle(IPC_CHANNELS.exportAnalytics, async (event, query: string): Promise<ExportResult> => {
    const window = assertTrustedSender(event, resolveWindow);

    if (typeof query !== "string") {
      throw new Error("Invalid analytics export request.");
    }

    const date = new Date().toISOString().slice(0, 10);
    const parameters = new URLSearchParams(query.startsWith("?") ? query.slice(1) : query);
    const sessionId = parameters.get("session_id");
    const employeeId = parameters.get("employee_id");
    const reportScope = sessionId
      ? `Session_${sessionId}`
      : employeeId
        ? `Employee_${employeeId}`
        : "Filtered";
    const destination = await dialog.showSaveDialog(window, {
      title: "Save production analytics report",
      defaultPath: `Garment_Production_Analytics_${reportScope}_${date}.xlsx`,
      filters: [{ name: "Microsoft Excel workbook", extensions: ["xlsx"] }],
    });

    if (destination.canceled || !destination.filePath) {
      return { canceled: true };
    }

    const workbook = await backendManager.downloadAnalytics(query);
    await writeFile(destination.filePath, Buffer.from(workbook));
    return { canceled: false, filePath: destination.filePath };
  });

  ipcMain.handle(IPC_CHANNELS.selectValidationVideo, async (event): Promise<ValidationVideoResult> => {
    const window = assertTrustedSender(event, resolveWindow);
    const selected = await dialog.showOpenDialog(window, {
      title: "Choose a recorded sewing-workstation video",
      properties: ["openFile"],
      filters: [
        { name: "Workstation video", extensions: ["mp4", "mov", "avi", "mkv", "m4v", "webm"] },
      ],
    });

    if (selected.canceled || !selected.filePaths[0]) {
      return { canceled: true };
    }

    return {
      canceled: false,
      filePath: selected.filePaths[0],
      fileName: path.basename(selected.filePaths[0]),
    };
  });

  ipcMain.handle(IPC_CHANNELS.liveStreamUrl, (event, sessionId: number): string => {
    assertTrustedSender(event, resolveWindow);

    if (!Number.isSafeInteger(sessionId) || sessionId < 1) {
      throw new Error("Invalid workstation video request.");
    }

    return `${STREAM_PROTOCOL}://live/session/${sessionId}.mjpeg`;
  });

  ipcMain.handle(IPC_CHANNELS.iotSelectDevice, (event, deviceId: string): void => {
    assertTrustedSender(event, resolveWindow);
    if (typeof deviceId !== "string" || !deviceId) {
      throw new Error("Select an available Bluetooth device before connecting.");
    }
    selectBluetoothController(deviceId);
  });

  ipcMain.handle(IPC_CHANNELS.iotCancelSelection, (event): void => {
    assertTrustedSender(event, resolveWindow);
    cancelBluetoothControllerSelection();
  });

  ipcMain.handle(
    IPC_CHANNELS.iotConnection,
    async (event, input: HardwareConnectionInput): Promise<HardwareConnectionResult> => {
      assertTrustedSender(event, resolveWindow);

      if (
        !input ||
        typeof input.device_id !== "string" ||
        !input.device_id ||
        typeof input.device_name !== "string" ||
        !input.device_name.trim() ||
        typeof input.connected !== "boolean" ||
        typeof input.notifications_active !== "boolean"
      ) {
        throw new Error("The physical controller connection could not be verified.");
      }

      const approved = input.connected && input.notifications_active
        ? bindApprovedBluetoothController(input.device_id)
        : hasApprovedBluetoothController(input.device_id);

      if (!approved) {
        throw new Error("Select the controller in the Bluetooth window before connecting it.");
      }

      const result = await backendManager.request<HardwareConnectionResult>({
        method: "POST",
        path: "/api/iot/connection",
        body: input,
      });

      activeHardwareDeviceId =
        input.connected && input.notifications_active ? input.device_id : null;
      return result;
    },
  );

  ipcMain.handle(
    IPC_CHANNELS.iotHardwareEvent,
    async (event, input: HardwareEventInput): Promise<IotEvent> => {
      assertTrustedSender(event, resolveWindow);

      if (
        !input ||
        typeof input.device_id !== "string" ||
        !input.device_id ||
        input.device_id !== activeHardwareDeviceId ||
        typeof input.device_name !== "string" ||
        !input.device_name.trim() ||
        !hasApprovedBluetoothController(input.device_id) ||
        !HARDWARE_BUTTON_EVENTS.some((allowed) => allowed === input.event_type)
      ) {
        throw new Error("The physical operator button event could not be verified.");
      }

      return backendManager.request<IotEvent>({
        method: "POST",
        path: "/api/iot-events",
        body: {
          event_type: input.event_type,
          event_source: "HARDWARE",
          device_name: input.device_name,
          payload: { device_id: input.device_id, ...input.payload },
        },
      });
    },
  );

  ipcMain.handle(IPC_CHANNELS.minimizeWindow, (event) => {
    assertTrustedSender(event, resolveWindow).minimize();
  });

  ipcMain.handle(IPC_CHANNELS.toggleMaximizeWindow, (event): WindowState => {
    const window = assertTrustedSender(event, resolveWindow);

    if (window.isMaximized()) {
      window.unmaximize();
    } else {
      window.maximize();
    }

    return { maximized: window.isMaximized() };
  });

  ipcMain.handle(IPC_CHANNELS.closeWindow, (event) => {
    assertTrustedSender(event, resolveWindow).close();
  });
}
