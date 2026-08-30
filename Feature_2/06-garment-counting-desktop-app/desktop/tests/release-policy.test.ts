import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { resolveSidecarLaunchPlan } from "../src/main/sidecar-launch.ts";
import {
  missingReleaseModels,
  missingReleaseBranding,
  repairFrozenTorchNumpySource,
  REQUIRED_MODEL_FILES,
  sidecarExecutableName,
  validateReleaseManifest,
  type ReleaseManifest,
} from "../src/shared/release-policy.ts";

function manifest(platform: NodeJS.Platform = "darwin", architecture = "arm64"): ReleaseManifest {
  return {
    applicationVersion: "1.0.2",
    platform,
    architecture,
    preparedAt: "2026-01-01T00:00:00.000Z",
    executable: sidecarExecutableName(platform),
    modelChecksums: Object.fromEntries(REQUIRED_MODEL_FILES.map((filename) => [filename, "sha256"])),
  };
}

test("packaged desktop applications launch only the bundled platform-specific sidecar", () => {
  const plan = resolveSidecarLaunchPlan({
    packaged: true,
    applicationPath: "/application/app.asar",
    resourcesPath: "/application/resources",
    platform: "darwin",
    configuredPython: "/unsafe/system/python",
    fileExists: () => true,
  });

  assert.equal(plan.mode, "bundled");
  assert.equal(plan.executable, path.join("/application/resources", "sidecar", "garment-counter-sidecar"));
  assert.deepEqual(plan.arguments, []);
});

test("missing packaged sidecars never fall back to an installed system Python", () => {
  assert.throws(
    () => resolveSidecarLaunchPlan({
      packaged: true,
      applicationPath: "/application/app.asar",
      resourcesPath: "/application/resources",
      platform: "win32",
      configuredPython: "python.exe",
      fileExists: () => false,
    }),
    /bundled application service is missing/i,
  );

  assert.equal(sidecarExecutableName("win32"), "garment-counter-sidecar.exe");
  assert.equal(sidecarExecutableName("darwin"), "garment-counter-sidecar");
});

test("development continues to use the existing backend virtual environment", () => {
  const plan = resolveSidecarLaunchPlan({
    packaged: false,
    applicationPath: "/project/desktop",
    resourcesPath: "/unused/resources",
    platform: "darwin",
    fileExists: (filename) => filename.endsWith(path.join(".venv", "bin", "python")),
  });

  assert.equal(plan.mode, "development");
  assert.equal(plan.executable, path.join("/project/backend", ".venv", "bin", "python"));
  assert.deepEqual(plan.arguments, ["-m", "app.main"]);
});

test("release packaging rejects missing trained models", () => {
  const missing = missingReleaseModels(
    "/models",
    path.join,
    (filename) => !filename.endsWith("best_model.pt"),
  );

  assert.deepEqual(missing, ["best_model.pt"]);
});

test("release packaging requires native macOS and Windows application icons", () => {
  const missing = missingReleaseBranding(
    "/branding",
    path.join,
    (filename) => !filename.endsWith("icon.icns"),
  );

  assert.deepEqual(missing, ["icon.icns"]);
});

test("frozen PyTorch compatibility avoids module-scope vars loop-name failures", () => {
  const original = "for name in values:\n    vars()[name] = build(name)\nvars()[name] = other\n";

  assert.equal(
    repairFrozenTorchNumpySource(original),
    "for name in values:\n    globals()[name] = build(name)\nglobals()[name] = other\n",
  );
  assert.equal(repairFrozenTorchNumpySource("globals()[name] = existing"), "globals()[name] = existing");
});

test("release manifests cannot silently mix target operating systems or CPU architectures", () => {
  assert.equal(validateReleaseManifest(manifest(), "darwin", "arm64"), null);
  assert.match(validateReleaseManifest(manifest(), "win32", "arm64") || "", /target operating system/i);
  assert.match(validateReleaseManifest(manifest(), "darwin", "x64") || "", /target CPU architecture/i);
});

test("release manifests include all production model integrity checksums", () => {
  const invalid = manifest();
  delete invalid.modelChecksums["best.pt"];

  assert.match(validateReleaseManifest(invalid, "darwin", "arm64") || "", /best\.pt/);
});
