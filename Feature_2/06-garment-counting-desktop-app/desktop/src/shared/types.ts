export type SessionMode = "PRODUCTION" | "VALIDATION";

export type SewingState = "IDLE_SETUP" | "SEWING";

export type RuntimeViewState = SewingState | "UNCERTAIN" | "INVALID_VIEW";

export type OperatorMode = "NORMAL" | "REWORK" | "DOWNTIME";

export type ReadinessState = "ready" | "attention" | "pending" | "blocked";

export type ReadinessComponentId =
  | "desktop"
  | "backend"
  | "workstation_detector"
  | "garment_classifier"
  | "camera"
  | "workstation_view"
  | "iot_controller";

export interface ReadinessComponent {
  id: ReadinessComponentId;
  label: string;
  description: string;
  status: ReadinessState;
  detail: string;
  actionLabel?: string;
}

export interface SystemReadiness {
  checkedAt: string;
  components: ReadinessComponent[];
  productionReady: boolean;
  completionPercent: number;
  validationReady?: boolean;
  vision_models?: VisionModels | null;
}

export interface ModelResourceAvailability {
  classifierCheckpointExists: boolean;
  workstationCheckpointExists: boolean;
}

export interface ProductionReadinessInput {
  sessionMode: SessionMode;
  backendReady: boolean;
  garmentClassifierReady: boolean;
  workstationDetectorReady: boolean;
  cameraReady: boolean;
  workstationVisible: boolean;
  iotConnected: boolean;
  iotNotificationsActive: boolean;
  simulatedIotApproved?: boolean;
}

export interface CountingPolicyInput {
  sessionMode: SessionMode;
  sessionActive: boolean;
  workstationVisible: boolean;
  iotConnected: boolean;
  iotNotificationsActive: boolean;
  operatorMode: OperatorMode;
  simulatedIotApproved?: boolean;
}

export interface CountingDecision {
  permitted: boolean;
  reason:
    | "COUNTING_PERMITTED"
    | "NO_ACTIVE_SESSION"
    | "INVALID_WORKSTATION_VIEW"
    | "IOT_DISCONNECTED"
    | "IOT_NOTIFICATIONS_INACTIVE"
    | "REWORK_ACTIVE"
    | "DOWNTIME_ACTIVE";
}

export interface DesktopAppInfo {
  appName: string;
  appVersion: string;
  electronVersion: string;
  chromiumVersion: string;
  nodeVersion: string;
  platform: NodeJS.Platform;
  architecture: string;
  packaged: boolean;
  resourceDirectory: string;
  userDataDirectory: string;
}

export interface WindowState {
  maximized: boolean;
}

export type BackendMethod = "GET" | "POST" | "PUT";

export interface BackendRequest {
  method: BackendMethod;
  path: string;
  body?: unknown;
}

export interface BackendStatus {
  state: "starting" | "ready" | "stopped" | "error";
  message: string;
}

