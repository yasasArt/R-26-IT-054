import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { sidecarExecutableName } from "../src/shared/release-policy.ts";

const desktopDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sidecarDirectory = path.join(desktopDirectory, "release", "sidecar");
const executable = path.join(sidecarDirectory, sidecarExecutableName(process.platform));
const modelDirectory = path.resolve(desktopDirectory, "..", "resources", "models");
const token = randomBytes(32).toString("hex");
const dataDirectory = mkdtempSync(path.join(os.tmpdir(), "garment-counter-release-smoke-"));
let child;
let recentOutput = "";

function errorDetails(error) {
  if (!(error instanceof Error)) return "An unknown localhost connection error occurred.";

  const cause = error.cause;
  const underlying = cause instanceof Error ? cause : null;
  const code = underlying && "code" in underlying ? underlying.code : null;
  const explanation = underlying?.message || error.message;

  return `${explanation}${code ? ` (${code})` : ""}`;
}

async function requestWithRetry(url, options, description) {
  let lastError = null;

  for (let attempt = 0; attempt < 8; attempt += 1) {
    if (child.exitCode !== null) {
      throw new Error(
        `The bundled Python service exited while ${description} (${child.exitCode}).${
          recentOutput ? `\nBackend output:\n${recentOutput}` : ""
        }`,
      );
    }

    try {
      return await fetch(url, options);
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 200 * (attempt + 1)));
    }
  }

  throw new Error(
    `The bundled Python service connection failed while ${description}: ${errorDetails(lastError)}.${
      recentOutput ? `\nBackend output:\n${recentOutput}` : ""
    }`,
  );
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();

      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("A release smoke-test localhost port could not be allocated."));
        return;
      }

      server.close((error) => error ? reject(error) : resolve(address.port));
    });
  });
}

async function waitForHealth(baseUrl) {
  const deadline = Date.now() + 120_000;

  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`The frozen Python service exited (${child.exitCode}). ${recentOutput}`);
    }

    try {
      const response = await fetch(`${baseUrl}/api/health`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        return response.json();
      }
    } catch {
      // Scientific-library imports can take longer on the first frozen start.
    }

    await new Promise((resolve) => setTimeout(resolve, 300));
  }

  throw new Error(`The frozen Python service never became healthy. ${recentOutput}`);
}

async function verifyRealModels(baseUrl) {
  const headers = { Authorization: `Bearer ${token}` };
  const loadResponse = await requestWithRetry(
    `${baseUrl}/api/vision/models/load`,
    { method: "POST", headers },
    "starting genuine trained-model verification",
  );

  if (!loadResponse.ok) {
    throw new Error(`The bundled service rejected genuine AI model initialization (${loadResponse.status}).`);
  }

  console.log("  Loading the genuine YOLO workstation detector and temporal garment classifier...");
  const deadline = Date.now() + 300_000;

  while (Date.now() < deadline) {
    const response = await requestWithRetry(
      `${baseUrl}/api/vision/models`,
      { headers },
      "verifying bundled trained-model readiness",
    );

    if (!response.ok) {
      throw new Error(`The bundled service could not report trained-model readiness (${response.status}).`);
    }

    const status = await response.json();
    const failed = [
      ["Workstation detector", status.detector],
      ["Garment classifier", status.classifier],
    ].filter(([, model]) => model?.state === "FAILED");

    if (failed.length) {
      throw new Error(
        `The installed application would ship with unusable trained AI models:\n${
          failed.map(([label, model]) => `  ${label}: ${model.message}`).join("\n")
        }${recentOutput ? `\nBackend diagnostics:\n${recentOutput}` : ""}`,
      );
    }

    if (status.ready && status.detector?.state === "READY" && status.classifier?.state === "READY") {
      console.log("  Genuine workstation detector: READY");
      console.log(`  Genuine temporal garment classifier: READY (${status.classifier.device || "default device"})`);
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, 400));
  }

  throw new Error(
    `The bundled trained AI models did not become ready within five minutes.${
      recentOutput ? `\nBackend diagnostics:\n${recentOutput}` : ""
    }`,
  );
}

try {
  if (!existsSync(executable)) {
    throw new Error(`The staged standalone application service does not exist: ${executable}`);
  }

  const port = await freePort();
  const baseUrl = `http://127.0.0.1:${port}`;
  child = spawn(executable, [], {
    cwd: sidecarDirectory,
    windowsHide: true,
    stdio: "pipe",
    env: {
      ...process.env,
      GARMENT_COUNTER_PORT: String(port),
      GARMENT_COUNTER_AUTH_TOKEN: token,
      GARMENT_COUNTER_DATA_DIR: dataDirectory,
      GARMENT_COUNTER_MODEL_DIR: modelDirectory,
      // Start quickly, verify authentication/SQLite, then explicitly load and
      // warm both genuine production checkpoints through the authenticated API.
      GARMENT_COUNTER_ENVIRONMENT: "test",
      PYTHONUNBUFFERED: "1",
    },
  });

  child.stdout.on("data", (data) => {
    recentOutput = `${recentOutput}\n${data.toString("utf8")}`.slice(-12000);
  });
  child.stderr.on("data", (data) => {
    recentOutput = `${recentOutput}\n${data.toString("utf8")}`.slice(-12000);
  });
  child.on("error", (error) => {
    recentOutput = error.message;
  });

  const health = await waitForHealth(baseUrl);
  const anonymousRequest = await requestWithRetry(
    `${baseUrl}/api/employees`,
    undefined,
    "checking anonymous-request rejection",
  );

  if (anonymousRequest.status !== 401) {
    throw new Error(`The bundled service accepted an unauthenticated request (${anonymousRequest.status}).`);
  }

  const employeeResponse = await requestWithRetry(
    `${baseUrl}/api/employees`,
    { headers: { Authorization: `Bearer ${token}` } },
    "checking the authenticated SQLite employee database",
  );

  if (!employeeResponse.ok || !Array.isArray(await employeeResponse.json())) {
    throw new Error("The bundled service could not initialize its isolated SQLite employee database.");
  }

  await verifyRealModels(baseUrl);

  console.log(`Bundled application service passed startup, localhost authentication, SQLite, and both genuine trained-model checks (${health.version || "healthy"}).`);
} catch (error) {
  console.error(error instanceof Error ? error.message : "The frozen-service smoke test failed.");
  process.exitCode = 1;
} finally {
  if (child && child.exitCode === null) {
    child.kill();
  }

  rmSync(dataDirectory, { recursive: true, force: true });
}
