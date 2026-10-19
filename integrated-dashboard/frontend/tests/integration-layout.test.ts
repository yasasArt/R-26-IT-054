import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectDirectory = path.resolve(frontendDirectory, "..");

test("every research component has distinct frontend, backend, and trained-model directories", () => {
  for (const feature of ["garment-counter", "garment-rework", "garment-style-colour", "garment-size"]) {
    assert.equal(existsSync(path.join(frontendDirectory, `${feature}-frontend`)), true);
    assert.equal(existsSync(path.join(projectDirectory, "backend", `${feature}-backend`)), true);
    assert.equal(existsSync(path.join(projectDirectory, "models", feature)), true);
  }
});

test("all four Python projects are installed into one shared backend environment", () => {
  const requirements = readFileSync(path.join(projectDirectory, "backend", "requirements.txt"), "utf8");

  assert.match(requirements, /-e \.\/garment-counter-backend\[dev,release\]/);
  assert.match(requirements, /-e \.\/garment-rework-backend\[dev,release\]/);
  assert.match(requirements, /-e \.\/garment-style-colour-backend\[dev,release\]/);
  assert.match(requirements, /-e \.\/garment-size-backend\[dev,release\]/);
  assert.equal(existsSync(path.join(projectDirectory, "backend", "setup_shared_environment.py")), true);
});

test("all supplied feature models stay isolated and retain distinct trained weights", () => {
  const models = [
    path.join(projectDirectory, "models", "garment-counter", "best.pt"),
    path.join(projectDirectory, "models", "garment-rework", "best.pt"),
    path.join(projectDirectory, "models", "garment-style-colour", "best.pt"),
    path.join(projectDirectory, "models", "garment-size", "best_model.pt"),
  ];
  const digests = models.map((filename) => createHash("sha256").update(readFileSync(filename)).digest("hex"));
  assert.equal(new Set(digests).size, models.length);
  assert.equal(existsSync(path.join(projectDirectory, "models", "garment-counter", "best_model.pt")), true);
});

test("the original feature appearances share generated utilities while size CSS remains scoped", () => {
  const stylesheet = readFileSync(path.join(frontendDirectory, "garment-style-colour-frontend", "index.css"), "utf8");
  const sizeStylesheet = readFileSync(path.join(frontendDirectory, "garment-size-frontend", "globals.css"), "utf8");
  const packageJson = JSON.parse(readFileSync(path.join(frontendDirectory, "package.json"), "utf8")) as {
    devDependencies: Record<string, string>;
  };

  assert.match(stylesheet, /@import "tailwindcss\/utilities\.css" layer\(utilities\) source\(none\)/);
  assert.match(stylesheet, /@source "\.\/\*\*\/\*\.\{ts,tsx\}"/);
  assert.match(stylesheet, /garment-rework-frontend/);
  assert.match(stylesheet, /garment-size-frontend/);
  assert.match(sizeStylesheet, /@scope \(\.garment-size-module\)/);
  assert.match(stylesheet, /--color-violet-soft:\s*#F1EDFF/i);
  assert.equal(typeof packageJson.devDependencies["@tailwindcss/postcss"], "string");
});

test("reported cross-feature regressions have explicit integration guards", () => {
  const cameraSetup = readFileSync(
    path.join(frontendDirectory, "garment-counter-frontend", "screens", "DeviceSetupScreen.tsx"),
    "utf8",
  );
  const styleVision = readFileSync(
    path.join(projectDirectory, "backend", "garment-style-colour-backend", "live_webcam_pipeline.py"),
    "utf8",
  );
  const sizeApp = readFileSync(path.join(frontendDirectory, "garment-size-frontend", "SizeApp.tsx"), "utf8");
  const sizeStyles = readFileSync(path.join(frontendDirectory, "garment-size-frontend", "globals.css"), "utf8");
  const startup = readFileSync(
    path.join(frontendDirectory, "src", "renderer", "modules", "platform", "FeatureStartupScreen.tsx"),
    "utf8",
  );
  const platformStyles = readFileSync(
    path.join(frontendDirectory, "src", "renderer", "modules", "platform", "platform.css"),
    "utf8",
  );

  assert.doesNotMatch(cameraSetup, /browserVideoDevices\[Number\(camera\.camera_id\)\]/);
  assert.match(cameraSetup, /label:\s*camera\.label/);
  assert.match(styleVision, /def run_service\(\):/);
  assert.match(styleVision, /THREADSCAN_VISION_PORT/);
  assert.match(styleVision, /host='127\.0\.0\.1'/);
  assert.match(sizeApp, /type="button"[\s\S]*?onClick=\{\(\) => go\(target\)\}/);
  assert.match(sizeStyles, /\.garment-size-module \.sidebar[\s\S]*?-webkit-app-region:\s*no-drag/);
  assert.match(startup, /feature-startup-shell/);
  assert.match(platformStyles, /place-items:\s*center/);
});