export interface Employee {
  id: number;
  employee_code: string;
  full_name: string;
  sewing_line: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmployeeInput {
  employee_code: string;
  full_name: string;
  sewing_line: string;
  active?: boolean;
}

export interface SessionDataDeletionResult {
  deleted_sessions: number;
  deleted_piece_events: number;
  deleted_iot_events: number;
  message: string;
}

export type IotConfigurationMode = "NOT_CONFIGURED" | "REAL" | "SIMULATED";

export interface DeviceConfiguration {
  id: number;
  camera_id: string | null;
  camera_label: string | null;
  camera_tested: boolean;
  camera_tested_at: string | null;
  iot_mode: IotConfigurationMode;
  iot_device_name: string | null;
  iot_device_id: string | null;
  iot_connected: boolean;
  iot_notifications_active: boolean;
  simulation_approved: boolean;
  updated_at: string;
}

export interface DeviceConfigurationInput {
  camera_id: string | null;
  camera_label: string | null;
  camera_tested: boolean;
  iot_mode: IotConfigurationMode;
  iot_device_name: string | null;
  iot_device_id?: string | null;
  simulation_approved: boolean;
}

export type HardwareButtonEventType = "REWORK" | "DOWNTIME" | "RESET";

export type BluetoothControllerPhase =
  | "DISCONNECTED"
  | "SCANNING"
  | "CONNECTING"
  | "CONNECTED"
  | "RECONNECTING"
  | "ERROR";

export interface BluetoothControllerState {
  phase: BluetoothControllerPhase;
  deviceId: string | null;
  deviceName: string | null;
  notificationsActive: boolean;
  reconnectAttempt: number;
  lastButton: HardwareButtonEventType | null;
  lastButtonAt: string | null;
  message: string;
}

export interface DiscoveredBluetoothDevice {
  deviceId: string;
  deviceName: string;
  compatible: boolean;
}

export interface HardwareConnectionInput {
  device_id: string;
  device_name: string;
  connected: boolean;
  notifications_active: boolean;
  reason?: string;
}

export interface HardwareConnectionResult {
  configuration: DeviceConfiguration;
  event: IotEvent | null;
}

export interface HardwareEventInput {
  device_id: string;
  device_name: string;
  event_type: HardwareButtonEventType;
  payload?: Record<string, unknown>;
}

export interface VisionCamera {
  camera_id: string;
  label: string;
  width: number;
  height: number;
}

export interface WorkstationDetection {
  visible: boolean;
  confidence: number;
  bbox: [number, number, number, number] | null;
  label: string | null;
  message: string;
}

export interface CameraTestResult {
  camera_id: string;
  camera_ready: boolean;
  width: number;
  height: number;
  workstation_checked: boolean;
  workstation_visible: boolean;
  detection: WorkstationDetection | null;
  tested_at: string;
}

export interface ModelStatus {
  state: "NOT_LOADED" | "LOADING" | "READY" | "FAILED";
  message: string;
  device: string | null;
}

export interface VisionModels {
  detector: ModelStatus;
  classifier: ModelStatus;
  ready: boolean;
}

export type InferencePhase = "STOPPED" | "STARTING" | "MONITORING" | "PAUSED" | "VIDEO_COMPLETE" | "ERROR";

export interface InferenceStatus {
  running: boolean;
  phase: InferencePhase;
  session_id: number | null;
  source_type: "camera" | "video" | null;
  source_label: string | null;
  test_workflow: boolean;
  sewing_state: RuntimeViewState;
  classification_confidence: number;
  workstation_visible: boolean;
  workstation_confirmed: boolean;
  workstation_confidence: number;
  workstation_bbox: [number, number, number, number] | null;
  workstation_message: string;
  counting_permitted: boolean;
  counting_message: string;
  processing_fps: number;
  buffered_frames: number;
  frames_processed: number;
  preview_ready: boolean;
  last_event: PieceEvent | null;
  last_error: string | null;
  updated_at: string;
  models: VisionModels;
}

export interface ProductionSession {
  id: number;
  session_code: string;
  employee_id: number;
  employee_code: string;
  employee_name: string;
  sewing_line: string;
  workstation_id: string;
  camera_id: string;
  camera_label: string;
  target_pieces: number;
  session_mode: SessionMode;
  status: "ACTIVE" | "COMPLETED";
  operator_mode: OperatorMode;
  simulated_iot: boolean;
  total_pieces: number;
  average_cycle_seconds: number | null;
  first_sewing_started_at: string | null;
  started_at: string;
  ended_at: string | null;
  remaining_pieces: number;
  achievement_percent: number;
  created_at: string;
}

export interface SessionCreateInput {
  employee_id: number;
  target_pieces: number;
  workstation_id: string;
  session_mode: SessionMode;
}

export interface PieceEvent {
  id: number;
  session_id: number;
  piece_number: number;
  cycle_seconds: number;
  sewing_started_at: string | null;
  completed_at: string;
  state_from: "SEWING";
  state_to: "IDLE_SETUP";
  confidence: number | null;
  event_source: "VISION" | "VALIDATION";
  created_at: string;
}

export type IotEventType = "REWORK" | "DOWNTIME" | "RESET" | "DISCONNECTED" | "RECONNECTED";

export interface IotEvent {
  id: number;
  session_id: number | null;
  employee_id: number | null;
  event_type: IotEventType;
  mode_before: OperatorMode;
  mode_after: OperatorMode;
  device_name: string | null;
  event_source: "HARDWARE" | "VALIDATION";
  payload_json: string | null;
  occurred_at: string;
  created_at: string;
}

export interface IotMetrics {
  rework_count: number;
  downtime_count: number;
  disconnect_count: number;
  rework_seconds: number;
  downtime_seconds: number;
  disconnected_seconds: number;
}

export interface TargetPoint {
  piece_number: number;
  remaining_pieces: number;
}

export interface DashboardPayload {
  session: ProductionSession;
  piece_events: PieceEvent[];
  iot_events: IotEvent[];
  iot_metrics: IotMetrics;
  target_series: TargetPoint[];
  device_configuration: DeviceConfiguration;
  inference: InferenceStatus;
}

export interface AnalyticsSummary extends IotMetrics {
  session_count: number;
  completed_session_count: number;
  employee_count: number;
  total_pieces: number;
  target_pieces: number;
  achievement_percent: number;
  average_cycle_seconds: number | null;
}

export interface AnalyticsSession extends ProductionSession, IotMetrics {}

export interface EmployeePerformance {
  employee_id: number;
  employee_code: string;
  employee_name: string;
  sewing_line: string;
  session_count: number;
  total_pieces: number;
  target_pieces: number;
  achievement_percent: number;
  rework_count: number;
  downtime_count: number;
  rework_seconds: number;
  downtime_seconds: number;
}

export interface AnalyticsFilters {
  employee_id?: string;
  session_id?: string;
  sewing_line?: string;
  start_date?: string;
  end_date?: string;
  session_mode?: SessionMode | "";
}

export interface AnalyticsPayload {
  generated_at: string;
  filters: AnalyticsFilters;
  summary: AnalyticsSummary;
  sessions: AnalyticsSession[];
  piece_events: PieceEvent[];
  iot_events: IotEvent[];
  employees: EmployeePerformance[];
}

export interface ExportResult {
  canceled: boolean;
  filePath?: string;
}

export interface ValidationVideoResult {
  canceled: boolean;
  filePath?: string;
  fileName?: string;
}

export interface DesktopApi {
  getAppInfo: () => Promise<DesktopAppInfo>;
  checkReadiness: () => Promise<SystemReadiness>;
  getBackendStatus: () => Promise<BackendStatus>;
  backendRequest: <T>(request: BackendRequest) => Promise<T>;
  exportAnalytics: (query: string) => Promise<ExportResult>;
  selectValidationVideo: () => Promise<ValidationVideoResult>;
  getLiveStreamUrl: (sessionId: number) => Promise<string>;
  onBluetoothDevices: (listener: (devices: DiscoveredBluetoothDevice[]) => void) => () => void;
  selectBluetoothDevice: (deviceId: string) => Promise<void>;
  cancelBluetoothSelection: () => Promise<void>;
  syncIotConnection: (input: HardwareConnectionInput) => Promise<HardwareConnectionResult>;
  submitHardwareEvent: (input: HardwareEventInput) => Promise<IotEvent>;
  minimizeWindow: () => Promise<void>;
  toggleMaximizeWindow: () => Promise<WindowState>;
  closeWindow: () => Promise<void>;
}
