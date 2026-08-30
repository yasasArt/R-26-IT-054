import { app } from "electron";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync } from "node:fs";
import { createServer } from "node:net";
import path from "node:path";

import {
  backendConnectionErrorCode,
  shouldRetryBackendConnection,
} from "../shared/backend-connection-policy";
import type { BackendRequest, BackendStatus } from "../shared/types";
import { getModelResourceDirectory } from "./readiness-service";
import { resolveSidecarLaunchPlan } from "./sidecar-launch";

const DEVELOPMENT_STARTUP_TIMEOUT_MS = 30_000;
const PACKAGED_STARTUP_TIMEOUT_MS = 90_000;
const HEALTH_POLL_INTERVAL_MS = 250;

function allocateLocalPort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();

    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();

      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("A localhost port could not be allocated for the application service."));
        return;
      }

      const { port } = address;
      server.close((error) => (error ? reject(error) : resolve(port)));
    });
  });
}

function pause(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export class BackendManager {
  private child: ChildProcessWithoutNullStreams | null = null;

  private port: number | null = null;

  private token: string | null = null;

  private status: BackendStatus = {
    state: "stopped",
    message: "The local application service has not started yet.",
  };

  private recentLogs: string[] = [];

  getStatus(): BackendStatus {
    return { ...this.status };
  }

  async start(): Promise<void> {
    if (this.child || this.status.state === "starting") return;

    this.status = { state: "starting", message: "Starting the local application service…" };
    this.port = await allocateLocalPort();
    this.token = randomBytes(32).toString("hex");

    let launchPlan;

    try {
      launchPlan = resolveSidecarLaunchPlan({
        packaged: app.isPackaged,
        applicationPath: app.getAppPath(),
        resourcesPath: process.resourcesPath,
        platform: process.platform,
        configuredPython: process.env.GARMENT_COUNTER_PYTHON,
        fileExists: existsSync,
      });
    } catch (error) {
      this.status = {
        state: "error",
        message: error instanceof Error ? error.message : "The application service could not be located.",
      };
      throw error;
    }

    const userDataDirectory = app.getPath("userData");

    this.child = spawn(launchPlan.executable, launchPlan.arguments, {
      cwd: launchPlan.workingDirectory,
      stdio: "pipe",
      windowsHide: true,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        GARMENT_COUNTER_PORT: String(this.port),
        GARMENT_COUNTER_AUTH_TOKEN: this.token,
        GARMENT_COUNTER_DATA_DIR: userDataDirectory,
        GARMENT_COUNTER_MODEL_DIR: getModelResourceDirectory(),
        GARMENT_COUNTER_ENVIRONMENT: app.isPackaged ? "production" : "development",
        YOLO_CONFIG_DIR: path.join(userDataDirectory, "ultralytics"),
        MPLCONFIGDIR: path.join(userDataDirectory, "matplotlib"),
        PYTORCH_ENABLE_MPS_FALLBACK: "1",
      },
    });

    this.child.stdout.on("data", (data: Buffer) => this.rememberLog(data));
    this.child.stderr.on("data", (data: Buffer) => this.rememberLog(data));
    this.child.once("error", (error) => {
      this.status = {
        state: "error",
        message: app.isPackaged
          ? `The bundled application service could not start. Reinstall Garment Counter if the problem continues. ${error.message}`
          : `The local service could not start. Check Python dependencies. ${error.message}`,
      };
      this.child = null;
    });
    this.child.once("exit", (code) => {
      if (this.status.state !== "stopped") {
        const finalMessage = this.recentLogs.at(-1);
        this.status = {
          state: "error",
          message:
            finalMessage ||
            `The local application service exited unexpectedly${code === null ? "." : ` (${code}).`}`,
        };
      }

      this.child = null;
    });

    const deadline =
      Date.now() + (app.isPackaged ? PACKAGED_STARTUP_TIMEOUT_MS : DEVELOPMENT_STARTUP_TIMEOUT_MS);

    while (Date.now() < deadline) {
      if (this.status.state === "error") {
        throw new Error(this.status.message);
      }

      try {
        const response = await fetch(`${this.baseUrl()}/api/health`, {
          headers: { Authorization: `Bearer ${this.token}` },
        });

        if (response.ok) {
          this.status = { state: "ready", message: "The local application service is ready." };
          return;
        }
      } catch {
        // The Python process may still be importing its application dependencies.
      }

      await pause(HEALTH_POLL_INTERVAL_MS);
    }

    this.status = {
      state: "error",
      message: app.isPackaged
        ? "The bundled application service did not become ready. Restart Garment Counter or reinstall the application."
        : "The local application service did not become ready. Check the backend setup guide.",
    };
    this.stopChild();
    throw new Error(this.status.message);
  }

  async request<T>(request: BackendRequest): Promise<T> {
    if (this.status.state !== "ready" || !this.port || !this.token) {
      throw new Error(this.status.message);
    }

    if (!["GET", "POST", "PUT"].includes(request.method)) {
      throw new Error("The requested application-service action is not allowed.");
    }

    if (!request.path.startsWith("/api/") || request.path.startsWith("//")) {
      throw new Error("Only local application-service API routes are allowed.");
    }

    const destination = new URL(request.path, this.baseUrl());

    if (destination.origin !== this.baseUrl() || !destination.pathname.startsWith("/api/")) {
      throw new Error("The requested service destination is not allowed.");
    }

    const response = await this.fetchLocal(destination, {
      method: request.method,
      headers: {
        Authorization: `Bearer ${this.token}`,
        ...(request.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: request.body === undefined ? undefined : JSON.stringify(request.body),
    }, `${request.method} ${request.path}`);

    if (!response.ok) {
      const errorPayload = (await response.json().catch(() => null)) as {
        detail?: string | { message?: string; blockers?: string[] };
      } | null;
      const detail = errorPayload?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : detail?.message
            ? `${detail.message}${detail.blockers?.length ? ` ${detail.blockers.join(", ")}.` : ""}`
            : `The application service rejected this request (${response.status}).`;

      console.error(`[BACKEND REQUEST FAILED] ${request.method} ${request.path}: ${message}`);
      throw new Error(`${request.method} ${request.path}: ${message}`);
    }

    return (await response.json()) as T;
  }

  async downloadAnalytics(query: string): Promise<ArrayBuffer> {
    if (this.status.state !== "ready" || !this.port || !this.token) {
      throw new Error(this.status.message);
    }

    if (query && !query.startsWith("?")) {
      throw new Error("Invalid analytics filters.");
    }

    const destination = new URL(`/api/analytics/export.xlsx${query}`, this.baseUrl());
    const response = await this.fetchLocal(destination, {
      headers: { Authorization: `Bearer ${this.token}` },
    }, "GET /api/analytics/export.xlsx");

    if (!response.ok) {
      throw new Error("The filtered Excel report could not be generated.");
    }

    return response.arrayBuffer();
  }

  async openVisionStream(sessionId: number): Promise<Response> {
    if (this.status.state !== "ready" || !this.port || !this.token) {
      throw new Error(this.status.message);
    }

    if (!Number.isSafeInteger(sessionId) || sessionId < 1) {
      throw new Error("The requested workstation stream is invalid.");
    }

    const response = await this.fetchLocal(`${this.baseUrl()}/api/vision/stream/${sessionId}`, {
      headers: { Authorization: `Bearer ${this.token}` },
    }, `GET /api/vision/stream/${sessionId}`);

    if (!response.ok || !response.body) {
      throw new Error("The authenticated workstation camera stream is unavailable.");
    }

    return new Response(response.body, {
      status: 200,
      headers: {
        "Content-Type": response.headers.get("Content-Type") || "multipart/x-mixed-replace; boundary=frame",
        "Cache-Control": "no-store",
      },
    });
  }

  stop(): void {
    this.status = { state: "stopped", message: "The local application service has stopped." };
    this.stopChild();
    this.token = null;
    this.port = null;
  }

  private baseUrl(): string {
    return `http://127.0.0.1:${this.port}`;
  }

  private async fetchLocal(
    destination: string | URL,
    options: RequestInit,
    operation: string,
  ): Promise<Response> {
    const method = options.method || "GET";

    for (let attempt = 0; ; attempt += 1) {
      try {
        return await fetch(destination, options);
      } catch (caughtError) {
        if (
          this.status.state === "ready" &&
          this.child &&
          !this.child.killed &&
          shouldRetryBackendConnection(method, attempt, caughtError)
        ) {
          await pause(150 * (attempt + 1));
          continue;
        }

        const code = backendConnectionErrorCode(caughtError);
        const detail = code ? ` (${code})` : "";
        const message = `${operation}: The local application service connection was interrupted${detail}.`;
        console.error(`[BACKEND CONNECTION FAILED] ${message}`);
        throw new Error(message, { cause: caughtError });
      }
    }
  }

  private stopChild(): void {
    if (!this.child) return;

    const child = this.child;
    child.kill();

    const forceClose = setTimeout(() => {
      if (!child.killed) child.kill("SIGKILL");
    }, 2_500);

    forceClose.unref();
  }

  private rememberLog(data: Buffer): void {
    const message = data.toString("utf8").trim();
    if (!message) return;

    if (/traceback|exception|error:/i.test(message)) {
      console.error("[PYTHON BACKEND ERROR]\n", message);
    }

    this.recentLogs.push(message);
    this.recentLogs = this.recentLogs.slice(-8);
  }
}

export const backendManager = new BackendManager();
