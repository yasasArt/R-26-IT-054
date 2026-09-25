import { app, BrowserWindow } from "electron";

import { backendManager } from "./backend-manager";
import { registerDesktopIpc } from "./ipc";
import { registerApplicationProtocolScheme, registerWorkstationStreamProtocol } from "./protocol";
import { createMainWindow, getMainWindow } from "./window-manager";

registerApplicationProtocolScheme();

app.setAppUserModelId("lk.zgen.garmentcounter");

const hasSingleInstanceLock = app.requestSingleInstanceLock();

if (!hasSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    const existingWindow = getMainWindow();

    if (!existingWindow) return;
    if (existingWindow.isMinimized()) existingWindow.restore();

    existingWindow.focus();
  });

  app.whenReady().then(async () => {
    registerDesktopIpc(getMainWindow);
    registerWorkstationStreamProtocol();
    await createMainWindow();
    void backendManager.start().catch(() => {
      // The renderer receives a safe, actionable startup message through the IPC status endpoint.
    });

    app.on("activate", async () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        await createMainWindow();
      }
    });
  });
}

app.on("before-quit", () => {
  backendManager.stop();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
