import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  chmodSync,
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  FROZEN_TORCH_NUMPY_MODULES,
  missingReleaseBranding,
  missingReleaseModels,
  repairFrozenTorchNumpySource,
  REQUIRED_MODEL_FILES,
  sidecarExecutableName,
} from "../src/shared/release-policy.ts";

const desktopDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectDirectory = path.resolve(desktopDirectory, "..");
const backendDirectory = path.join(projectDirectory, "backend");
const modelDirectory = path.join(projectDirectory, "resources", "models");
const brandingDirectory = path.join(projectDirectory, "resources", "branding");
const sidecarDirectory = path.join(desktopDirectory, "release", "sidecar");
const builtSidecarDirectory = path.join(backendDirectory, "dist", "garment-counter-sidecar");
const packageJson = JSON.parse(readFileSync(path.join(desktopDirectory, "package.json"), "utf8"));
const mode = process.argv[2] || "--release";

function fail(message) {
  console.error(`\nRelease preparation failed: ${message}`);
  process.exitCode = 1;
}

function command(executable, arguments_, options = {}) {
  const result = spawnSync(executable, arguments_, {
    cwd: options.cwd || desktopDirectory,
    stdio: options.capture ? "pipe" : "inherit",
    encoding: "utf8",
    env: { ...process.env, ...options.env },
    windowsHide: true,
    shell: process.platform === "win32" && executable.toLowerCase().endsWith(".cmd"),
  });

  if (result.error) {
    throw new Error(`Could not start ${executable}: ${result.error.message}`);
  }

  if (result.status !== 0) {
    throw new Error(options.message || `${executable} finished unsuccessfully.`);
  }

  return result.stdout?.trim() || "";
}

function resolvePython() {
  if (process.env.GARMENT_COUNTER_PYTHON) {
    return process.env.GARMENT_COUNTER_PYTHON;
  }

  const virtualEnvironment =
    process.platform === "win32"
      ? path.join(backendDirectory, ".venv", "Scripts", "python.exe")
      : path.join(backendDirectory, ".venv", "bin", "python");

  return existsSync(virtualEnvironment)
    ? virtualEnvironment
    : process.platform === "win32"
      ? "python"
      : "python3";
}

function checkModels() {
  const missingModels = missingReleaseModels(modelDirectory, path.join, existsSync);

  if (missingModels.length) {
    throw new Error(`Missing required trained model files: ${missingModels.join(", ")}.`);
  }
}

function checkBranding() {
  const missingBranding = missingReleaseBranding(brandingDirectory, path.join, existsSync);

  if (missingBranding.length) {
    throw new Error(`Missing required production application icons: ${missingBranding.join(", ")}.`);
  }
}

function repairFrozenTorchModules() {
  const possibleDirectories = [
    path.join(sidecarDirectory, "_internal", "torch", "_numpy"),
    path.join(sidecarDirectory, "torch", "_numpy"),
  ];
  const packageDirectory = possibleDirectories.find((directory) =>
    existsSync(path.join(directory, "_ufuncs.py")),
  );

  if (!packageDirectory) {
    throw new Error(
      "PyInstaller did not collect the PyTorch NumPy compatibility package as Python source. " +
      "Verify backend/packaging/hooks/hook-torch._numpy.py is present before building the release.",
    );
  }

  let replacements = 0;

  for (const filename of FROZEN_TORCH_NUMPY_MODULES) {
    const moduleFilename = path.join(packageDirectory, filename);
    if (!existsSync(moduleFilename)) continue;

    const source = readFileSync(moduleFilename, "utf8");
    const repaired = repairFrozenTorchNumpySource(source);

    if (repaired !== source) {
      replacements += (source.match(/vars\(\)\[name\]/g) || []).length;
      writeFileSync(moduleFilename, repaired, "utf8");
    }
  }

  console.log(`  Frozen PyTorch compatibility: ${replacements} module-scope binding${replacements === 1 ? "" : "s"} repaired.`);
}

function inspectPython(python) {
  const inspection = command(
    python,
    [
      "-c",
      [
        "import importlib.util, json, platform, sys",
        "packages = ('PyInstaller', 'fastapi', 'uvicorn', 'cv2', 'torch', 'torchvision', 'ultralytics', 'openpyxl')",
        "print(json.dumps({'version': platform.python_version(), 'missing': [name for name in packages if importlib.util.find_spec(name) is None]}))",
      ].join("; "),
    ],
    { cwd: backendDirectory, capture: true, message: "The backend Python environment could not be inspected." },
  );

  const report = JSON.parse(inspection);

  if (report.missing.length) {
    throw new Error(
      `The backend environment is missing ${report.missing.join(", ")}. Activate backend/.venv and run pip install -e '.[dev,release]'.`,
    );
  }

  const [major, minor] = report.version.split(".").map(Number);

  if (major !== 3 || minor < 11) {
    throw new Error(`Python ${report.version} is unsupported. Create the release environment with Python 3.11 or 3.12.`);
  }

  if (minor > 12) {
    console.warn(`Python ${report.version} is newer than the recommended release versions. Python 3.11 or 3.12 is recommended.`);
  }

  return report;
}

