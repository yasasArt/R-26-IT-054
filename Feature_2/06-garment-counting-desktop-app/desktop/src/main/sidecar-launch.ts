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

  const workingDirectory = path.resolve(context.applicationPath, "..", "backend");
  const virtualEnvironmentPython =
    context.platform === "win32"
      ? path.join(workingDirectory, ".venv", "Scripts", "python.exe")
      : path.join(workingDirectory, ".venv", "bin", "python");
  const executable =
    context.configuredPython ||
    (context.fileExists(virtualEnvironmentPython)
      ? virtualEnvironmentPython
      : context.platform === "win32"
        ? "python"
        : "python3");

  return { executable, arguments: ["-m", "app.main"], workingDirectory, mode: "development" };
}
