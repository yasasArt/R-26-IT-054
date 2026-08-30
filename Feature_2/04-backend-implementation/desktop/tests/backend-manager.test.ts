import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test } from "node:test";

import { allocateLoopbackPort, BackendManager } from "../src/main/backend-manager.js";

test("loopback port allocation returns a valid ephemeral port", async () => {
  const port = await allocateLoopbackPort();
  assert.ok(port > 0 && port <= 65_535);
});

test("manager starts, authenticates and stops a child backend", async () => {
  const root = await mkdtemp(join(tmpdir(), "garment-phase11-"));
  const manager = new BackendManager({
    appDataPath: join(root, "data"),
    databasePath: join(root, "data", "test.db"),
    modelsPath: join(root, "models"),
    developmentCommand: {
      command: process.execPath,
      args: [resolve("tests/fake-backend.mjs")],
      cwd: process.cwd(),
    },
    environment: "production",
    startupTimeoutMs: 5_000,
    shutdownTimeoutMs: 2_000,
  });

  await manager.start();
  assert.equal(manager.running, true);
  const result = await manager.requestFromRenderer({
    method: "GET",
    path: "/api/models/status",
  });
  assert.equal(result.kind, "json");
  if (result.kind === "json") {
    assert.deepEqual(result.data, { authenticated: true, tokenLength: 43 });
  }

  await manager.stop();
  assert.equal(manager.running, false);
  await assert.rejects(
    manager.requestFromRenderer({ method: "GET", path: "/api/models/status" }),
    /not running/,
  );
});

