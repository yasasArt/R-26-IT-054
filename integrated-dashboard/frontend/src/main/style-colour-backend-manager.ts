import { app } from "electron";
import { spawn, spawnSync, type ChildProcessWithoutNullStreams } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

import type { BackendStatus } from "../shared/types";

const API_PORT = 8000;
const VISION_PORT = 5050;
const STARTUP_TIMEOUT_MS = 120_000;
const HEALTH_POLL_INTERVAL_MS = 400;

interface PackingProcess {
  name: "API" | "vision";
  child: ChildProcessWithoutNullStreams;
}

function pause(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export class StyleColourBackendManager {
  private processes: PackingProcess[] = [];

  private startPromise: Promise<void> | null = null;

  private stopping = false;

  private recentLogs: string[] = [];

  private processLogs: Record<PackingProcess["name"], string[]> = { API: [], vision: [] };

  private status: BackendStatus = {
    state: "stopped",
    message: "The style and colour detection services have not started yet.",
  };

  getStatus(): BackendStatus {
    return { ...this.status };
  }

  start(): Promise<void> {
    if (this.status.state === "ready") return Promise.resolve();
    if (this.startPromise) return this.startPromise;

    this.startPromise = this.startProcesses()
      .catch((error: unknown) => {
        this.status = {
          state: "error",
          message: error instanceof Error ? error.message : "The style and colour services could not start.",
        };
        throw error;
      })
      .finally(() => {
        this.startPromise = null;
      });
    return this.startPromise;
  }

  private async startProcesses(): Promise<void> {
    this.stopping = false;
    this.status = { state: "starting", message: "Starting ThreadScan style and colour services…" };
    this.recentLogs = [];
    this.processLogs = { API: [], vision: [] };

    const [apiAlreadyReady, visionAlreadyReady] = await Promise.all([
      this.isApiReady(),
      this.isVisionReady(),
    ]);
    if (apiAlreadyReady && visionAlreadyReady) {
      this.status = { state: "ready", message: "The style and colour detection services are ready." };
      return;
    }

    const plan = this.resolveLaunchPlan();
    // Packaged installs keep using the writable userData directory - resourcesPath is
    // read-only after install and gets wiped on reinstall/update. In an ordinary dev
    // checkout, the database lives in a "data" folder next to the backend source itself
    // (backend/garment-style-colour-backend/data/threadscan.db), matching the size/rework
    // feature backends' own convention, so it's easy to find and inspect directly.
    const dataDirectory = app.isPackaged
      ? path.join(app.getPath("userData"), "features", "garment-style-colour")
      : path.join(plan.backendDirectory, "data");
    const environment: NodeJS.ProcessEnv = {
      ...process.env,
      PYTHONUNBUFFERED: "1",
      THREADSCAN_MODEL_PATH: plan.modelPath,
      THREADSCAN_DATA_DIR: dataDirectory,
      THREADSCAN_API_PORT: String(API_PORT),
      THREADSCAN_VISION_PORT: String(VISION_PORT),
      THREADSCAN_BACKEND_API_BASE: `http://127.0.0.1:${API_PORT}`,
      YOLO_CONFIG_DIR: path.join(dataDirectory, "ultralytics"),
      MPLCONFIGDIR: path.join(dataDirectory, "matplotlib"),
    };

    if (!apiAlreadyReady) {
      this.spawnProcess("API", plan.command, [...plan.prefixArguments, "api"], plan.backendDirectory, environment);
    }
    if (!visionAlreadyReady) {
      this.spawnProcess("vision", plan.command, [...plan.prefixArguments, "vision"], plan.backendDirectory, environment);
    }

    const deadline = Date.now() + STARTUP_TIMEOUT_MS;
    while (Date.now() < deadline) {
      if (this.status.state === "error") throw new Error(this.status.message);
      if (await this.isThreadScanReady()) {
        this.status = { state: "ready", message: "The style and colour detection services are ready." };
        return;
      }
      await pause(HEALTH_POLL_INTERVAL_MS);
    }

    this.status = {
      state: "error",
      message:
        this.processLogs.vision.at(-1) ||
        this.processLogs.API.at(-1) ||
        "ThreadScan did not become ready. Check its Python environment and YOLO model.",
    };
    this.stop();
    throw new Error(this.status.message);
  }

  private resolveLaunchPlan(): {
    command: string;
    prefixArguments: string[];
    backendDirectory: string;
    modelPath: string;
  } {
    if (app.isPackaged) {
      const backendDirectory = path.join(process.resourcesPath, "style-colour-backend");
      const executable = path.join(
        backendDirectory,
        process.platform === "win32" ? "threadscan-backend.exe" : "threadscan-backend",
      );
      const modelPath = path.join(process.resourcesPath, "models", "garment-style-colour", "best.pt");

      if (!existsSync(executable)) {
        throw new Error("The packaged ThreadScan service is missing. Rebuild the integrated installer.");
      }
      if (!existsSync(modelPath)) {
        throw new Error("The packaged ThreadScan YOLO model is missing. Rebuild the integrated installer.");
      }

      return { command: executable, prefixArguments: [], backendDirectory, modelPath };
    }

    const projectRoot = path.resolve(app.getAppPath(), "..");
    const backendRoot = path.join(projectRoot, "backend");
    const backendDirectory = path.join(backendRoot, "garment-style-colour-backend");
    const modelPath = path.join(projectRoot, "models", "garment-style-colour", "best.pt");
    const configuredPython = process.env.THREADSCAN_PYTHON?.trim();
    const localPython = path.join(
      backendRoot,
      ".venv",
      process.platform === "win32" ? path.join("Scripts", "python.exe") : path.join("bin", "python"),
    );
    if (!configuredPython && !existsSync(localPython)) {
      throw new Error(
        "The shared Python environment is missing. From the project root, run " +
        "python3.12 backend/setup_shared_environment.py before opening Garment Style and Colour Detection.",
      );
    }
    const command = configuredPython || localPython;

    if (!existsSync(path.join(backendDirectory, "launcher.py"))) {
      throw new Error("The independent packing backend source is missing.");
    }
    if (!existsSync(modelPath)) {
      throw new Error("The ThreadScan YOLO model is missing from models/garment-style-colour.");
    }

    this.assertPackingDependencies(command);

    return {
      command,
      prefixArguments: [path.join(backendDirectory, "launcher.py")],
      backendDirectory,
      modelPath,
    };
  }

  private assertPackingDependencies(python: string): void {
    const probe = spawnSync(
      python,
      [
        "-c",
        "import importlib.util,json;mods=('fastapi','uvicorn','flask','flask_cors','cv2','ultralytics');" +
          "print(json.dumps([name for name in mods if importlib.util.find_spec(name) is None]))",
      ],
      { encoding: "utf8", windowsHide: true, timeout: 15_000 },
    );

    if (probe.error || probe.status !== 0) {
      throw new Error(
        "The shared Python environment could not be checked. Run " +
        "python3.12 backend/setup_shared_environment.py from the project root.",
      );
    }

    const missing = JSON.parse(probe.stdout.trim()) as string[];
    if (missing.length > 0) {
      throw new Error(
        `The shared Python environment is missing ${missing.join(", ")}. ` +
        "Run python3.12 backend/setup_shared_environment.py from the project root.",
      );
    }
  }

  private spawnProcess(
    name: PackingProcess["name"],
    command: string,
    arguments_: string[],
    cwd: string,
    environment: NodeJS.ProcessEnv,
  ): void {
    const child = spawn(command, arguments_, {
      cwd,
      env: environment,
      stdio: "pipe",
      windowsHide: true,
    });

    child.stdout.on("data", (data: Buffer) => this.rememberLog(name, data));
    child.stderr.on("data", (data: Buffer) => this.rememberLog(name, data));
    child.once("error", (error) => {
      if (this.stopping) return;
      this.status = { state: "error", message: `The style and colour ${name} service could not start. ${error.message}` };
    });
    child.once("exit", (code) => {
      this.processes = this.processes.filter((entry) => entry.child !== child);
      if (this.stopping) return;
      const processMessage = this.processLogs[name].at(-1);
      this.status = {
        state: "error",
        message: processMessage || `The style and colour ${name} service exited unexpectedly${code === null ? "." : ` (${code}).`}`,
      };
    });

    this.processes.push({ name, child });
  }

  private rememberLog(name: PackingProcess["name"], data: Buffer): void {
    const lines = data.toString("utf8").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    this.processLogs[name].push(...lines);
    this.processLogs[name] = this.processLogs[name].slice(-25);
    for (const line of lines) this.recentLogs.push(`[${name}] ${line}`);
    if (this.recentLogs.length > 40) this.recentLogs.splice(0, this.recentLogs.length - 40);
  }

  private async isThreadScanReady(): Promise<boolean> {
    const [apiReady, visionReady] = await Promise.all([this.isApiReady(), this.isVisionReady()]);
    return apiReady && visionReady;
  }

  private async isApiReady(): Promise<boolean> {
    try {
      const api = await fetch(`http://127.0.0.1:${API_PORT}/`, { signal: AbortSignal.timeout(750) });
      if (!api.ok) return false;
      const payload = (await api.json()) as { message?: string };
      return typeof payload.message === "string" && payload.message.includes("ThreadScan");
    } catch {
      return false;
    }
  }

  private async isVisionReady(): Promise<boolean> {
    try {
      const vision = await fetch(`http://127.0.0.1:${VISION_PORT}/api/pipeline/status`, {
        signal: AbortSignal.timeout(750),
      });
      return vision.ok;
    } catch {
      return false;
    }
  }

  async stopCamera(): Promise<void> {
    if (this.status.state !== "ready") return;
    const response = await fetch(`http://127.0.0.1:${VISION_PORT}/api/device/stop-camera`, {
      method: "POST",
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) throw new Error("The packing camera could not be released.");
  }

  stop(): void {
    this.stopping = true;
    for (const { child } of this.processes) {
      if (!child.killed) child.kill();
    }
    this.processes = [];
    this.startPromise = null;
    this.status = { state: "stopped", message: "The style and colour detection services are stopped." };
  }
}

export const styleColourBackendManager = new StyleColourBackendManager();
