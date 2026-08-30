import type { ChildProcess, SpawnOptions } from "node:child_process";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdir } from "node:fs/promises";
import { createServer } from "node:net";
import { basename } from "node:path";
import { randomBytes } from "node:crypto";

import {
  appendQuery,
  assertAllowedRequest,
  type BackendCapability,
  type EndpointRule,
} from "./backend-policy.js";
import type {
  ApiRequest,
  ApiResult,
  BinaryApiResult,
  JsonApiResult,
  JsonValue,
  PhysicalControllerEvent,
  VisionStartInput,
} from "../shared/api-types.js";

export interface BackendCommand {
  command: string;
  args?: readonly string[];
  cwd?: string;
}

export interface BackendManagerOptions {
  appDataPath: string;
  databasePath: string;
  modelsPath: string;
  packagedExecutable?: string;
  developmentCommand?: BackendCommand;
  startupTimeoutMs?: number;
  shutdownTimeoutMs?: number;
  environment?: "development" | "production";
}

export class BackendRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly payload: JsonValue,
  ) {
    super(`Backend request failed with HTTP ${status}`);
  }
}

export async function allocateLoopbackPort(): Promise<number> {
  const server = createServer();
  server.unref();
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  if (!address || typeof address === "string") {
    server.close();
    throw new Error("Unable to allocate a loopback port");
  }
  const port = address.port;
  await new Promise<void>((resolve, reject) =>
    server.close((error) => (error ? reject(error) : resolve())),
  );
  return port;
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function parseFilename(header: string | null): string | undefined {
  if (!header) return undefined;
  const match = /filename="?([^";]+)"?/i.exec(header);
  const captured = match?.[1];
  if (!captured) return undefined;
  const safe = basename(captured).replace(/[^A-Za-z0-9._-]/g, "_");
  return safe || undefined;
}

function isVideoName(name: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9 ._-]*\.(mp4|mov|avi|mkv|m4v)$/i.test(name);
}

export class BackendManager {
  private child: ChildProcess | undefined;
  private privateToken: string | undefined;
  private loopbackBaseUrl: string | undefined;
  private launchError: Error | undefined;

  constructor(private readonly options: BackendManagerOptions) {}

  get running(): boolean {
    return this.child !== undefined && this.child.exitCode === null;
  }

  async start(): Promise<void> {
    if (this.running) throw new Error("Backend process is already running");
    await mkdir(this.options.appDataPath, { recursive: true });
    await mkdir(this.options.modelsPath, { recursive: true });

    const port = await allocateLoopbackPort();
    const token = randomBytes(32).toString("base64url");
    const baseUrl = `http://127.0.0.1:${port}`;
    const command = this.resolveCommand(port);
    const spawnOptions: SpawnOptions = {
      cwd: command.cwd,
      env: {
        ...process.env,
        GARMENT_COUNTER_ENVIRONMENT: this.options.environment ?? "production",
        GARMENT_COUNTER_HOST: "127.0.0.1",
        GARMENT_COUNTER_PORT: String(port),
        GARMENT_COUNTER_API_TOKEN: token,
        GARMENT_COUNTER_APP_DATA_DIR: this.options.appDataPath,
        GARMENT_COUNTER_DATABASE_PATH: this.options.databasePath,
        GARMENT_COUNTER_MODELS_DIR: this.options.modelsPath,
        PYTHONUNBUFFERED: "1",
      },
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    };

    const child = spawn(command.command, [...(command.args ?? [])], spawnOptions);
    child.stdout?.resume();
    child.stderr?.resume();
    child.once("error", () => {
      this.launchError = new Error("Unable to start the backend process");
    });
    this.child = child;
    this.privateToken = token;
    this.loopbackBaseUrl = baseUrl;

    try {
      await this.waitUntilReady(this.options.startupTimeoutMs ?? 30_000);
    } catch (error) {
      await this.stop();
      throw error;
    }
  }

  async stop(): Promise<void> {
    const child = this.child;
    if (child && child.exitCode === null) {
      const exited = once(child, "exit").then(() => true);
      child.kill("SIGTERM");
      const timedOut = delay(this.options.shutdownTimeoutMs ?? 5_000).then(() => false);
      if (!(await Promise.race([exited, timedOut])) && child.exitCode === null) {
        child.kill("SIGKILL");
        await once(child, "exit");
      }
    }
    this.child = undefined;
    this.privateToken = undefined;
    this.loopbackBaseUrl = undefined;
    this.launchError = undefined;
  }

  requestFromRenderer(input: ApiRequest): Promise<ApiResult> {
    return this.perform(input, "renderer");
  }

  visionStatus(): Promise<ApiResult> {
    return this.perform(
      { method: "GET", path: "/api/vision/status" },
      "vision",
    );
  }

  stopVision(): Promise<ApiResult> {
    return this.perform(
      { method: "POST", path: "/api/vision/stop" },
      "vision",
    );
  }

