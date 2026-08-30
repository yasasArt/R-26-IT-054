import axios from "axios";

const API_BASE = "http://127.0.0.1:8000";
const API_URL = `${API_BASE}/api/garments`;

// The Flask/OpenCV capture service (separate Python process, separate venv -
// see resources/live_webcam_pipeline.py). Handles the live video
// feed and anything that needs the CV stack (video best-frame analysis).
export const CV_API_BASE = "http://127.0.0.1:5050";

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export interface GarmentScan {
  _id: string;
  style_name: string;
  main_color: string;
  other_colors?: string;
  confidence: number;
  image_base64?: string;
  timestamp?: string;
}

// Full persisted history, most recent first - used to populate History Log
// on load so it survives an app restart/refresh, not just what streamed in
// during the current session.
export const fetchAllGarments = async (): Promise<GarmentScan[]> => {
  try {
    const response = await axios.get(`${API_URL}/`);
    return response.data;
  } catch (error) {
    console.error("Garment History Fetch Error:", describeError(error));
    return [];
  }
};

export interface DeleteHistoryResult {
  status: string;
  deleted_count: number;
}

// Permanently deletes every saved garment record - used by the History
// Management card on the Target & Schedule page. Irreversible.
export const deleteAllGarments = async (): Promise<DeleteHistoryResult> => {
  const response = await axios.delete(`${API_URL}/`);
  return response.data;
};

export const fetchLatestGarment = async (): Promise<GarmentScan | null> => {
  try {
    const response = await axios.get(`${API_URL}/latest`);
    return response.data;
  } catch (error) {
    console.error("Backend Connection Error:", describeError(error));
    return null;
  }
};

export interface BreakWindow {
  name: string;
  start_time: string; // "HH:MM"
  duration_minutes: number;
}

// The four classes the detection model is trained on.
export type GarmentCategory = "SHIRT" | "T_SHIRT" | "TROUSER" | "SHORT";

export const CATEGORIES: GarmentCategory[] = ["SHIRT", "T_SHIRT", "TROUSER", "SHORT"];

export const CATEGORY_LABEL: Record<GarmentCategory, string> = {
  SHIRT: "Shirts",
  T_SHIRT: "T-Shirts",
  TROUSER: "Trousers",
  SHORT: "Shorts",
};

export type CategoryTargets = Record<GarmentCategory, number>;

export interface Settings {
  target_pieces: number;
  category_targets: CategoryTargets;
  start_date: string; // "YYYY-MM-DD" - schedule window start, operator-editable; total_days_allocated = due_date - start_date
  due_date: string; // "YYYY-MM-DD"
  work_start_time: string; // "HH:MM"
  work_end_time: string; // "HH:MM"
  breaks: BreakWindow[];
}

export const fetchSettings = async (): Promise<Settings | null> => {
  try {
    const response = await axios.get(`${API_BASE}/api/settings`);
    return response.data;
  } catch (error) {
    console.error("Settings Fetch Error:", describeError(error));
    return null;
  }
};

export const updateSettings = async (settings: Settings) => {
  const response = await axios.put(`${API_BASE}/api/settings`, settings);
  return response.data;
};

// Bumps the counting baseline to now, without touching target_pieces,
// category_targets, start_date, due_date, or breaks - called automatically
// once a target is completed, to start a fresh counting cycle within the
// same configured target. No garment record is ever touched by this.
export const resetProgress = async (): Promise<{ count_since: string }> => {
  const response = await axios.post(`${API_BASE}/api/settings/reset-progress`);
  return response.data;
};

export interface DailyStat {
  date: string;
  count: number;
}

export const fetchDailyStats = async (): Promise<DailyStat[]> => {
  try {
    const response = await axios.get(`${API_BASE}/api/stats/daily`);
    return response.data;
  } catch (error) {
    console.error("Daily Stats Fetch Error:", describeError(error));
    return [];
  }
};

export interface CategorySummary {
  target_pieces: number;
  // Frozen at target_pieces once is_completed - garments detected after
  // that point are still saved (History Log/Analytics see everything),
  // they just stop being credited toward this number. raw_packed is the
  // true, uncapped count; overrun = raw_packed - total_packed.
  total_packed: number;
  raw_packed: number;
  overrun: number;
  remaining: number;
  is_completed: boolean;
  current_rate_per_hour: number;
  required_rate_per_hour: number;
  efficiency_pct: number | null;
  planned_daily_hours: number;
  estimated_days_to_target: number | null;
  projected_completion_date: string | null;
  due_date: string;
  on_track: boolean | null;
  delayed_days: number | null;
  extra_hours_per_day: number | null;
  total_days_allocated: number;
  total_hours_allocated: number;
  // Only set once is_completed - the exact timestamp of the garment that
  // reached the target, and how long that actually took from count_since.
  completed_at: string | null;
  elapsed_hours: number | null;
  elapsed_days: number | null;
}

