import { readFile, stat } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  session,
  type IpcMainInvokeEvent,
} from "electron";

import { BackendManager } from "./backend-manager.js";
import type {
  ApiRequest,
  PhysicalControllerEvent,
  VisionStartInput,
} from "../shared/api-types.js";

const MAX_IPC_VIDEO_BYTES = 2 * 1024 * 1024 * 1024;
const moduleDirectory = dirname(fileURLToPath(import.meta.url));
let mainWindow: BrowserWindow | null = null;
let backend: BackendManager | null = null;
let rendererUrl = "";

function requireTrustedRenderer(event: IpcMainInvokeEvent): void {
  if (
    !mainWindow ||
    event.sender !== mainWindow.webContents ||
    event.senderFrame !== mainWindow.webContents.mainFrame ||
    event.senderFrame.url !== rendererUrl
  ) {
    throw new Error("Rejected IPC call from an untrusted renderer frame");
  }
}

function requireBackend(): BackendManager {
  if (!backend) throw new Error("Backend manager is not initialized");
  return backend;
}

function registerIpcHandlers(): void {
  ipcMain.handle("garment:api", (event, input: ApiRequest) => {
    requireTrustedRenderer(event);
    return requireBackend().requestFromRenderer(input);
  });
  ipcMain.handle("garment:vision:start", (event, input: VisionStartInput) => {
    requireTrustedRenderer(event);
    return requireBackend().startVision(input);
  });
  ipcMain.handle("garment:vision:stop", (event) => {
    requireTrustedRenderer(event);
    return requireBackend().stopVision();
  });
  ipcMain.handle("garment:vision:status", (event) => {
    requireTrustedRenderer(event);
    return requireBackend().visionStatus();
  });
  ipcMain.handle("garment:vision:preview-frame", (event) => {
    requireTrustedRenderer(event);
    return requireBackend().previewFrame();
  });
  ipcMain.handle("garment:vision:delete-video", (event, videoId: string) => {
    requireTrustedRenderer(event);
    return requireBackend().deleteVideo(videoId);
  });
  ipcMain.handle("garment:vision:choose-video", async (event) => {
    requireTrustedRenderer(event);
    const result = await dialog.showOpenDialog(mainWindow!, {
      properties: ["openFile"],
      filters: [{ name: "Validation video", extensions: ["mp4", "mov", "avi", "mkv", "m4v"] }],
    });
    if (result.canceled || result.filePaths.length !== 1) return null;
    const path = result.filePaths[0];
    if (!path) return null;
    const metadata = await stat(path);
    if (!metadata.isFile() || metadata.size <= 0 || metadata.size > MAX_IPC_VIDEO_BYTES) {
      throw new Error("Selected validation video has an invalid size");
    }
    return requireBackend().uploadVideo(basename(path), await readFile(path));
  });
}

function configureRendererSecurity(): void {
  session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => {
    callback(false);
  });
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [
          "default-src 'self'; img-src 'self' blob: data:; " +
            "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'",
        ],
      },
    });
  });
}

function resolveRendererUrl(): string {
  if (app.isPackaged) {
    return pathToFileURL(join(moduleDirectory, "../renderer/index.html")).toString();
  }
  const candidate = new URL(
    process.env.GARMENT_RENDERER_URL ?? "http://127.0.0.1:5173/",
  );
  if (
    candidate.protocol !== "http:" ||
    !["127.0.0.1", "localhost"].includes(candidate.hostname)
  ) {
    throw new Error("Development renderer must use a loopback HTTP origin");
  }
  return candidate.toString();
}

async function createMainWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    webPreferences: {
      preload: join(moduleDirectory, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  mainWindow.webContents.on("will-attach-webview", (event) => event.preventDefault());
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (url !== rendererUrl) event.preventDefault();
  });
  mainWindow.once("ready-to-show", () => mainWindow?.show());
  await mainWindow.loadURL(rendererUrl);
}

/** Called directly by Electron-main Bluetooth code; it is not exposed in preload. */
export function recordPhysicalControllerEvent(
  input: PhysicalControllerEvent,
) {
  return requireBackend().recordPhysicalControllerEvent(input);
}

void app.whenReady().then(async () => {
  const appDataPath = app.getPath("userData");
  const backendExecutable = app.isPackaged
    ? join(process.resourcesPath, "backend", process.platform === "win32" ? "garment-counter-backend.exe" : "garment-counter-backend")
    : undefined;
  const managerOptions = {
    appDataPath,
    databasePath: join(appDataPath, "garment_counter.db"),
    modelsPath: app.isPackaged
      ? join(process.resourcesPath, "models")
      : resolve(app.getAppPath(), "..", "models"),
    ...(backendExecutable ? { packagedExecutable: backendExecutable } : {}),
    ...(!app.isPackaged
      ? { developmentCommand: {
          command: process.env.PYTHON_EXECUTABLE ?? "python",
          args: ["-m", "uvicorn", "app.main:app"],
          cwd: resolve(app.getAppPath(), ".."),
        } }
      : {}),
    environment: app.isPackaged ? "production" : "development",
  } as const;
  backend = new BackendManager(managerOptions);
  await backend.start();
  rendererUrl = resolveRendererUrl();
  configureRendererSecurity();
  registerIpcHandlers();
  await createMainWindow();
}).catch(() => {
  dialog.showErrorBox(
    "Garment Counter startup failed",
    "The secure local backend could not be started.",
  );
  app.exit(1);
});

app.on("before-quit", (event) => {
  if (backend?.running) {
    event.preventDefault();
    void backend.stop().finally(() => app.quit());
  }
});

app.on("window-all-closed", () => app.quit());
