import type { ApiRequest, HttpMethod, JsonPrimitive } from "../shared/api-types.js";

export type BackendCapability = "renderer" | "vision" | "controller";
export type BodyKind = "none" | "json";
export type ResponseKind = "json" | "binary";

export interface EndpointRule {
  method: HttpMethod;
  path: RegExp;
  body: BodyKind;
  response: ResponseKind;
  queryKeys?: readonly string[];
}

const ID = "[1-9][0-9]*";
const VIDEO = "[a-f0-9-]+\\.(?:mp4|mov|avi|mkv|m4v)";
const JSON_LIMIT_BYTES = 1024 * 1024;

const rendererRules: readonly EndpointRule[] = [
  { method: "GET", path: /^\/api\/health$/, body: "none", response: "json" },
  { method: "GET", path: /^\/api\/health\/database$/, body: "none", response: "json" },
  { method: "GET", path: /^\/api\/employees$/, body: "none", response: "json", queryKeys: ["include_inactive"] },
  { method: "POST", path: /^\/api\/employees$/, body: "json", response: "json" },
  { method: "GET", path: new RegExp(`^/api/employees/${ID}$`), body: "none", response: "json" },
  { method: "PATCH", path: new RegExp(`^/api/employees/${ID}$`), body: "json", response: "json" },
  { method: "GET", path: /^\/api\/configuration$/, body: "none", response: "json" },
  { method: "PUT", path: /^\/api\/configuration$/, body: "json", response: "json" },
  { method: "GET", path: /^\/api\/sessions\/readiness$/, body: "none", response: "json", queryKeys: ["session_mode"] },
  { method: "GET", path: /^\/api\/sessions\/active$/, body: "none", response: "json" },
  { method: "GET", path: /^\/api\/sessions$/, body: "none", response: "json" },
  { method: "POST", path: /^\/api\/sessions$/, body: "json", response: "json" },
  { method: "GET", path: new RegExp(`^/api/sessions/${ID}$`), body: "none", response: "json" },
  { method: "DELETE", path: new RegExp(`^/api/sessions/${ID}$`), body: "none", response: "json" },
  { method: "POST", path: new RegExp(`^/api/sessions/${ID}/complete$`), body: "none", response: "json" },
  { method: "GET", path: new RegExp(`^/api/sessions/${ID}/piece-events$`), body: "none", response: "json" },
  { method: "GET", path: new RegExp(`^/api/sessions/${ID}/production-summary$`), body: "none", response: "json" },
  { method: "GET", path: new RegExp(`^/api/sessions/${ID}/iot-events$`), body: "none", response: "json" },
  { method: "GET", path: new RegExp(`^/api/sessions/${ID}/iot-summary$`), body: "none", response: "json", queryKeys: ["as_of"] },
  { method: "GET", path: /^\/api\/analytics$/, body: "none", response: "json", queryKeys: ["session_id", "employee_id", "date_from", "date_to", "session_status", "session_mode"] },
  { method: "GET", path: /^\/api\/analytics\/export$/, body: "none", response: "binary", queryKeys: ["session_id", "employee_id", "date_from", "date_to", "session_status", "session_mode"] },
  { method: "GET", path: /^\/api\/models\/status$/, body: "none", response: "json" },
];

const visionRules: readonly EndpointRule[] = [
  { method: "GET", path: /^\/api\/vision\/status$/, body: "none", response: "json" },
  { method: "POST", path: /^\/api\/vision\/stop$/, body: "none", response: "json" },
  { method: "POST", path: new RegExp(`^/api/vision/sessions/${ID}/start$`), body: "json", response: "json" },
  { method: "GET", path: /^\/api\/vision\/preview\/frame$/, body: "none", response: "binary" },
  { method: "DELETE", path: new RegExp(`^/api/vision/videos/${VIDEO}$`), body: "none", response: "json" },
];

const controllerRules: readonly EndpointRule[] = [
  { method: "POST", path: /^\/api\/trusted\/controller-events$/, body: "json", response: "json" },
];

const rulesByCapability: Record<BackendCapability, readonly EndpointRule[]> = {
  renderer: rendererRules,
  vision: visionRules,
  controller: controllerRules,
};

function validateQuery(
  query: Record<string, JsonPrimitive> | undefined,
  allowed: readonly string[] | undefined,
): void {
  if (query === undefined) return;
  const allowedKeys = new Set(allowed ?? []);
  for (const [key, value] of Object.entries(query)) {
    if (!allowedKeys.has(key)) throw new Error(`Query parameter is not allowed: ${key}`);
    if (value !== null && !["string", "number", "boolean"].includes(typeof value)) {
      throw new Error(`Query parameter has an invalid value: ${key}`);
    }
  }
}

function validateBody(input: ApiRequest, kind: BodyKind): void {
  if (kind === "none") {
    if (input.body !== undefined) throw new Error("This endpoint does not accept a body");
    return;
  }
  if (input.body === undefined || input.body === null || Array.isArray(input.body)) {
    throw new Error("This endpoint requires a JSON object body");
  }
  const encoded = JSON.stringify(input.body);
  if (Buffer.byteLength(encoded, "utf8") > JSON_LIMIT_BYTES) {
    throw new Error("JSON request exceeds the IPC size limit");
  }
}

export function assertAllowedRequest(
  input: ApiRequest,
  capability: BackendCapability,
): EndpointRule {
  if (!input || typeof input !== "object") throw new Error("Invalid API request");
  if (typeof input.path !== "string" || input.path.length > 300) {
    throw new Error("Invalid API path");
  }
  if (!input.path.startsWith("/api/") || /[?#\\\\\u0000-\u001f]/.test(input.path)) {
    throw new Error("Only normalized local API paths are allowed");
  }
  const rule = rulesByCapability[capability].find(
    (candidate) => candidate.method === input.method && candidate.path.test(input.path),
  );
  if (!rule) throw new Error("API method and path are not allow-listed");
  validateQuery(input.query, rule.queryKeys);
  validateBody(input, rule.body);
  return rule;
}

export function appendQuery(
  path: string,
  query: Record<string, JsonPrimitive> | undefined,
): string {
  if (!query) return path;
  const parameters = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== null) parameters.set(key, String(value));
  }
  const encoded = parameters.toString();
  return encoded ? `${path}?${encoded}` : path;
}

