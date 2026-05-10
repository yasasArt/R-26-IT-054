export type AreaMode = "sewing" | "quality";

export type OperatorStatus = "active" | "idle" | "downtime" | "rework";

export type CameraStatus = "live" | "disconnected" | "error" | "calibrating";

export type IoTStatus = "connected" | "disconnected" | "error";

export type CalibrationStatus = "calibrated" | "uncalibrated" | "error";

export type QualityDecision = "PASS" | "REWORK" | "MISMATCH";

export type GarmentSize = "S" | "M" | "L" | "XL" | "Unknown";

export type GarmentStyle = "T-Shirt" | "Pants" | "Skinny" | "Unknown";

export type SignalStatus = "triggered" | "waiting" | "idle";

export type EventType =
  | "piece_detected"
  | "rework_start"
  | "rework_end"
  | "downtime_start"
  | "downtime_end"
  | "iot_event"
  | "camera_event"
  | "session_start"
  | "session_end";

export type Severity = "info" | "warning" | "error" | "success";

// ─────────────────────────────────────────
// WORKSTATION / SESSION
// ─────────────────────────────────────────

export interface IWorkstationConfig {
  stationId: string;
  stationLabel: string;
  operatorName: string;
  mode: AreaMode | null;
  shiftStart: Date | null;
  shiftTarget: number; // pieces target for sewing mode
  serverUrl: string;
  cameraId: string;
  cameraLabel: string;
}

export interface ISession {
  sessionId: string;
  stationId: string;
  operatorName: string;
  mode: AreaMode;
  startTime: Date;
  endTime?: Date;
  isActive: boolean;
}

// ─────────────────────────────────────────
// FEATURE 2 — SEWING / PIECE COUNTING
// ─────────────────────────────────────────

/**
 * Dual-signal detection event.
 * Signal A: YOLOv8 garment stationary in output zone ≥1.5s
 * Signal B: YOLOv8-Pose wrist entered then withdrew from zone
 * Count only fires when both agree within the time window.
 */
export interface IDualSignalState {
  signalA: SignalStatus; // Garment stationary in zone
  signalATimestamp: Date | null;
  signalB: SignalStatus; // Wrist place-and-withdraw action
  signalBTimestamp: Date | null;
  bothAgreed: boolean;
}

export interface IDetectionEvent {
  id: string;
  timestamp: Date;
  pieceNumber: number;
  cycleTimeSeconds: number;
  operatorStatus: OperatorStatus;
  confidenceScore: number; // 0–1
  signalA: boolean;
  signalB: boolean;
}

export interface ICycleRecord {
  id: string;
  timestamp: Date;
  pieceNumber: number;
  durationSeconds: number;
  isWithinTarget: boolean;
}

export interface IIoTEvent {
  id: string;
  timestamp: Date;
  type: "rework_triggered" | "rework_resolved" | "downtime_triggered" | "downtime_resolved";
  triggeredBy: "operator" | "system";
  durationSeconds?: number;
}

export interface IShiftSummary {
  shiftStart: Date;
  elapsedSeconds: number;
  totalPieces: number;
  targetPieces: number;
  completionPercent: number;
  averageCycleTime: number;
  totalDowntimeSeconds: number;
  totalReworkCount: number;
  projectedEndTime: Date | null;
}

// ─────────────────────────────────────────
// FEATURE 3 — COLOUR & STYLE RECOGNITION
// ─────────────────────────────────────────

export interface IColourDetection {
  id: string;
  name: string; // e.g. "Navy Blue"
  hex: string; // e.g. "#1E3A5F"
  percentage: number; // 0–100, proportion of garment
  hsvRange?: {
    hMin: number;
    hMax: number;
    sMin: number;
    sMax: number;
  };
}

export interface IStyleDetection {
  style: GarmentStyle;
  confidenceScore: number; // 0–1
  alternativeStyle?: GarmentStyle;
  alternativeScore?: number;
}

// ─────────────────────────────────────────
// FEATURE 4 — SIZE MEASUREMENT
// ─────────────────────────────────────────

export interface ISizeMeasurement {
  widthCm: number;
  heightCm: number;
  detectedSize: GarmentSize;
  pixelPerCmRatio: number;
  confidenceScore: number; // 0–1
  boundingBoxPx?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface ICalibrationData {
  status: CalibrationStatus;
  referenceObjectSizeCm: number;
  pixelPerCmRatio: number;
  lastCalibratedAt: Date | null;
  cameraId: string;
}

// ─────────────────────────────────────────
// QUALITY INSPECTION (Feature 3 + 4 combined)
// ─────────────────────────────────────────

export interface IProductionSpec {
  specId: string;
  specLabel: string; // e.g. "TEE-B1"
  expectedStyle: GarmentStyle;
  expectedSize: GarmentSize;
  expectedColours: string[]; // colour names
  widthToleranceCm: number; // ± tolerance
  heightToleranceCm: number;
}

export interface ISpecMatchResult {
  attribute: "size" | "style" | "colour" | "width" | "height";
  label: string;
  expected: string;
  detected: string;
  isMatch: boolean;
}

export interface IGarmentAnalysis {
  id: string;
  timestamp: Date;
  // Size (Feature 4)
  sizeMeasurement: ISizeMeasurement;
  // Colour & Style (Feature 3)
  styleDetection: IStyleDetection;
  colourDetections: IColourDetection[];
  // Combined decision
  decision: QualityDecision;
  specMatchResults: ISpecMatchResult[];
  overallConfidence: number;
  // Camera frame reference
  frameCapturedAt: Date;
  previewImageUrl?: string; // mock image path for demo
}

export interface IInspectionRecord {
  id: string;
  timestamp: Date;
  garmentAnalysis: IGarmentAnalysis;
  decision: QualityDecision;
  specLabel: string;
  operatorOverride?: boolean;
}

// ─────────────────────────────────────────
// DEVICE STATUS
// ─────────────────────────────────────────

export interface ICameraDevice {
  deviceId: string;
  label: string;
  status: CameraStatus;
  resolution: string; // e.g. "1920x1080"
  fps: number;
  lastSeenAt: Date | null;
  isCalibrated: boolean;
}

export interface IIoTDevice {
  deviceId: string;
  label: string;
  status: IoTStatus;
  firmwareVersion: string;
  lastPingAt: Date | null;
  reworkSwitchState: boolean;
  downtimeSwitchState: boolean;
  ipAddress: string;
}

// ─────────────────────────────────────────
// GENERAL EVENT LOG
// ─────────────────────────────────────────

export interface ILogEntry {
  id: string;
  timestamp: Date;
  eventType: EventType;
  severity: Severity;
  title: string;
  description: string;
  mode: AreaMode;
  metadata?: Record<string, unknown>;
}

// ─────────────────────────────────────────
// UI STATE HELPERS
// ─────────────────────────────────────────

export interface IStatTileData {
  label: string;
  value: string | number;
  unit?: string;
  trend?: "up" | "down" | "neutral";
  status?: "normal" | "warning" | "danger" | "success";
}

export interface IDemoScriptStep {
  id: string;
  delay: number; // ms until next step
  action: string; // action identifier
  payload?: Record<string, unknown>;
  label: string; // human-readable description
}
