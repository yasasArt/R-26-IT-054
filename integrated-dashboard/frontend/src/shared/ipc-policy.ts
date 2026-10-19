import type { BackendRequest } from "./types";

export function allowsRendererBackendRequest(request: BackendRequest): boolean {
  const path = request.path.split("?", 1)[0];

  if (path === "/api/iot/connection") return false;

  if (request.method !== "POST") return true;

  const body = request.body;

  if (path === "/api/iot-events") {
    return Boolean(
      body &&
        typeof body === "object" &&
        "event_source" in body &&
        body.event_source === "VALIDATION",
    );
  }

  if (body && typeof body === "object" && "event_source" in body) {
    return body.event_source === "VALIDATION";
  }

  return true;
}

