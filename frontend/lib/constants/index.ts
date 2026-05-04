import type { IWorkstationConfig, IProductionSpec } from "@/lib/types";

// ─────────────────────────────────────────
// APP META
// ─────────────────────────────────────────

export const APP_NAME = "AI Vision System";
export const APP_SUBTITLE = "Apparel Manufacturing Workstation";
export const APP_VERSION = "1.0.0-prototype";

// ─────────────────────────────────────────
// STATION CONFIG
// ─────────────────────────────────────────

export const AVAILABLE_STATIONS: Array<{ id: string; label: string }> = [
  { id: "WS-01", label: "WS-01 | Floor 2 – Line 5" },
  { id: "WS-02", label: "WS-02 | Floor 2 – Line 6" },
  { id: "WS-03", label: "WS-03 | Floor 3 – Quality Bay" },
  { id: "WS-04", label: "WS-04 | Floor 3 – Quality Bay 2" },
];

export const DEMO_PIN = "1234";
export const DEMO_SERVER_URL = "192.168.1.100:8080";

export const DEFAULT_WORKSTATION_CONFIG: IWorkstationConfig = {
  stationId: "WS-01",
  stationLabel: "WS-01 | Floor 2 – Line 5",
  operatorName: "",
  mode: null,
  shiftStart: null,
  shiftTarget: 150,
  serverUrl: DEMO_SERVER_URL,
  cameraId: "cam-0",
  cameraLabel: "Logitech C922",
};

// ─────────────────────────────────────────
// SEWING MODE THRESHOLDS
// ─────────────────────────────────────────

export const CYCLE_TIME = {
  TARGET_SECONDS: 45,
  WARNING_SECONDS: 65,
  DANGER_SECONDS: 90,
  MIN_SECONDS: 20,
  MAX_SECONDS: 180,
} as const;

export const SHIFT = {
  DEFAULT_TARGET_PIECES: 150,
  DEFAULT_DURATION_HOURS: 8,
  PIECES_PER_HOUR_TARGET: 18,
} as const;

export const DETECTION = {
  SIGNAL_A_DWELL_MS: 1500,   // garment must be stationary for this long
  SIGNAL_WINDOW_MS: 3000,    // both signals must agree within this window
  LOG_MAX_ENTRIES: 100,      // cap detection log at N entries
  CONFIDENCE_THRESHOLD: 0.72,
} as const;

// ─────────────────────────────────────────
// QUALITY MODE THRESHOLDS
// ─────────────────────────────────────────

export const SIZE_THRESHOLDS = {
  // Width in cm (approximate — actual values tuned per product spec)
  S:  { widthMin: 40, widthMax: 46, heightMin: 62, heightMax: 67 },
  M:  { widthMin: 46, widthMax: 52, heightMin: 65, heightMax: 70 },
  L:  { widthMin: 52, widthMax: 58, heightMin: 68, heightMax: 74 },
  XL: { widthMin: 58, widthMax: 66, heightMin: 71, heightMax: 78 },
} as const;

export const QUALITY = {
  INSPECTION_LOG_MAX: 200,
  CONFIDENCE_PASS_THRESHOLD: 0.80,
  COLOUR_MATCH_TOLERANCE: 20, // HSV hue degrees
  SIZE_TOLERANCE_CM: 1.5,
} as const;

// ─────────────────────────────────────────
// DEMO / SIMULATION
// ─────────────────────────────────────────

export const SIMULATION = {
  DEFAULT_SPEED_MS: 4000,     // base interval between events at 1×
  SPEEDS: {
    "0.5x": 8000,
    "1x": 4000,
    "2x": 2000,
    "5x": 800,
    manual: 0,
  },
} as const;

// ─────────────────────────────────────────
// SAMPLE PRODUCTION SPECIFICATIONS
// ─────────────────────────────────────────

export const PRODUCTION_SPECS: IProductionSpec[] = [
  {
    specId: "POLO-A3",
    specLabel: "POLO-A3",
    expectedStyle: "Polo",
    expectedSize: "M",
    expectedColours: ["Navy Blue"],
    widthToleranceCm: 1.5,
    heightToleranceCm: 2.0,
  },
  {
    specId: "TEE-B1",
    specLabel: "TEE-B1",
    expectedStyle: "T-Shirt",
    expectedSize: "L",
    expectedColours: ["White"],
    widthToleranceCm: 1.5,
    heightToleranceCm: 2.0,
  },
  {
    specId: "PANTS-C2",
    specLabel: "PANTS-C2",
    expectedStyle: "Pants",
    expectedSize: "M",
    expectedColours: ["Black"],
    widthToleranceCm: 2.0,
    heightToleranceCm: 2.5,
  },
  {
    specId: "SKINNY-D4",
    specLabel: "SKINNY-D4",
    expectedStyle: "Skinny",
    expectedSize: "S",
    expectedColours: ["Black"],
    widthToleranceCm: 1.0,
    heightToleranceCm: 2.0,
  },
];

// ─────────────────────────────────────────
// COLOUR LIBRARY (for mock data generation)
// ─────────────────────────────────────────

export const COLOUR_LIBRARY: Array<{ name: string; hex: string }> = [
  { name: "Navy Blue",   hex: "#1E3A5F" },
  { name: "White",       hex: "#F8F8F8" },
  { name: "Black",       hex: "#1A1A1A" },
  { name: "Sky Blue",    hex: "#4FA3D1" },
  { name: "Red",         hex: "#C0392B" },
  { name: "Olive Green", hex: "#5D6D3A" },
  { name: "Light Grey",  hex: "#BDC3C7" },
  { name: "Cream",       hex: "#F5F0E8" },
  { name: "Charcoal",    hex: "#2C3E50" },
  { name: "Burgundy",    hex: "#800020" },
];

// ─────────────────────────────────────────
// ROUTES
// ─────────────────────────────────────────

export const ROUTES = {
  LOGIN: "/login",
  SETUP: "/setup",
  DASHBOARD_SEWING: "/dashboard/sewing",
  DASHBOARD_QUALITY: "/dashboard/quality",
  LOGS: "/logs",
  DEVICES: "/devices",
} as const;