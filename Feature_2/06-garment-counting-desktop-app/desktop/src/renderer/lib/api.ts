import type {
  AnalyticsFilters,
  AnalyticsPayload,
  BackendRequest,
  CameraTestResult,
  DashboardPayload,
  DeviceConfiguration,
  DeviceConfigurationInput,
  Employee,
  EmployeeInput,
  IotEvent,
  IotEventType,
  InferenceStatus,
  PieceEvent,
  ProductionSession,
  SessionCreateInput,
  SessionDataDeletionResult,
  SystemReadiness,
  VisionCamera,
  VisionModels,
} from "../../shared/types";

function request<T>(method: BackendRequest["method"], path: string, body?: unknown): Promise<T> {
  return window.garmentDesktop.backendRequest<T>({ method, path, body });
}

export function analyticsQuery(filters: AnalyticsFilters): string {
  const parameters = new URLSearchParams();

  for (const [key, value] of Object.entries(filters)) {
    if (value) parameters.set(key, value);
  }

  const query = parameters.toString();
  return query ? `?${query}` : "";
}

export const api = {
  readiness: () => request<SystemReadiness>("GET", "/api/readiness"),
  employees: (includeInactive = false) =>
    request<Employee[]>("GET", `/api/employees${includeInactive ? "?include_inactive=true" : ""}`),
  createEmployee: (input: EmployeeInput) => request<Employee>("POST", "/api/employees", input),
  updateEmployee: (id: number, input: EmployeeInput) =>
    request<Employee>("PUT", `/api/employees/${id}`, input),
  deviceConfiguration: () => request<DeviceConfiguration>("GET", "/api/device-configuration"),
  saveDeviceConfiguration: (input: DeviceConfigurationInput) =>
    request<DeviceConfiguration>("PUT", "/api/device-configuration", input),
  visionModels: () => request<VisionModels>("GET", "/api/vision/models"),
  reloadVisionModels: () => request<VisionModels>("POST", "/api/vision/models/load"),
  scanVisionCameras: (expectedCount?: number) =>
    request<VisionCamera[]>(
      "GET",
      `/api/vision/cameras${expectedCount ? `?expected_count=${Math.min(5, expectedCount)}` : ""}`,
    ),
  testVisionCamera: (cameraId: string) =>
    request<CameraTestResult>("POST", "/api/vision/cameras/test", { camera_id: cameraId }),
  startVision: (sessionId: number, sourceType: "camera" | "video", videoPath?: string) =>
    request<InferenceStatus>("POST", "/api/vision/start", {
      session_id: sessionId,
      source_type: sourceType,
      ...(videoPath ? { video_path: videoPath } : {}),
    }),
  stopVision: (sessionId: number) =>
    request<InferenceStatus>("POST", `/api/vision/stop/${sessionId}`),
  inferenceStatus: (sessionId: number) =>
    request<InferenceStatus>("GET", `/api/vision/status/${sessionId}`),
  activeSession: () => request<ProductionSession | null>("GET", "/api/sessions/active"),
  sessions: () => request<ProductionSession[]>("GET", "/api/sessions"),
  deleteSessionHistory: (confirmation: string) =>
    request<SessionDataDeletionResult>("POST", "/api/sessions/delete-history", { confirmation }),
  createSession: (input: SessionCreateInput) => request<ProductionSession>("POST", "/api/sessions", input),
  completeSession: (id: number) => request<ProductionSession>("POST", `/api/sessions/${id}/complete`),
  dashboard: (id: number) => request<DashboardPayload>("GET", `/api/sessions/${id}/dashboard`),
  addValidationPiece: (sessionId: number) =>
    request<PieceEvent>("POST", `/api/sessions/${sessionId}/pieces`, { event_source: "VALIDATION" }),
  createValidationIotEvent: (sessionId: number, eventType: IotEventType) =>
    request<IotEvent>("POST", "/api/iot-events", {
      session_id: sessionId,
      event_type: eventType,
      event_source: "VALIDATION",
    }),
  testValidationController: () =>
    request<IotEvent>("POST", "/api/iot-events", {
      event_type: "RESET",
      event_source: "VALIDATION",
    }),
  analytics: (filters: AnalyticsFilters) =>
    request<AnalyticsPayload>("GET", `/api/analytics${analyticsQuery(filters)}`),
};
