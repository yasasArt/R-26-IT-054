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
