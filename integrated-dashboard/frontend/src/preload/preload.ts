import { contextBridge, ipcRenderer } from "electron";

import { IPC_CHANNELS } from "../shared/ipc-channels";
import type {
  BackendRequest,
  BackendStatus,
  DesktopApi,
  DesktopAppInfo,
  DiscoveredBluetoothDevice,
  ExportResult,
  HardwareConnectionInput,
  HardwareConnectionResult,
  HardwareEventInput,
  IotEvent,
  SystemReadiness,
  ValidationVideoResult,
  WindowState,
} from "../shared/types";

const desktopApi: DesktopApi = {
  getAppInfo: () => ipcRenderer.invoke(IPC_CHANNELS.appInfo) as Promise<DesktopAppInfo>,
  checkReadiness: () => ipcRenderer.invoke(IPC_CHANNELS.readiness) as Promise<SystemReadiness>,
  getBackendStatus: () => ipcRenderer.invoke(IPC_CHANNELS.backendStatus) as Promise<BackendStatus>,
  backendRequest: <T>(request: BackendRequest) =>
    ipcRenderer.invoke(IPC_CHANNELS.backendRequest, request) as Promise<T>,
  startStyleServices: () =>
    ipcRenderer.invoke(IPC_CHANNELS.styleBackendStart) as Promise<BackendStatus>,
  getStyleBackendStatus: () =>
    ipcRenderer.invoke(IPC_CHANNELS.styleBackendStatus) as Promise<BackendStatus>,
  stopStyleCamera: () =>
    ipcRenderer.invoke(IPC_CHANNELS.styleStopCamera) as Promise<void>,
  startReworkService: () =>
    ipcRenderer.invoke(IPC_CHANNELS.reworkBackendStart) as Promise<BackendStatus>,
  getReworkBackendStatus: () =>
    ipcRenderer.invoke(IPC_CHANNELS.reworkBackendStatus) as Promise<BackendStatus>,
  reworkRequest: <T>(request: { method: "GET" | "POST"; path: string; body?: unknown }) =>
    ipcRenderer.invoke(IPC_CHANNELS.reworkBackendRequest, request) as Promise<T>,
  stopReworkCamera: () =>
    ipcRenderer.invoke(IPC_CHANNELS.reworkStopCamera) as Promise<void>,
  getReworkStreamUrl: () =>
    ipcRenderer.invoke(IPC_CHANNELS.reworkStreamUrl) as Promise<string>,
  startSizeService: () =>
    ipcRenderer.invoke(IPC_CHANNELS.sizeBackendStart) as Promise<BackendStatus>,
  getSizeBackendStatus: () =>
    ipcRenderer.invoke(IPC_CHANNELS.sizeBackendStatus) as Promise<BackendStatus>,
  sizeApiGet: (path: string) =>
    ipcRenderer.invoke(IPC_CHANNELS.sizeBackendGet, path) as Promise<unknown>,
  sizeApiRequest: <T>(request: { method: "POST" | "DELETE"; path: string; body?: unknown }) =>
    ipcRenderer.invoke(IPC_CHANNELS.sizeBackendRequest, request) as Promise<T>,
  sizeApiMeasure: (payload) =>
    ipcRenderer.invoke(IPC_CHANNELS.sizeBackendMeasure, payload) as Promise<unknown>,
  exportAnalytics: (query: string) =>
    ipcRenderer.invoke(IPC_CHANNELS.exportAnalytics, query) as Promise<ExportResult>,
  selectValidationVideo: () =>
    ipcRenderer.invoke(IPC_CHANNELS.selectValidationVideo) as Promise<ValidationVideoResult>,
  getLiveStreamUrl: (sessionId: number) =>
    ipcRenderer.invoke(IPC_CHANNELS.liveStreamUrl, sessionId) as Promise<string>,
  onBluetoothDevices: (listener: (devices: DiscoveredBluetoothDevice[]) => void) => {
    const receiveDevices = (_event: Electron.IpcRendererEvent, devices: DiscoveredBluetoothDevice[]) => {
      listener(devices);
    };

    ipcRenderer.on(IPC_CHANNELS.iotDiscoveredDevices, receiveDevices);
    return () => ipcRenderer.removeListener(IPC_CHANNELS.iotDiscoveredDevices, receiveDevices);
  },
  selectBluetoothDevice: (deviceId: string) =>
    ipcRenderer.invoke(IPC_CHANNELS.iotSelectDevice, deviceId) as Promise<void>,
  cancelBluetoothSelection: () =>
    ipcRenderer.invoke(IPC_CHANNELS.iotCancelSelection) as Promise<void>,
  syncIotConnection: (input: HardwareConnectionInput) =>
    ipcRenderer.invoke(IPC_CHANNELS.iotConnection, input) as Promise<HardwareConnectionResult>,
  submitHardwareEvent: (input: HardwareEventInput) =>
    ipcRenderer.invoke(IPC_CHANNELS.iotHardwareEvent, input) as Promise<IotEvent>,
  minimizeWindow: () => ipcRenderer.invoke(IPC_CHANNELS.minimizeWindow) as Promise<void>,
  toggleMaximizeWindow: () => ipcRenderer.invoke(IPC_CHANNELS.toggleMaximizeWindow) as Promise<WindowState>,
  closeWindow: () => ipcRenderer.invoke(IPC_CHANNELS.closeWindow) as Promise<void>,
};

contextBridge.exposeInMainWorld("garmentDesktop", desktopApi);