function printPlan(python) {
  console.log("Garment Counter production-release plan");
  console.log(`  Version:       ${packageJson.version}`);
  console.log(`  Platform:      ${process.platform}/${process.arch}`);
  console.log(`  Python:        ${python}`);
  console.log(`  Model folder:  ${modelDirectory}`);
  console.log(`  App branding:  ${brandingDirectory}`);
  console.log(`  Sidecar stage: ${sidecarDirectory}`);
  console.log(`  Installer:     ${process.platform === "darwin" ? "macOS APP + ZIP + DMG" : process.platform === "win32" ? "Windows Setup EXE" : "Target-platform package"}`);
}

function buildSidecar(python) {
  console.log("\n[1/4] Building the standalone Python, AI, camera, database, and reporting service...");
  command(
    python,
    ["-m", "PyInstaller", "--noconfirm", "--clean", path.join("packaging", "garment_counter_sidecar.spec")],
    {
      cwd: backendDirectory,
      env: { GARMENT_COUNTER_BACKEND_ROOT: backendDirectory },
      message: "PyInstaller could not build the offline application service.",
    },
  );

  const executableName = sidecarExecutableName(process.platform);
  const builtExecutable = path.join(builtSidecarDirectory, executableName);

  if (!existsSync(builtExecutable)) {
    throw new Error(`PyInstaller completed without producing ${builtExecutable}.`);
  }

  mkdirSync(path.dirname(sidecarDirectory), { recursive: true });
  rmSync(sidecarDirectory, { recursive: true, force: true });
  cpSync(builtSidecarDirectory, sidecarDirectory, { recursive: true });
  repairFrozenTorchModules();

  if (process.platform !== "win32") {
    chmodSync(path.join(sidecarDirectory, executableName), 0o755);
  }

  const modelChecksums = Object.fromEntries(
    REQUIRED_MODEL_FILES.map((filename) => [
      filename,
      createHash("sha256").update(readFileSync(path.join(modelDirectory, filename))).digest("hex"),
    ]),
  );

  writeFileSync(
    path.join(sidecarDirectory, "release-manifest.json"),
    `${JSON.stringify(
      {
        applicationVersion: packageJson.version,
        platform: process.platform,
        architecture: process.arch,
        preparedAt: new Date().toISOString(),
        executable: executableName,
        modelChecksums,
      },
      null,
      2,
    )}\n`,
  );
}

try {
  checkModels();
  checkBranding();
  const python = resolvePython();
  printPlan(python);

  if (mode === "--plan") {
    console.log("\nThe trained-model resources and release layout are present.");
  } else {
    const report = inspectPython(python);
    console.log(`  Python build:  ${report.version} · all release dependencies available`);

    if (mode === "--doctor") {
      console.log("\nThe production release environment is ready.");
    } else if (mode === "--release" || mode === "--prepare-only") {
      buildSidecar(python);

      console.log("\n[2/4] Verifying the bundled service, security, SQLite, and both genuine AI models...");
      command(process.execPath, [
        "--disable-warning=MODULE_TYPELESS_PACKAGE_JSON",
        "--disable-warning=ExperimentalWarning",
        "--experimental-strip-types",
        path.join("scripts", "smoke-sidecar.mjs"),
      ], {
        message: "The bundled application service or genuine trained AI models did not pass production verification.",
      });

      if (mode === "--prepare-only") {
        console.log(`\nStandalone Python service prepared successfully at ${sidecarDirectory}`);
      } else {
        const npmExecutable = process.platform === "win32" ? "npm.cmd" : "npm";

        console.log("\n[3/4] Running desktop quality, security, and production-build checks...");
        command(npmExecutable, ["run", "verify"], { message: "Desktop verification did not pass." });

        console.log("\n[4/4] Creating the target-platform desktop application and installer...");
        command(npmExecutable, ["run", "make"], { message: "Electron Forge could not create the production installer." });

        if (process.platform === "darwin") {
          command(process.execPath, [path.join("scripts", "create-macos-dmg.mjs")], {
            message: "The macOS application was packaged, but the DMG could not be generated.",
          });
        }

        console.log(`\nGarment Counter ${packageJson.version} release artifacts are available in ${path.join(desktopDirectory, "out")}`);
      }
    } else {
      throw new Error(`Unknown release mode ${mode}.`);
    }
  }
} catch (error) {
  fail(error instanceof Error ? error.message : "An unexpected release error occurred.");
}
