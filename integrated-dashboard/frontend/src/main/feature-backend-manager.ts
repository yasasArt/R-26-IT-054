import { app } from "electron";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { existsSync } from "node:fs";
import { createServer } from "node:net";
import path from "node:path";

import type { BackendStatus } from "../shared/types";

interface FeatureConfiguration {
  id: "rework" | "size";
  label: string;
  backendDirectory: string;
  modelDirectory: string;
  modelFilename: string;
  packagedExecutable: string;
  healthPath: string;
  environment(modelPath: string, dataDirectory: string): NodeJS.ProcessEnv;
}

function allocateLocalPort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("A local feature-service port could not be allocated."));
        return;
      }
      server.close((error) => error ? reject(error) : resolve(address.port));
    });
  });
}

function pause(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export class FeatureBackendManager {
  private child: ChildProcessWithoutNullStreams | null = null;
  private port: number | null = null;
  private startPromise: Promise<void> | null = null;
  private recentLogs: string[] = [];
  private status: BackendStatus = { state: "stopped", message: "The feature service is stopped." };

  constructor(private readonly configuration: FeatureConfiguration) {}

  getStatus(): BackendStatus {
    return { ...this.status };
  }

  start(): Promise<void> {
    if (this.status.state === "ready") return Promise.resolve();
    if (this.startPromise) return this.startPromise;
    this.startPromise = this.startProcess().finally(() => { this.startPromise = null; });
    return this.startPromise;
  }

  private async startProcess(): Promise<void> {
    this.status = { state: "starting", message: `Starting ${this.configuration.label}…` };
    this.port = await allocateLocalPort();
    const plan = this.resolveLaunchPlan();
    const dataDirectory = path.join(app.getPath("userData"), "features", this.configuration.id);
    const environment: NodeJS.ProcessEnv = {
      ...process.env,
      PYTHONUNBUFFERED: "1",
      GARMENT_FEATURE_PORT: String(this.port),
      YOLO_CONFIG_DIR: path.join(dataDirectory, "ultralytics"),
      MPLCONFIGDIR: path.join(dataDirectory, "matplotlib"),
      ...this.configuration.environment(plan.modelPath, dataDirectory),
    };

    this.child = spawn(plan.command, plan.arguments, {
      cwd: plan.backendDirectory,
      env: environment,
      stdio: "pipe",
      windowsHide: true,
    });
    this.child.stdout.on("data", (data: Buffer) => this.rememberLog(data));
    this.child.stderr.on("data", (data: Buffer) => this.rememberLog(data));
    this.child.once("error", (error) => {
      this.status = { state: "error", message: `${this.configuration.label} could not start. ${error.message}` };
      this.child = null;
    });
    this.child.once("exit", (code) => {
      this.child = null;
      if (this.status.state !== "stopped") {
        this.status = {
          state: "error",
          message: this.recentLogs.at(-1) || `${this.configuration.label} exited unexpectedly${code === null ? "." : ` (${code}).`}`,
        };
      }
    });

    const deadline = Date.now() + (app.isPackaged ? 120_000 : 60_000);
    while (Date.now() < deadline) {
      if (this.status.state === "error") throw new Error(this.status.message);
      try {
        const response = await fetch(`${this.baseUrl()}${this.configuration.healthPath}`, {
          signal: AbortSignal.timeout(900),
        });
        if (response.ok) {
          this.status = { state: "ready", message: `${this.configuration.label} is ready.` };
          return;
        }
      } catch {
        // Model loading can take several seconds on first use.
      }
      await pause(350);
    }
    this.status = { state: "error", message: this.recentLogs.at(-1) || `${this.configuration.label} did not become ready.` };
    this.stop();
    throw new Error(this.status.message);
  }

  private resolveLaunchPlan(): { command: string; arguments: string[]; backendDirectory: string; modelPath: string } {
    const projectRoot = app.isPackaged ? process.resourcesPath : path.resolve(app.getAppPath(), "..");
    const modelPath = path.join(projectRoot, "models", this.configuration.modelDirectory, this.configuration.modelFilename);
    if (!existsSync(modelPath)) throw new Error(`${this.configuration.label} model is missing: ${modelPath}`);

    if (app.isPackaged) {
      const backendDirectory = path.join(process.resourcesPath, "feature-sidecars", this.configuration.id);
      const executable = path.join(
        backendDirectory,
        process.platform === "win32" ? `${this.configuration.packagedExecutable}.exe` : this.configuration.packagedExecutable,
      );
      if (!existsSync(executable)) throw new Error(`${this.configuration.label} packaged service is missing. Rebuild the installer.`);
      return { command: executable, arguments: [], backendDirectory, modelPath };
    }

    const backendRoot = path.join(projectRoot, "backend");
    const backendDirectory = path.join(backendRoot, this.configuration.backendDirectory);
    const python = process.env.GARMENT_INTELLIGENCE_PYTHON?.trim() || path.join(
      backendRoot,
      ".venv",
      process.platform === "win32" ? path.join("Scripts", "python.exe") : path.join("bin", "python"),
    );
    if (!existsSync(python)) {
      throw new Error("The shared Python environment is missing. Run python3.12 backend/setup_shared_environment.py.");
    }
    if (!existsSync(path.join(backendDirectory, "main.py"))) throw new Error(`${this.configuration.label} backend source is missing.`);
    return {
      command: python,
      arguments: ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", String(this.port)],
      backendDirectory,
      modelPath,
    };
  }

  async request<T>(method: "GET" | "POST" | "DELETE", requestPath: string, body?: unknown): Promise<T> {
    if (this.status.state !== "ready") throw new Error(this.status.message);
    const response = await fetch(`${this.baseUrl()}${requestPath}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(30_000),
    });
    const text = await response.text();
    if (!response.ok) throw new Error(text || `${this.configuration.label} returned ${response.status}.`);
    return (text ? JSON.parse(text) : {}) as T;
  }

  async measure(payload: { bytes: ArrayBuffer; fileName: string; mimeType: string; garmentType: string }): Promise<unknown> {
    if (this.status.state !== "ready") throw new Error(this.status.message);
    if (!(payload.bytes instanceof ArrayBuffer) || payload.bytes.byteLength > 15 * 1024 * 1024) {
      throw new Error("Invalid garment measurement frame.");
    }
    const form = new FormData();
    form.append("file", new Blob([payload.bytes], { type: payload.mimeType || "image/jpeg" }), payload.fileName || "garment.jpg");
    form.append("garment_type", payload.garmentType);
    const response = await fetch(`${this.baseUrl()}/measure`, { method: "POST", body: form, signal: AbortSignal.timeout(45_000) });
    const text = await response.text();
    if (!response.ok) throw new Error(text || `Size detection returned ${response.status}.`);
    return text ? JSON.parse(text) : {};
  }

  async openStream(requestPath: string): Promise<Response> {
    if (this.status.state !== "ready") throw new Error(this.status.message);
    // The 10 s limit applies to connecting only. An AbortSignal.timeout()
    // passed to fetch would also abort the endless MJPEG body after 10 s,
    // freezing the Rework video (and its counting, which runs while the
    // stream is read).
    const controller = new AbortController();
    const connectTimer = setTimeout(() => controller.abort(), 10_000);
    let response: Response;
    try {
      response = await fetch(`${this.baseUrl()}${requestPath}`, { signal: controller.signal });
    } finally {
      clearTimeout(connectTimer);
    }
    if (!response.ok || !response.body) throw new Error("The feature video stream is unavailable.");
    return new Response(response.body, { status: 200, headers: { "Content-Type": response.headers.get("Content-Type") || "multipart/x-mixed-replace; boundary=frame", "Cache-Control": "no-store" } });
  }

  stop(): void {
    this.status = { state: "stopped", message: `${this.configuration.label} is stopped.` };
    this.child?.kill();
    this.child = null;
    this.port = null;
  }

  private baseUrl(): string {
    if (!this.port) throw new Error(`${this.configuration.label} has no active port.`);
    return `http://127.0.0.1:${this.port}`;
  }

  private rememberLog(data: Buffer): void {
    const lines = data.toString("utf8").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    this.recentLogs.push(...lines);
    this.recentLogs = this.recentLogs.slice(-30);
  }
}

export const reworkBackendManager = new FeatureBackendManager({
  id: "rework",
  label: "Rework Counter",
  backendDirectory: "garment-rework-backend",
  modelDirectory: "garment-rework",
  modelFilename: "best.pt",
  packagedExecutable: "garment-rework-backend",
  healthPath: "/health",
  environment: (modelPath, dataDirectory) => ({ GARMENT_REWORK_MODEL_PATH: modelPath, GARMENT_REWORK_DATA_DIR: dataDirectory }),
});

export const sizeBackendManager = new FeatureBackendManager({
  id: "size",
  label: "Garment Size Detection",
  backendDirectory: "garment-size-backend",
  modelDirectory: "garment-size",
  modelFilename: "best_model.pt",
  packagedExecutable: "garment-size-backend",
  healthPath: "/health",
  environment: (modelPath, dataDirectory) => ({ GARMENT_MODEL_PATH: modelPath, THREADSCAN_DATA_DIR: dataDirectory }),
});