export interface DecisionSummary extends CategorySummary {
  categories: Record<GarmentCategory, CategorySummary>;
}

export const fetchSummary = async (): Promise<DecisionSummary | null> => {
  try {
    const response = await axios.get(`${API_BASE}/api/stats/summary`);
    return response.data;
  } catch (error) {
    console.error("Summary Fetch Error:", describeError(error));
    return null;
  }
};

export interface CategoryPrediction {
  predicted_count: number;
  predicted_rate_per_hour: number;
  planned_effective_hours_tomorrow?: number;
  method: string;
  days_used: number;
}

export interface PredictionResult extends CategoryPrediction {
  categories: Record<GarmentCategory, CategoryPrediction>;
}

export const fetchPrediction = async (): Promise<PredictionResult | null> => {
  try {
    const response = await axios.get(`${API_BASE}/api/predict/next-day`);
    return response.data;
  } catch (error) {
    console.error("Prediction Fetch Error:", describeError(error));
    return null;
  }
};

export interface DowntimeEvent {
  type: "breakdown" | "power_failure";
  start: string; // factory-local wall-clock datetime, e.g. "2026-08-22T21:34" (no UTC conversion)
  end: string; // factory-local wall-clock datetime
  reason?: string;
}

export interface DowntimeRecord extends DowntimeEvent {
  _id: string;
}

export const submitDowntime = async (event: DowntimeEvent) => {
  const response = await axios.post(`${API_BASE}/api/downtime`, event);
  return response.data;
};

export const fetchDowntime = async (day?: string): Promise<DowntimeRecord[]> => {
  try {
    const response = await axios.get(`${API_BASE}/api/downtime`, {
      params: day ? { day } : {},
    });
    return response.data;
  } catch (error) {
    console.error("Downtime Fetch Error:", describeError(error));
    return [];
  }
};

export interface CameraDevice {
  camera_index: number;
  camera_label: string;
}

export const fetchCameraDevice = async (): Promise<CameraDevice | null> => {
  try {
    const response = await axios.get(`${API_BASE}/api/device/camera`);
    return response.data;
  } catch (error) {
    console.error("Camera Device Fetch Error:", describeError(error));
    return null;
  }
};

export const updateCameraDevice = async (device: CameraDevice) => {
  const response = await axios.put(`${API_BASE}/api/device/camera`, device);
  return response.data;
};

export interface AvailableCamera {
  index: number;
  name: string;
}

// Enumerated by the CV service via DirectShow (pygrabber) - the same backend
// cv2.VideoCapture(index, cv2.CAP_DSHOW) uses, so this index is guaranteed to
// open the device it's listed against (unlike the browser's own camera list,
// which enumerates through a different OS subsystem and isn't guaranteed to
// agree on ordering).
export const fetchAvailableCameras = async (): Promise<AvailableCamera[]> => {
  try {
    const response = await axios.get(`${CV_API_BASE}/api/device/cameras`);
    return response.data;
  } catch (error) {
    console.error("Camera Enumeration Error:", describeError(error));
    return [];
  }
};

export interface CameraTestResult {
  success: boolean;
  width?: number;
  height?: number;
  error?: string;
}

export const testCameraDevice = async (index: number): Promise<CameraTestResult> => {
  try {
    const response = await axios.post(
      `${CV_API_BASE}/api/device/test-camera`,
      { index },
      { timeout: 20000 }
    );
    return response.data;
  } catch (error) {
    return { success: false, error: describeError(error) };
  }
};

export interface StopCameraResult {
  success: boolean;
  was_running?: boolean;
  error?: string;
}

// Releases the shared camera (e.g. for a Downtime Log breakdown/power
// failure) - the detection loop just idles until a camera is opened again
// via Device Setup.
export const stopCamera = async (): Promise<StopCameraResult> => {
  try {
    const response = await axios.post(`${CV_API_BASE}/api/device/stop-camera`, {}, { timeout: 10000 });
    return response.data;
  } catch (error) {
    return { success: false, error: describeError(error) };
  }
};

export type PipelineState = "STARTING" | "EMPTY" | "UNCERTAIN" | "DETECTING" | "CAPTURED" | "WAITING_REMOVAL";

export interface PipelineStatus {
  state: PipelineState;
  detected_style: string | null;
  confidence: number | null;
  camera_active: boolean;
}

// Polled by the Live Dashboard for a real-time status badge - reflects
// what the pipeline is seeing *right now*, not just the last captured
// garment. In particular this is how "Uncertain" (an unrelated object, not
// a garment) becomes visible to the operator instead of only ever being
// baked into the raw video pixels.
export const fetchPipelineStatus = async (): Promise<PipelineStatus | null> => {
  try {
    const response = await axios.get(`${CV_API_BASE}/api/pipeline/status`, { timeout: 3000 });
    return response.data;
  } catch {
    return null;
  }
};

