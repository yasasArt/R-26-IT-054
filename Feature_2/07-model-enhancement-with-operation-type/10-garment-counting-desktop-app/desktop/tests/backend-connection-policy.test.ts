import assert from "node:assert/strict";
import test from "node:test";

import {
  backendConnectionErrorCode,
  shouldRetryBackendConnection,
} from "../src/shared/backend-connection-policy.ts";

test("nested Electron fetch errors expose their underlying localhost connection code", () => {
  const error = new TypeError("fetch failed", {
    cause: Object.assign(new Error("read ECONNRESET"), { code: "ECONNRESET" }),
  });

  assert.equal(backendConnectionErrorCode(error), "ECONNRESET");
  assert.equal(shouldRetryBackendConnection("GET", 0, error), true);
  assert.equal(shouldRetryBackendConnection("GET", 1, error), true);
  assert.equal(shouldRetryBackendConnection("GET", 2, error), false);
});

test("production mutations are never retried because duplicate writes are unsafe", () => {
  const error = Object.assign(new Error("socket disconnected"), { code: "ECONNRESET" });

  assert.equal(shouldRetryBackendConnection("POST", 0, error), false);
  assert.equal(shouldRetryBackendConnection("PUT", 0, error), false);
  assert.equal(shouldRetryBackendConnection("GET", 0, new Error("bad response")), false);
});
