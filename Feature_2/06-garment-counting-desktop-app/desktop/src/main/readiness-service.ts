import { app } from "electron";
import { existsSync } from "node:fs";
import path from "node:path";

import { createPhaseOneReadiness } from "../shared/readiness";
import type { DesktopAppInfo, SystemReadiness } from "../shared/types";

export function getModelResourceDirectory(): string {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "models");
  }

  return path.resolve(app.getAppPath(), "..", "resources", "models");
}

export function getDesktopAppInfo(): DesktopAppInfo {
  return {
    appName: app.getName(),
    appVersion: app.getVersion(),
    electronVersion: process.versions.electron,
    chromiumVersion: process.versions.chrome,
    nodeVersion: process.versions.node,
    platform: process.platform,
    architecture: process.arch,
    packaged: app.isPackaged,
    resourceDirectory: getModelResourceDirectory(),
    userDataDirectory: app.getPath("userData"),
  };
}

export function checkPhaseOneReadiness(): SystemReadiness {
  const modelDirectory = getModelResourceDirectory();

  return createPhaseOneReadiness({
    classifierCheckpointExists: existsSync(path.join(modelDirectory, "best_model.pt")),
    workstationCheckpointExists: existsSync(path.join(modelDirectory, "best.pt")),
  });
}