  startVision(input: VisionStartInput): Promise<ApiResult> {
    if (!Number.isSafeInteger(input.sessionId) || input.sessionId < 1) {
      throw new Error("Invalid session ID");
    }
    const body: Record<string, JsonValue> = { source_type: input.sourceType };
    if (input.sourceType === "CAMERA") {
      if (input.videoId !== undefined) throw new Error("Camera input cannot include videoId");
      if (input.cameraIndex !== undefined) body.camera_index = input.cameraIndex;
    } else {
      if (!input.videoId) throw new Error("Video input requires videoId");
      if (input.cameraIndex !== undefined) throw new Error("Video input cannot include cameraIndex");
      body.video_id = input.videoId;
    }
    return this.perform(
      {
        method: "POST",
        path: `/api/vision/sessions/${input.sessionId}/start`,
        body,
      },
      "vision",
    );
  }

  async previewFrame(): Promise<BinaryApiResult> {
    const result = await this.perform(
      { method: "GET", path: "/api/vision/preview/frame" },
      "vision",
    );
    if (result.kind !== "binary") throw new Error("Preview did not return an image");
    return result;
  }

  deleteVideo(videoId: string): Promise<ApiResult> {
    return this.perform(
      { method: "DELETE", path: `/api/vision/videos/${videoId}` },
      "vision",
    );
  }

  recordPhysicalControllerEvent(input: PhysicalControllerEvent): Promise<ApiResult> {
    return this.perform(
      {
        method: "POST",
        path: "/api/trusted/controller-events",
        body: {
          session_id: input.sessionId,
          event_key: input.eventKey,
          event_type: input.eventType,
          occurred_at: input.occurredAt,
          ...(input.deviceName ? { device_name: input.deviceName } : {}),
          ...(input.deviceId ? { device_id: input.deviceId } : {}),
        },
      },
      "controller",
    );
  }

  async uploadVideo(name: string, bytes: Uint8Array): Promise<ApiResult> {
    const safeName = basename(name);
    if (safeName !== name || !isVideoName(safeName)) {
      throw new Error("Invalid validation-video name");
    }
    if (!(bytes instanceof Uint8Array) || bytes.byteLength === 0) {
      throw new Error("Validation video is empty");
    }
    const form = new FormData();
    const ownedBytes = new Uint8Array(bytes.byteLength);
    ownedBytes.set(bytes);
    form.append("file", new Blob([ownedBytes.buffer]), safeName);
    return this.performFetch(
      "/api/vision/videos",
      { method: "POST", body: form },
      "json",
    );
  }

  private resolveCommand(port: number): BackendCommand {
    if (this.options.packagedExecutable) {
      return { command: this.options.packagedExecutable };
    }
    if (this.options.developmentCommand) return this.options.developmentCommand;
    return {
      command: process.env.PYTHON_EXECUTABLE ?? "python",
      args: [
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        String(port),
      ],
    };
  }

  private async waitUntilReady(timeoutMs: number): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (this.launchError) throw this.launchError;
      if (!this.running) throw new Error("Backend exited before becoming ready");
      try {
        const response = await fetch(`${this.loopbackBaseUrl}/health`, {
          redirect: "error",
          signal: AbortSignal.timeout(1_000),
        });
        if (response.ok && (await response.json()).ready === true) return;
      } catch {
        // Startup connection failures are expected until Uvicorn begins listening.
      }
      await delay(100);
    }
    throw new Error("Backend did not become ready before the startup timeout");
  }

  private perform(input: ApiRequest, capability: BackendCapability): Promise<ApiResult> {
    const rule = assertAllowedRequest(input, capability);
    const path = appendQuery(input.path, input.query);
    const init: RequestInit = { method: input.method };
    if (rule.body === "json") {
      init.body = JSON.stringify(input.body);
      init.headers = { "Content-Type": "application/json" };
    }
    return this.performFetch(path, init, rule.response);
  }

  private async performFetch(
    path: string,
    init: RequestInit,
    responseKind: EndpointRule["response"],
  ): Promise<ApiResult> {
    const token = this.privateToken;
    const baseUrl = this.loopbackBaseUrl;
    if (!this.running || !token || !baseUrl) throw new Error("Backend is not running");
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers,
      redirect: "error",
      signal: AbortSignal.timeout(60_000),
    });

    if (!response.ok) {
      let payload: JsonValue = { detail: `HTTP ${response.status}` };
      try {
        payload = (await response.json()) as JsonValue;
      } catch {
        // Return a controlled status without copying an untrusted HTML error page.
      }
      throw new BackendRequestError(response.status, payload);
    }

    if (responseKind === "binary") {
      const filename = parseFilename(response.headers.get("content-disposition"));
      return {
        kind: "binary",
        status: response.status,
        bytes: new Uint8Array(await response.arrayBuffer()),
        contentType: response.headers.get("content-type") ?? "application/octet-stream",
        ...(filename ? { filename } : {}),
      };
    }

    const text = await response.text();
    const result: JsonApiResult = {
      kind: "json",
      status: response.status,
      data: text ? (JSON.parse(text) as JsonValue) : null,
    };
    return result;
  }
}
