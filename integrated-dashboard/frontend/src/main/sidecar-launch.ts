import path from "node:path";

import { sidecarExecutableName } from "../shared/release-policy.ts";

export interface SidecarLaunchContext {
  packaged: boolean;
  applicationPath: string;
  resourcesPath: string;
  platform: NodeJS.Platform;
  configuredPython?: string;
  fileExists: (filename: string) => boolean;
}

export interface SidecarLaunchPlan {
  executable: string;
  arguments: string[];
  workingDirectory: string;
  mode: "bundled" | "development";
}

export function resolveSidecarLaunchPlan(context: SidecarLaunchContext): SidecarLaunchPlan {
  if (context.packaged) {
    const workingDirectory = path.join(context.resourcesPath, "sidecar");
    const executable = path.join(workingDirectory, sidecarExecutableName(context.platform));

    if (!context.fileExists(executable)) {
      throw new Error(
        "The bundled application service is missing or damaged. Reinstall Garment Counter from the official installer.",
      );
    }

    return { executable, arguments: [], workingDirectory, mode: "bundled" };
  }

  const projectRoot = path.dirname(context.applicationPath);
  const backendRoot = path.join(projectRoot, "backend");
  const workingDirectory = path.join(backendRoot, "garment-counter-backend");
  const virtualEnvironmentPython =
    context.platform === "win32"
      ? path.join(backendRoot, ".venv", "Scripts", "python.exe")
      : path.join(backendRoot, ".venv", "bin", "python");

  if (!context.configuredPython && !context.fileExists(virtualEnvironmentPython)) {
    throw new Error(
      "The shared Python environment is missing. From the project root, run " +
      "python3.12 backend/setup_shared_environment.py before starting the application.",
    );
  }

  const executable =
    context.configuredPython ||
    virtualEnvironmentPython;

  return { executable, arguments: ["-m", "app.main"], workingDirectory, mode: "development" };
}
