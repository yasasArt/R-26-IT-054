export const REQUIRED_MODEL_FILES = [
  "best_model.pt",
  "best.pt",
  "label_mapping.json",
  "data.yaml",
] as const;

export const REQUIRED_BRANDING_FILES = ["icon.png", "icon.icns", "icon.ico"] as const;

export const FROZEN_TORCH_NUMPY_MODULES = ["_ufuncs.py", "_funcs.py", "_dtypes.py"] as const;

export interface ReleaseManifest {
  applicationVersion: string;
  platform: NodeJS.Platform;
  architecture: string;
  preparedAt: string;
  executable: string;
  modelChecksums: Record<string, string>;
}

export function sidecarExecutableName(platform: NodeJS.Platform): string {
  return platform === "win32" ? "garment-counter-sidecar.exe" : "garment-counter-sidecar";
}

export function missingReleaseModels(
  modelDirectory: string,
  joinPath: (...parts: string[]) => string,
  fileExists: (filename: string) => boolean,
): string[] {
  return REQUIRED_MODEL_FILES.filter((filename) => !fileExists(joinPath(modelDirectory, filename)));
}

export function missingReleaseBranding(
  brandingDirectory: string,
  joinPath: (...parts: string[]) => string,
  fileExists: (filename: string) => boolean,
): string[] {
  return REQUIRED_BRANDING_FILES.filter((filename) => !fileExists(joinPath(brandingDirectory, filename)));
}

export function repairFrozenTorchNumpySource(source: string): string {
  return source.replaceAll("vars()[name]", "globals()[name]");
}

export function validateReleaseManifest(
  manifest: ReleaseManifest,
  platform: NodeJS.Platform,
  architecture: string,
): string | null {
  if (manifest.platform !== platform) {
    return `The Python service was prepared for ${manifest.platform}, not ${platform}. Rebuild it on the target operating system.`;
  }

  if (manifest.architecture !== architecture) {
    return `The Python service was prepared for ${manifest.architecture}, not ${architecture}. Rebuild it on the target CPU architecture.`;
  }

  if (manifest.executable !== sidecarExecutableName(platform)) {
    return "The prepared Python service executable does not match the target operating system.";
  }

  for (const filename of REQUIRED_MODEL_FILES) {
    if (!manifest.modelChecksums[filename]) {
      return `The release manifest does not include an integrity checksum for ${filename}.`;
    }
  }

  return null;
}
