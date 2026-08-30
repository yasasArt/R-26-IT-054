import assert from "node:assert/strict";
import { test } from "node:test";

import { assertAllowedRequest } from "../src/main/backend-policy.js";

test("renderer can access only allow-listed method and path pairs", () => {
  const rule = assertAllowedRequest(
    { method: "GET", path: "/api/analytics/export", query: { employee_id: 7 } },
    "renderer",
  );
  assert.equal(rule.response, "binary");

  assert.throws(
    () => assertAllowedRequest({ method: "GET", path: "http://example.com/api/health" }, "renderer"),
    /normalized local API paths/,
  );
  assert.throws(
    () => assertAllowedRequest({ method: "POST", path: "/api/models/status", body: {} }, "renderer"),
    /not allow-listed/,
  );
  assert.throws(
    () => assertAllowedRequest({ method: "GET", path: "/docs" }, "renderer"),
    /normalized local API paths/,
  );
});

test("capabilities separate renderer, vision and controller routes", () => {
  assert.throws(
    () => assertAllowedRequest({ method: "GET", path: "/api/vision/preview/frame" }, "renderer"),
    /not allow-listed/,
  );
  assert.throws(
    () => assertAllowedRequest(
      { method: "POST", path: "/api/trusted/controller-events", body: {} },
      "renderer",
    ),
    /not allow-listed/,
  );
  assert.equal(
    assertAllowedRequest(
      { method: "GET", path: "/api/vision/preview/frame" },
      "vision",
    ).response,
    "binary",
  );
  assert.equal(
    assertAllowedRequest(
      {
        method: "POST",
        path: "/api/trusted/controller-events",
        body: { session_id: 1 },
      },
      "controller",
    ).response,
    "json",
  );
});

test("query keys and request bodies are strict", () => {
  assert.throws(
    () => assertAllowedRequest(
      { method: "GET", path: "/api/analytics", query: { arbitrary: "value" } },
      "renderer",
    ),
    /Query parameter is not allowed/,
  );
  assert.throws(
    () => assertAllowedRequest(
      { method: "GET", path: "/api/models/status", body: { unexpected: true } },
      "renderer",
    ),
    /does not accept a body/,
  );
  assert.throws(
    () => assertAllowedRequest(
      { method: "POST", path: "/api/employees" },
      "renderer",
    ),
    /requires a JSON object body/,
  );
});

