"use client";

import type { CSSProperties, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  CalendarDays,
  Camera,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Database,
  Download,
  FileDown,
  Gauge,
  History,
  LayoutDashboard,
  Loader2,
  Menu,
  PackageCheck,
  PieChart,
  Play,
  Plus,
  RotateCcw,
  Save,
  ScanLine,
  Search,
  Settings,
  Shirt,
  Square,
  Target,
  TimerReset,
  Trash2,
  TrendingUp,
  Wifi,
  WifiOff,
  X,
  ArrowLeft,
} from "lucide-react";
import { toast } from "sonner";
import { Toaster } from "@garment-size/components/ui/sonner";
import { Button } from "@garment-size/components/ui/button";
import { Input } from "@garment-size/components/ui/input";
import {
  NativeSelect,
  NativeSelectOption,
} from "@garment-size/components/ui/native-select";
import "./live-scanner.css";


const API_URL = "http://127.0.0.1:8000";


const SCAN_INTERVAL_MS = 300;


const CAPTURE_MAX_WIDTH = 1280;


const JPEG_QUALITY = 0.82;


const SIZES = ["S", "M", "L", "XL"] as const;

// -------------------- TypeScript data models --------------------

type Size = (typeof SIZES)[number];
type Counts = Record<Size, number>;
type Page =
  | "dashboard"
  | "schedule"
  | "history"
  | "analytics"
  | "downtime"
  | "alerts"
  | "settings";
type BreakItem = { id: string; name: string; start: string; end: string };
type Schedule = {
  garmentType: string;
  orderId: string;
  startDate: string;
  endDate: string;
  shiftStart: string;
  shiftEnd: string;
  targets: Counts;
  breaks: BreakItem[];
};
type SessionStatus = "active" | "paused" | "completed";
type ProductionSession = {
  id: string;
  orderId: string;
  garmentType: string;
  status: SessionStatus;
  schedule: Schedule;
  packed: Counts;
  carriedCounts: Counts;
  baselineCounts: Counts;
  createdAt: string;
  startedAt: string;
  activeStartedAt: string;
  endedAt?: string;
  completedAt?: string;
  accumulatedMinutes: number;
  measurementSessionId?: number;
};
type DowntimeEntry = {
  id: string;
  sessionId?: string;
  orderId: string;
  date: string;
  reason: string;
  start: string;
  end: string;
  minutes: number;
  note: string;
  createdAt: string;
};
type LiveMeasurement = {
  state?: string;
  message?: string;
  tracking_state?: string;
  detected?: boolean;
  confidence?: number;
  width_cm?: number;
  length_cm?: number;
  size?: string;
  stable_count?: number;
  stable_required?: number;
  counted_now?: boolean;
  ready_for_next_garment?: boolean;
  annotated_image?: string;
  display_measurement?: {
    garment_type?: string;
    size?: string;
    width_cm?: number;
    length_cm?: number;
    confidence?: number;
  } | null;
};




const ZERO: Counts = { S: 0, M: 0, L: 0, XL: 0 };
const today = () => new Date().toISOString().slice(0, 10);


function createInitialSchedule(): Schedule {
  const currentDate = today();
  return {
    garmentType: "T-Shirt",
    orderId: "",
    startDate: currentDate,
    endDate: currentDate,
    shiftStart: "08:00",
    shiftEnd: "17:00",
    targets: { ...ZERO },
    breaks: [
      { id: "tea-am", name: "Morning tea", start: "10:00", end: "10:15" },
      { id: "lunch", name: "Lunch", start: "12:30", end: "13:00" },
      { id: "tea-pm", name: "Afternoon tea", start: "15:15", end: "15:30" },
    ],
  };
}


const STORE = {
  legacySchedule: "threadscan-schedule-v2",
  legacySessions: "threadscan-sessions-v2",
  legacyActive: "threadscan-active-v2",
  downtime: "threadscan-downtime-v2",
};

// -------------------- Backend helper functions --------------------


async function apiGet(pathname: string): Promise<unknown> {
 
  if (window.garmentDesktop?.sizeApiGet) {
    try {
      return await window.garmentDesktop.sizeApiGet(pathname);
    } catch (error) {
      
      console.warn(
        `Electron IPC failed for ${pathname}. Trying direct backend request.`,
        error,
      );
    }
  }

  // Browser-only fallback, useful when the Next.js UI is opened without Electron.
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(`${API_URL}${pathname}`, {
      method: "GET",
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(
        `Backend returned ${response.status}${body ? `: ${body}` : ""}`,
      );
    }

    return await response.json();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`Backend request timed out: ${API_URL}${pathname}`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}


async function apiMutation<T>(
  method: "POST" | "DELETE",
  pathname: string,
  body?: unknown,
): Promise<T> {
  if (window.garmentDesktop?.sizeApiRequest) {
    return window.garmentDesktop.sizeApiRequest<T>({ method, path: pathname, body });
  }

  const response = await fetch(`${API_URL}${pathname}`, {
    method,
    cache: "no-store",
    headers: body === undefined ? { Accept: "application/json" } : {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let payload: unknown = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { detail: text };
    }
  }
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String(payload.detail)
        : `Backend returned ${response.status}`;
    throw new Error(detail);
  }
  return payload as T;
}

async function persistOrder(session: ProductionSession): Promise<ProductionSession> {
  const response = await apiMutation<{ order: ProductionSession }>(
    "POST",
    "/orders",
    session,
  );
  return response.order;
}


async function apiMeasure(
  image: Blob,
  garmentType: string,
): Promise<LiveMeasurement & { detail?: string }> {
  const fileName = `threadscan-${Date.now()}.jpg`;

  if (window.garmentDesktop?.sizeApiMeasure) {
    return (await window.garmentDesktop.sizeApiMeasure({
      bytes: await image.arrayBuffer(),
      fileName,
      mimeType: image.type || "image/jpeg",
      garmentType,
    })) as LiveMeasurement & { detail?: string };
  }

  // Normal browser development fallback.
  const form = new FormData();
  form.append("file", image, fileName);
  form.append("garment_type", garmentType);

  const response = await fetch(`${API_URL}/measure`, {
    method: "POST",
    body: form,
    cache: "no-store",
  });
  const payload = (await response.json()) as LiveMeasurement & {
    detail?: string;
  };

  if (!response.ok) {
    throw new Error(payload.detail || `Backend returned ${response.status}`);
  }

  return payload;
}

function counts(value: Partial<Counts> = {}): Counts {
  return {
    S: Number(value.S) || 0,
    M: Number(value.M) || 0,
    L: Number(value.L) || 0,
    XL: Number(value.XL) || 0,
  };
}

function hasSizes(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const row = value as Record<string, unknown>;
  return SIZES.some(
    (size) => row[size] !== undefined || row[size.toLowerCase()] !== undefined,
  );
}

function normalizeCounts(payload: unknown, garmentType: string): Counts {
  if (!payload || typeof payload !== "object") return counts();
  const root = payload as Record<string, unknown>;
  const keys = [
    garmentType.toLowerCase(),
    garmentType.toLowerCase().replace(/[^a-z]/g, ""),
    garmentType.toLowerCase().replace("-", "_"),
  ];
  const sources = [
    root.counts,
    root.size_counts,
    root.counts_by_size,
    root.by_size,
    root.session_counts,
    root,
  ];
  for (const source of sources) {
    if (!source || typeof source !== "object" || Array.isArray(source))
      continue;
    const record = source as Record<string, unknown>;
    const candidate = hasSizes(record)
      ? record
      : keys.map((key) => record[key]).find(hasSizes);
    if (candidate && hasSizes(candidate)) {
      return counts({
        S: Number(candidate.S ?? candidate.s),
        M: Number(candidate.M ?? candidate.m),
        L: Number(candidate.L ?? candidate.l),
        XL: Number(candidate.XL ?? candidate.xl),
      });
    }
  }
  return counts();
}

function backendGarmentType(garmentType: string): string | null {
  const normalized = garmentType.toLowerCase().replace(/[^a-z]/g, "");
  if (normalized === "tshirt") return "tshirt";
  if (normalized === "shirt") return "shirt";
  if (normalized === "trouser" || normalized === "trousers") return "trouser";
  return null;
}

function total(value: Counts) {
  return SIZES.reduce((sum, size) => sum + value[size], 0);
}

function sameCounts(a: Counts, b: Counts) {
  return SIZES.every((size) => a[size] === b[size]);
}

function liveSessionCounts(
  session: ProductionSession | null,
  raw: Counts,
): Counts {
  if (!session) return counts();
  const result = counts();
  SIZES.forEach((size) => {
    result[size] =
      session.carriedCounts[size] +
      Math.max(0, raw[size] - session.baselineCounts[size]);
  });
  return result;
}

function minutesBetween(start: string, end: string) {
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  return Math.max(0, eh * 60 + em - sh * 60 - sm);
}

function elapsedMinutes(from: string, to = new Date().toISOString()) {
  return Math.max(0, Math.round((Date.parse(to) - Date.parse(from)) / 60000));
}

function formatDuration(hours: number) {
  if (!Number.isFinite(hours) || hours < 0) return "--";
  const value = Math.round(hours * 60);
  return `${Math.floor(value / 60)}h ${(value % 60).toString().padStart(2, "0")}m`;
}
/** Rounds a chart maximum up to a "nice" value (1, 2, 2.5 or 5 x 10^n) and
 * returns evenly spaced axis ticks from 0, so chart gridlines are easy to read. */
function niceScale(maxValue: number, targetTicks = 4) {
  const rough = Math.max(maxValue, 1) / targetTicks;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step =
    [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((m) => m >= rough) ??
    10 * magnitude;
  const roundedStep = step < 1 ? 1 : Math.round(step);
  const max = Math.ceil(Math.max(maxValue, 1) / roundedStep) * roundedStep;
  const ticks: number[] = [];
  for (let tick = 0; tick <= max; tick += roundedStep) ticks.push(tick);
  return { max, ticks };
}

function formatDateTime(value?: string) {
  if (!value) return "--";
  return new Date(value).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function downloadCsv(session: ProductionSession) {
  const rows: (string | number)[][] = [
    ["Session ID", session.id],
    ["Order ID", session.orderId],
    ["Garment", session.garmentType],
    ["Status", session.status],
    ["Started", session.startedAt],
    ["Ended", session.endedAt ?? ""],
    ["Duration minutes", session.accumulatedMinutes],
    [],
    ["Size", "Target", "Packed", "Remaining", "Completion %"],
    ...SIZES.map((size) => {
      const target = session.schedule.targets[size];
      const packed = session.packed[size];
      return [
        size,
        target,
        packed,
        Math.max(0, target - packed),
        target ? Math.min(100, Math.round((packed / target) * 100)) : 0,
      ];
    }),
    [],
    [
      "Total",
      total(session.schedule.targets),
      total(session.packed),
      Math.max(0, total(session.schedule.targets) - total(session.packed)),
    ],
  ];
  const csv =
    "\uFEFF" +
    rows
      .map((row) =>
        row
          .map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`)
          .join(","),
      )
      .join("\r\n");
  const url = URL.createObjectURL(
    new Blob([csv], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `${session.orderId.replace(/[^a-z0-9-_]/gi, "-")}-${session.id}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// -------------------- Reusable UI components --------------------


function AppLogo() {
  return (
    <div className="brand">
      <div className="brand-mark">
        <Shirt size={25} />
      </div>
      <div>
        <strong>THREADSCAN</strong>
        <span>Packing Intelligence</span>
      </div>
    </div>
  );
}
const primaryNav = [
  { label: "Live Dashboard", icon: LayoutDashboard, page: "dashboard" as Page },
  { label: "Order Setup", icon: PackageCheck, page: "schedule" as Page },
  { label: "Production History", icon: History, page: "history" as Page },
  { label: "Production Analytics", icon: BarChart3, page: "analytics" as Page },
];

function Sidebar({
  page,
  setPage,
  open,
  close,
  onExit,
}: {
  page: Page;
  setPage: (value: Page) => void;
  open: boolean;
  close: () => void;
  onExit: () => void;
}) {
  const go = (value: Page) => {
    setPage(value);
    close();
  };
  const item = (label: string, Icon: typeof Target, target: Page) => (
    <button
      key={label}
      type="button"
      className={page === target ? "nav-active" : ""}
      onClick={() => go(target)}
    >
      <Icon size={19} />
      <span>{label}</span>
    </button>
  );
  return (
    <>
      {open && (
        <button
          type="button"
          className="sidebar-scrim"
          onClick={close}
          aria-label="Close menu"
        />
      )}
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <button type="button" className="mobile-close" onClick={close} aria-label="Close">
          <X />
        </button>
        <AppLogo />
        <p className="nav-caption">MONITOR</p>
        <nav>
          {primaryNav.map((entry) => item(entry.label, entry.icon, entry.page))}
        </nav>
        <p className="nav-caption admin-caption">SETUP &amp; ADMIN</p>
        <nav>
          {item("Target & Schedule", CalendarDays, "schedule")}
          {item("Downtime Log", TimerReset, "downtime")}
          {item("Alerts", Bell, "alerts")}
          {item("Settings", Settings, "settings")}
        </nav>
        <div className="sidebar-spacer" />
        <button className="size-switch-feature" type="button" onClick={onExit}>
          <ArrowLeft size={16} /> Switch feature
        </button>
        <div className="system-chip">
          <span className="system-dot" /> Backend service
        </div>
        <div className="user-card">
          <div className="avatar">UC</div>
          <div>
            <strong>Uchith Chethana</strong>
            <span>Production Admin</span>
          </div>
        </div>
      </aside>
    </>
  );
}

function Header({ title, online }: { title: string; online: boolean }) {
  const now = new Date();
  return (
    <header className="topbar">
      <button
        type="button"
        className="menu-button"
        onClick={() => window.dispatchEvent(new Event("open-nav"))}
      >
        <Menu />
      </button>
      <div>
        <h1>{title}</h1>
        <p>
          {now.toLocaleDateString("en-GB", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
          })}
        </p>
      </div>
      <div className={`engine-status ${online ? "online" : "offline"}`}>
        {online ? <Wifi size={16} /> : <WifiOff size={16} />}
        <span>{online ? "BACKEND CONNECTED" : "BACKEND OFFLINE"}</span>
      </div>
    </header>
  );
}

function Kpi({
  label,
  value,
  detail,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string | number;
  detail: string;
  icon: typeof Target;
  tone: string;
}) {
  return (
    <article className={`kpi-card tone-${tone}`}>
      <div className="kpi-icon">
        <Icon size={21} />
      </div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="form-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function SummaryStat({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <article className="summary-stat">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

// -------------------- Live Automatic Scanning card --------------------


function LiveScanner({
  garmentType,
  online,
  active,
}: {
  garmentType: string;
  online: boolean;
  active: boolean;
}) {
  
  const videoRef = useRef<HTMLVideoElement | null>(null);

  
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  
  const processingRef = useRef(false);

  
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);

  
  const [selectedDeviceId, setSelectedDeviceId] = useState("");

  
  const [cameraReady, setCameraReady] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [scanError, setScanError] = useState("");

  
  const [result, setResult] = useState<LiveMeasurement | null>(null);

  
  const [annotatedImage, setAnnotatedImage] = useState<string | null>(null);

  
  const backendType = backendGarmentType(garmentType);

  
  useEffect(() => {
    let cancelled = false;
    let stream: MediaStream | null = null;

    const startCamera = async () => {
      setCameraReady(false);
      setCameraError("");

      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            deviceId: selectedDeviceId
              ? { exact: selectedDeviceId }
              : undefined,
            width: { ideal: 1920 },
            height: { ideal: 1080 },
            aspectRatio: { ideal: 16 / 9 },
            frameRate: { ideal: 30 },
          },
        });

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        const video = videoRef.current;
        if (!video) return;
        video.srcObject = stream;
        await video.play();

        const cameraDevices = (
          await navigator.mediaDevices.enumerateDevices()
        ).filter((device) => device.kind === "videoinput");
        setDevices(cameraDevices);

        const currentDeviceId = stream
          .getVideoTracks()[0]
          ?.getSettings().deviceId;
        if (!selectedDeviceId && currentDeviceId)
          setSelectedDeviceId(currentDeviceId);
        setCameraReady(true);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setCameraError(`Camera could not start: ${message}`);
      }
    };

    void startCamera();
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((track) => track.stop());
      if (videoRef.current) videoRef.current.srcObject = null;
    };
  }, [selectedDeviceId]);

  
  const scanFrame = useCallback(async () => {
    // Measurement must remain active even before an order is created. The
    // session baseline logic below decides which backend counts belong to a
    // production session, so detection itself must not be blocked here.
    if (!online || !cameraReady || !backendType || processingRef.current)
      return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (
      !video ||
      !canvas ||
      video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
      video.videoWidth === 0 ||
      video.videoHeight === 0
    )
      return;

    processingRef.current = true;
    setScanning(true);

    try {
      // Preserve the camera's original aspect ratio. Forcing every frame to
      // 1920x1080 stretches 4:3 or reduced-resolution streams and changes the
      // measured shirt width/length enough to switch between S and M.
      const scale = Math.min(1, CAPTURE_MAX_WIDTH / video.videoWidth);
      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);
      const context = canvas.getContext("2d", { alpha: false });
      if (!context) throw new Error("Camera canvas is unavailable");
      context.drawImage(video, 0, 0, canvas.width, canvas.height);

      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (value) =>
            value
              ? resolve(value)
              : reject(new Error("Camera frame encoding failed")),
          "image/jpeg",
          JPEG_QUALITY,
        );
      });

      
      const payload = await apiMeasure(blob, backendType);

      setResult(payload);
      setScanError("");
      const trackingState = payload.tracking_state || payload.state;
      const stableCount = Number(payload.stable_count) || 0;
      const stableRequired = Number(payload.stable_required) || 3;
      
      const acceptedMeasurement = Boolean(
        payload.counted_now ||
        trackingState === "COUNTED" ||
        trackingState === "WAIT_REMOVAL" ||
        stableCount >= stableRequired,
      );

      // Do not replace the preview with a noisy single-frame S/M result.
      // The accepted image appears only after the backend's stable-frame gate.
      if (payload.annotated_image && acceptedMeasurement) {
        setAnnotatedImage(`data:image/jpeg;base64,${payload.annotated_image}`);
      } else if (
        payload.state === "NO_GARMENT" ||
        payload.tracking_state === "EMPTY"
      ) {
        setAnnotatedImage(null);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setScanError(message);
    } finally {
      setScanning(false);
      processingRef.current = false;
    }
  }, [backendType, cameraReady, online]);


  useEffect(() => {
    const timer = window.setInterval(() => void scanFrame(), SCAN_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [scanFrame]);


  const stableCount = Number(result?.stable_count) || 0;
  const stableRequired = Number(result?.stable_required) || 3;
  const resultState = result?.tracking_state || result?.state;
  const measurementAccepted = Boolean(
    result?.counted_now ||
    resultState === "COUNTED" ||
    resultState === "WAIT_REMOVAL" ||
    stableCount >= stableRequired,
  );
  const displayed = measurementAccepted
    ? (result?.display_measurement ?? result)
    : null;
  const state = !online
    ? "BACKEND OFFLINE"
    : !backendType
      ? "UNSUPPORTED GARMENT"
      : cameraError
        ? "CAMERA ERROR"
        : result?.tracking_state || result?.state || "SCANNING";

  return (
    <section className="panel live-scanner-panel">
      {/* Card heading: title, camera selector සහ scanning state */}
      <div className="scanner-heading">
        <div className="scanner-title">
          <span>
            <ScanLine size={19} />
          </span>
          <div>
            <h2>Live Automatic Scanning</h2>
            <p>Automatic garment measurement from the fixed 100 cm camera.</p>
          </div>
        </div>
        <div className="scanner-controls">
          <label>
            <Camera size={14} />
            <select
              value={selectedDeviceId}
              onChange={(event) => setSelectedDeviceId(event.target.value)}
              disabled={!devices.length}
            >
              {devices.map((device, index) => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.label || `Camera ${index + 1}`}
                </option>
              ))}
            </select>
          </label>
          <span
            className={`scanner-state ${state === "READY" || state === "WAIT_REMOVAL" ? "ready" : state.includes("ERROR") || state.includes("OFFLINE") ? "error" : "waiting"}`}
          >
            {scanning && <Loader2 className="spin" size={13} />}
            {state}
          </span>
        </div>
      </div>
      <div className="scanner-body">
        {/* Left side: original camera view හෝ accepted annotated image */}
        <div className="scanner-preview">
          <video ref={videoRef} autoPlay muted playsInline />
          {annotatedImage && (
            <img
              src={annotatedImage}
              alt="Detected garment with measurement lines"
            />
          )}
          <canvas ref={canvasRef} aria-hidden="true" />
          <div className="detection-zone">
            <span>Detection zone</span>
          </div>
          <b className="automatic-chip">
            <span /> Live automatic scanning
          </b>
          {!cameraReady && (
            <div className="preview-message">
              {cameraError || "Starting camera..."}
            </div>
          )}
        </div>

        {/* Right side: detected size, confidence, width සහ length */}
        <aside className="scanner-measurements">
          <div className="measurement-top">
            <span>LIVE MEASUREMENT</span>
            <strong>{displayed?.size || "--"}</strong>
          </div>
          <div className="measurement-grid">
            <div>
              <span>Garment</span>
              <strong>{garmentType}</strong>
            </div>
            <div>
              <span>Confidence</span>
              <strong>
                {displayed?.confidence != null
                  ? `${(Number(displayed.confidence) * 100).toFixed(1)}%`
                  : "--"}
              </strong>
            </div>
            <div>
              <span>Chest width</span>
              <strong>
                {displayed?.width_cm != null
                  ? `${Number(displayed.width_cm).toFixed(1)} cm`
                  : "--"}
              </strong>
            </div>
            <div>
              <span>Body length</span>
              <strong>
                {displayed?.length_cm != null
                  ? `${Number(displayed.length_cm).toFixed(1)} cm`
                  : "--"}
              </strong>
            </div>
          </div>
          <div className="stable-progress">
            <div>
              <span>Stable frames</span>
              <b>
                {stableCount}/{stableRequired}
              </b>
            </div>
            <div>
              <i
                style={{
                  width: `${Math.min(100, (stableCount / Math.max(stableRequired, 1)) * 100)}%`,
                }}
              />
            </div>
          </div>
          <p className={scanError ? "scanner-error" : "scanner-message"}>
            {scanError ||
              cameraError ||
              result?.message ||
              (active
                ? "Place one fully unfolded garment inside the detection zone."
                : "Automatic measurement is active. Create an order to track its production count.")}
          </p>
        </aside>
      </div>
    </section>
  );
}

// -------------------- Main Dashboard page --------------------


function Dashboard({
  schedule,
  production,
  online,
  loading,
  lastUpdated,
  active,
  edit,
  end,
}: {
  schedule: Schedule;
  production: Counts;
  online: boolean;
  loading: boolean;
  lastUpdated: Date | null;
  active: ProductionSession | null;
  edit: () => void;
  end: () => void;
}) {
  
  const target = total(schedule.targets);

  
  const packed = total(production);

  
  const remaining = Math.max(0, target - packed);

  
  const breakMinutes = schedule.breaks.reduce(
    (sum, item) => sum + minutesBetween(item.start, item.end),
    0,
  );
  
  const workHours = Math.max(
    1,
    (minutesBetween(schedule.shiftStart, schedule.shiftEnd) - breakMinutes) /
      60,
  );
  
  const activeMinutes = active
    ? active.accumulatedMinutes + elapsedMinutes(active.activeStartedAt)
    : 0;
  
  const speed = activeMinutes ? Math.round(packed / (activeMinutes / 60)) : 0;

  
  const remainingHours = speed ? remaining / speed : 0;

  // Overall order completion percentage.
  const completion = target
    ? Math.min(100, Math.round((packed / target) * 100))
    : 0;
  
  const predicted =
    lastUpdated && speed
      ? new Date(lastUpdated.getTime() + remainingHours * 3600000)
      : null;
  return (
    <>
      <Header title="Packing Production Dashboard" online={online} />
      <main className="content">
        {/* ORDER CONTEXT BAR: garment, order, shift, live state සහ buttons */}
        <section className={`context-bar ${active ? "" : "no-session"}`}>
          <div>
            <label>GARMENT TYPE</label>
            <strong>
              <Shirt size={17} /> {schedule.garmentType}
            </strong>
          </div>
          <div>
            <label>ORDER ID</label>
            <strong>{active ? schedule.orderId : "No active order"}</strong>
          </div>
          <div>
            <label>PRODUCTION WINDOW</label>
            <strong>
              {schedule.shiftStart} – {schedule.shiftEnd}
            </strong>
          </div>
          <div className="live-cell">
            <span className={active ? "live-pulse" : "idle-dot"} />
            {active ? "LIVE" : "IDLE"}
          </div>
          <div className="context-actions">
            <Button
              className="end-session-button"
              disabled={!active}
              onClick={end}
            >
              <Square /> End session
            </Button>
            <Button variant="outline" onClick={edit}>
              Edit target <ChevronRight />
            </Button>
          </div>
        </section>
        {!active && (
          
          <section className="session-callout">
            <AlertTriangle />
            <div>
              <strong>No production session is running</strong>
              <span>
                Create an order, or resume a paused session from History.
              </span>
            </div>
            <Button onClick={edit}>Create order</Button>
          </section>
        )}

        {}
        <section className="kpi-grid">
          <Kpi
            label="TOTAL PACKED"
            value={packed}
            detail="pieces this session"
            icon={PackageCheck}
            tone="blue"
          />
          <Kpi
            label="FULL TARGET"
            value={target}
            detail="planned pieces"
            icon={Target}
            tone="violet"
          />
          <Kpi
            label="REMAINING"
            value={remaining}
            detail={`${completion}% completed`}
            icon={Gauge}
            tone="amber"
          />
          <Kpi
            label="ELAPSED"
            value={formatDuration(activeMinutes / 60)}
            detail="effective session time"
            icon={Clock3}
            tone="cyan"
          />
          <Kpi
            label="CURRENT SPEED"
            value={speed}
            detail="pieces / hour"
            icon={Activity}
            tone="green"
          />
        </section>

        
        <div className="dashboard-grid">
          
          <section className="panel production-panel">
            <div className="panel-heading">
              <div>
                <h2>Size-wise Production</h2>
                <p>Live output against the active session target.</p>
              </div>
              {loading && <Loader2 className="spin" />}
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>SIZE</th>
                    <th>TARGET</th>
                    <th>PACKED</th>
                    <th>REMAINING</th>
                    <th>SPEED</th>
                    <th>PROGRESS</th>
                    <th>STATUS</th>
                  </tr>
                </thead>
                <tbody>
                  {SIZES.map((size) => {
                    
                    const goal = schedule.targets[size],
                      done = active ? production[size] : 0,
                      left = Math.max(0, goal - done),
                      percent = goal
                        ? Math.min(100, Math.round((done / goal) * 100))
                        : 0;
                    const status =
                      percent >= 100
                        ? "Complete"
                        : percent >= 70
                          ? "On track"
                          : percent >= 40
                            ? "Packing"
                            : goal
                              ? "At risk"
                              : "Not set";
                    return (
                      <tr key={size}>
                        <td>
                          <span
                            className={`size-badge size-${size.toLowerCase()}`}
                          >
                            {size}
                          </span>
                        </td>
                        <td>{goal}</td>
                        <td>
                          <strong>{done}</strong>
                        </td>
                        <td>{left}</td>
                        <td>
                          {packed ? Math.round((speed * done) / packed) : 0}/h
                        </td>
                        <td>
                          <div className="progress-cell">
                            <span>{percent}%</span>
                            <div className="progress-track">
                              <i style={{ width: `${percent}%` }} />
                            </div>
                          </div>
                        </td>
                        <td>
                          <span
                            className={`status-pill status-${status.toLowerCase().replace(" ", "-")}`}
                          >
                            {status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {/* CARD 2: Camera + backend live garment measurement */}
          <LiveScanner
            garmentType={schedule.garmentType}
            online={online}
            active={Boolean(active)}
          />

          {/* CARD 3: Current speed භාවිත කර predicted completion පෙන්වයි. */}
          <section className="panel prediction-panel">
            <div className="prediction-title">
              <span>
                <TrendingUp size={20} />
              </span>
              <div>
                <h2>Production Forecast</h2>
                <p>Calculated from the current packing pace</p>
              </div>
            </div>
            <div className="prediction-time">
              <label>PREDICTED COMPLETION</label>
              <strong>
                {predicted
                  ? predicted.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "--:--"}
              </strong>
              <span>
                {predicted
                  ? predicted.toLocaleDateString("en-GB", {
                      day: "2-digit",
                      month: "short",
                    })
                  : "Waiting for pace"}
              </span>
            </div>
            <div className="prediction-stats">
              <div>
                <span>Remaining time</span>
                <strong>{speed ? formatDuration(remainingHours) : "--"}</strong>
              </div>
              <div>
                <span>Current speed</span>
                <strong>{speed} pcs/hr</strong>
              </div>
              <div>
                <span>Required speed</span>
                <strong>{Math.ceil(target / workHours)} pcs/hr</strong>
              </div>
              <div>
                <span>Backend</span>
                <strong>{online ? "Connected" : "Offline"}</strong>
              </div>
            </div>
            <div className="forecast-note">
              <CheckCircle2 size={17} />
              <span>
                Forecast updates automatically as the session count changes.
              </span>
            </div>
          </section>

          {/* CARD 4: size  target and packed count bar comparison */}
          <section className="panel chart-panel">
            <div className="panel-heading">
              <div>
                <h2>Target vs Packed</h2>
                <p>Current output by garment size.</p>
              </div>
            </div>
            <div className="bar-chart">
              {SIZES.map((size) => {
                const max = Math.max(...Object.values(schedule.targets), 1);
                return (
                  <div className="bar-row" key={size}>
                    <b>{size}</b>
                    <div className="bars">
                      <i
                        className="target-bar"
                        style={{
                          width: `${(schedule.targets[size] / max) * 100}%`,
                        }}
                      />
                      <i
                        className="packed-bar"
                        style={{
                          width: `${(Math.min(production[size], max) / max) * 100}%`,
                        }}
                      />
                    </div>
                    <span>
                      {production[size]}/{schedule.targets[size]}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="legend">
              <span>
                <i className="legend-target" /> Target
              </span>
              <span>
                <i className="legend-packed" /> Packed
              </span>
            </div>
          </section>

          {/* CARD 5: All sizes sum overall completion donut */}
          <section className="panel completion-panel">
            <div className="panel-heading">
              <div>
                <h2>Overall Target Completion</h2>
                <p>Order progress across all sizes.</p>
              </div>
            </div>
            <div className="completion-body">
              <div
                className="donut"
                style={
                  { "--progress": `${completion * 3.6}deg` } as CSSProperties
                }
              >
                <div>
                  <strong>{completion}%</strong>
                  <span>COMPLETE</span>
                </div>
              </div>
              <div className="completion-copy">
                <strong>{remaining} pieces remaining</strong>
                <p>
                  {speed
                    ? `Expected finish in ${formatDuration(remainingHours)} at the current speed.`
                    : "A completion time appears after production starts."}
                </p>
                <small>
                  {lastUpdated
                    ? `Last synced ${lastUpdated.toLocaleTimeString()}`
                    : "Waiting for backend sync"}
                </small>
              </div>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}

// -------------------- Target & Schedule page --------------------


function TargetSchedule({
  value,
  online,
  active,
  onSave,
}: {
  value: Schedule;
  online: boolean;
  active: ProductionSession | null;
  onSave: (value: Schedule) => Promise<void>;
}) {
  
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);

  
  useEffect(() => setDraft(value), [value]);

  
  const goal = total(draft.targets),
    breakMinutes = draft.breaks.reduce(
      (sum, item) => sum + minutesBetween(item.start, item.end),
      0,
    );
  const shiftMinutes = minutesBetween(draft.shiftStart, draft.shiftEnd),
    effectiveHours = Math.max(0, (shiftMinutes - breakMinutes) / 60);
  
  const changeTarget = (size: Size, value: string) =>
    setDraft((current) => ({
      ...current,
      targets: { ...current.targets, [size]: Math.max(0, Number(value) || 0) },
    }));
  
  const changeBreak = (id: string, field: keyof BreakItem, value: string) =>
    setDraft((current) => ({
      ...current,
      breaks: current.breaks.map((item) =>
        item.id === id ? { ...item, [field]: value } : item,
      ),
    }));
  
  const save = async () => {
    if (!draft.orderId.trim()) return toast.error("Enter an Order ID");
    if (!draft.startDate) return toast.error("Select a start date");
    if (!draft.endDate) return toast.error("Select an end date");
    if (draft.startDate > draft.endDate)
      return toast.error("End date cannot be before start date");
    if (!goal) return toast.error("Set at least one size target above 0");
    if (draft.shiftStart >= draft.shiftEnd)
      return toast.error("Shift end time must be after shift start time");
    const invalidBreak = draft.breaks.find(
      (item) =>
        !item.name.trim() ||
        item.start >= item.end ||
        item.start < draft.shiftStart ||
        item.end > draft.shiftEnd,
    );
    if (invalidBreak)
      return toast.error(
        `${invalidBreak.name || "A break"} must have valid times inside the shift`,
      );
    if (shiftMinutes <= breakMinutes)
      return toast.error(
        "Shift time must be longer than the configured breaks",
      );
    setSaving(true);
    try {
      await onSave({ ...draft, orderId: draft.orderId.trim() });
    } finally {
      setSaving(false);
    }
  };
  return (
    <>
      <Header title="Target & Schedule" online={online} />
      <main className="content schedule-content">
        <div className="page-intro">
          <div>
            <h2>Production Configuration</h2>
            <p>
              Set the order target, size split, working hours and planned
              breaks.
            </p>
          </div>
          <span className="config-badge">
            <Database size={16} /> Saved to SQLite
          </span>
        </div>
        {active && active.orderId !== draft.orderId && (
          <div className="inline-warning">
            <AlertTriangle /> End active order {active.orderId} before starting
            another order.
          </div>
        )}
        <div className="schedule-grid">
          {/* Left card: editable order form sections 1-4 */}
          <section className="panel form-panel">
            <div className="form-section">
              <div className="section-number">1</div>
              <div className="section-content">
                <h3>Order details</h3>
                <p>Select garment type and define the production order.</p>
                <div className="form-grid three">
                  <Field label="Garment type">
                    <NativeSelect
                      className="w-full"
                      value={draft.garmentType}
                      onChange={(e) =>
                        setDraft({ ...draft, garmentType: e.target.value })
                      }
                    >
                      <NativeSelectOption>T-Shirt</NativeSelectOption>
                      <NativeSelectOption>Shirt</NativeSelectOption>
                      <NativeSelectOption>Trouser</NativeSelectOption>
                      <NativeSelectOption>Shorts</NativeSelectOption>
                    </NativeSelect>
                  </Field>
                  <Field label="Order ID">
                    <Input
                      placeholder="ORD-2026-001"
                      value={draft.orderId}
                      onChange={(e) =>
                        setDraft({ ...draft, orderId: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Start date">
                    <Input
                      type="date"
                      value={draft.startDate}
                      onChange={(e) => {
                        const startDate = e.target.value;
                        setDraft((current) => ({
                          ...current,
                          startDate,
                          endDate:
                            current.endDate && current.endDate >= startDate
                              ? current.endDate
                              : startDate,
                        }));
                      }}
                    />
                  </Field>
                </div>
              </div>
            </div>
            <div className="form-section">
              <div className="section-number">2</div>
              <div className="section-content">
                <h3>Size-wise target</h3>
                <p>Reset changes every value in this section to 0.</p>
                <div className="target-inputs">
                  {SIZES.map((size) => (
                    <Field key={size} label={`Size ${size}`}>
                      <Input
                        type="number"
                        min="0"
                        value={draft.targets[size]}
                        onChange={(e) => changeTarget(size, e.target.value)}
                      />
                    </Field>
                  ))}
                </div>
              </div>
            </div>
            <div className="form-section">
              <div className="section-number">3</div>
              <div className="section-content">
                <h3>Shift schedule</h3>
                <p>Configure active production time.</p>
                <div className="form-grid three">
                  <Field label="Shift starts">
                    <Input
                      type="time"
                      value={draft.shiftStart}
                      onChange={(e) =>
                        setDraft({ ...draft, shiftStart: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Shift ends">
                    <Input
                      type="time"
                      value={draft.shiftEnd}
                      onChange={(e) =>
                        setDraft({ ...draft, shiftEnd: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="End date">
                    <Input
                      type="date"
                      min={draft.startDate || undefined}
                      value={draft.endDate}
                      onChange={(e) =>
                        setDraft({ ...draft, endDate: e.target.value })
                      }
                    />
                  </Field>
                </div>
              </div>
            </div>
            <div className="form-section last">
              <div className="section-number">4</div>
              <div className="section-content">
                <div className="break-title">
                  <div>
                    <h3>Fixed breaks</h3>
                    <p>Break duration is removed from effective work time.</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setDraft((current) => ({
                        ...current,
                        breaks: [
                          ...current.breaks,
                          {
                            id: crypto.randomUUID(),
                            name: "New break",
                            start: "14:00",
                            end: "14:15",
                          },
                        ],
                      }))
                    }
                  >
                    <Plus /> Add break
                  </Button>
                </div>
                <div className="break-list">
                  {draft.breaks.map((item) => (
                    <div className="break-row" key={item.id}>
                      <Input
                        value={item.name}
                        onChange={(e) =>
                          changeBreak(item.id, "name", e.target.value)
                        }
                      />
                      <Input
                        type="time"
                        value={item.start}
                        onChange={(e) =>
                          changeBreak(item.id, "start", e.target.value)
                        }
                      />
                      <span>to</span>
                      <Input
                        type="time"
                        value={item.end}
                        onChange={(e) =>
                          changeBreak(item.id, "end", e.target.value)
                        }
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() =>
                          setDraft((current) => ({
                            ...current,
                            breaks: current.breaks.filter(
                              (entry) => entry.id !== item.id,
                            ),
                          }))
                        }
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="form-actions">
              {/* New order form fresh defaults  reset . */}
              <Button
                variant="outline"
                onClick={() => {
                  if (active) {
                    setDraft((current) => ({ ...current, targets: counts() }));
                    toast.info("All size targets reset to 0");
                  } else {
                    setDraft(createInitialSchedule());
                    toast.info("All new-order values were reset");
                  }
                }}
              >
                <RotateCcw /> {active ? "Reset targets" : "Reset order"}
              </Button>
              <Button className="save-button" onClick={save} disabled={saving}>
                {saving ? <Loader2 className="spin" /> : <Save />}
                {saving
                  ? "Saving..."
                  : active
                    ? "Update session"
                    : "Save & start session"}
              </Button>
            </div>
          </section>

          {/* Right card: form values  live order summary  */}
          <aside className="panel summary-panel">
            <div className="summary-icon">
              <CalendarDays />
            </div>
            <h2>Order Summary</h2>
            <p>Production plan for this order.</p>
            <div className="summary-total">
              <span>TOTAL TARGET</span>
              <strong>{goal}</strong>
              <small>pieces</small>
            </div>
            <div className="summary-list">
              <div>
                <span>Order ID</span>
                <strong>{draft.orderId || "Not set"}</strong>
              </div>
              <div>
                <span>Garment</span>
                <strong>{draft.garmentType}</strong>
              </div>
              <div>
                <span>Shift</span>
                <strong>{formatDuration(shiftMinutes / 60)}</strong>
              </div>
              <div>
                <span>Breaks</span>
                <strong>{breakMinutes} min</strong>
              </div>
              <div>
                <span>Effective time</span>
                <strong>{formatDuration(effectiveHours)}</strong>
              </div>
              <div>
                <span>Required speed</span>
                <strong>
                  {effectiveHours ? Math.ceil(goal / effectiveHours) : 0} pcs/hr
                </strong>
              </div>
            </div>
            <div className="size-summary">
              {SIZES.map((size) => (
                <div key={size}>
                  <b className={`size-badge size-${size.toLowerCase()}`}>
                    {size}
                  </b>
                  <span>{draft.targets[size]} pcs</span>
                </div>
              ))}
            </div>
            <div className="plan-note">
              <Target size={18} />
              <p>
                Dashboard and history use this size split as the order target.
              </p>
            </div>
          </aside>
        </div>
      </main>
    </>
  );
}

// -------------------- Production History page --------------------


function OrderSummary({
  session,
  onResume,
  active,
}: {
  session: ProductionSession;
  onResume: (session: ProductionSession) => void;
  active: boolean;
}) {
  const goal = total(session.schedule.targets),
    packed = total(session.packed),
    progress = goal ? Math.min(100, Math.round((packed / goal) * 100)) : 0;
  return (
    <section className="panel order-summary-card">
      <div className="order-summary-head">
        <div>
          <span>ORDER SUMMARY</span>
          <h2>{session.orderId}</h2>
          <p>
            {session.id} · {session.garmentType} ·{" "}
            {formatDateTime(session.startedAt)}
          </p>
        </div>
        <div className="summary-actions">
          {session.status === "paused" && (
            <Button disabled={active} onClick={() => onResume(session)}>
              <Play /> Resume from {packed}
            </Button>
          )}
          <Button variant="outline" onClick={() => downloadCsv(session)}>
            <FileDown /> Download CSV
          </Button>
        </div>
      </div>
      <div className="order-summary-grid">
        <div className="summary-progress-card">
          <div
            className="mini-donut"
            style={{ "--progress": `${progress * 3.6}deg` } as CSSProperties}
          >
            <strong>{progress}%</strong>
          </div>
          <div>
            <span>SESSION OUTPUT</span>
            <strong>
              {packed} / {goal}
            </strong>
            <small>{Math.max(0, goal - packed)} remaining</small>
          </div>
        </div>
        <div className="summary-size-table">
          {SIZES.map((size) => (
            <div key={size}>
              <b className={`size-badge size-${size.toLowerCase()}`}>{size}</b>
              <span>Target {session.schedule.targets[size]}</span>
              <strong>{session.packed[size]} packed</strong>
              <em>
                {Math.max(
                  0,
                  session.schedule.targets[size] - session.packed[size],
                )}{" "}
                remaining
              </em>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
/** Session search, resume, CSV download and summary */
function HistoryPage({
  sessions,
  online,
  active,
  resume,
  remove,
}: {
  sessions: ProductionSession[];
  online: boolean;
  active: ProductionSession | null;
  resume: (session: ProductionSession) => Promise<void>;
  remove: (session: ProductionSession) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(
    sessions[0]?.id ?? null,
  );
  
  const ordered = useMemo(
    () =>
      [...sessions]
        .filter((session) =>
          session.orderId.toLowerCase().includes(query.trim().toLowerCase()),
        )
        .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt)),
    [sessions, query],
  );
  const selected =
    sessions.find((session) => session.id === selectedId) ?? ordered[0];
  return (
    <>
      <Header title="Production History" online={online} />
      <main className="content">
        <div className="page-intro history-intro">
          <div>
            <h2>Session-by-session History</h2>
            <p>Every session is stored and searchable by Order ID.</p>
          </div>
          <div className="search-box">
            <Search />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by Order ID..."
            />
          </div>
        </div>
        <section className="summary-strip">
          <SummaryStat
            label="ALL SESSIONS"
            value={sessions.length}
            detail="stored sessions"
          />
          <SummaryStat
            label="COMPLETED"
            value={sessions.filter((s) => s.status === "completed").length}
            detail="targets completed"
          />
          <SummaryStat
            label="PAUSED"
            value={sessions.filter((s) => s.status === "paused").length}
            detail="available to resume"
          />
          <SummaryStat
            label="TOTAL PACKED"
            value={sessions.reduce((sum, s) => sum + total(s.packed), 0)}
            detail="historical pieces"
          />
        </section>
        <section className="panel history-panel">
          <div className="panel-heading">
            <div>
              <h2>Order Sessions</h2>
              <p>{ordered.length} matching session(s), newest first.</p>
            </div>
            <span className="table-hint">Select a row for its summary</span>
          </div>
          <div className="table-wrap">
            <table className="history-table">
              <thead>
                <tr>
                  <th>SESSION</th>
                  <th>ORDER ID</th>
                  <th>GARMENT</th>
                  <th>STARTED</th>
                  <th>PACKED / TARGET</th>
                  <th>PROGRESS</th>
                  <th>STATUS</th>
                  <th>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {ordered.map((session) => {
                  const goal = total(session.schedule.targets),
                    packed = total(session.packed),
                    progress = goal
                      ? Math.min(100, Math.round((packed / goal) * 100))
                      : 0;
                  return (
                    <tr
                      key={session.id}
                      className={
                        selected?.id === session.id ? "selected-row" : ""
                      }
                      onClick={() => setSelectedId(session.id)}
                    >
                      <td>
                        <strong>{session.id}</strong>
                      </td>
                      <td>
                        <b>{session.orderId}</b>
                      </td>
                      <td>{session.garmentType}</td>
                      <td>{formatDateTime(session.startedAt)}</td>
                      <td>
                        {packed} / {goal}
                      </td>
                      <td>
                        <div className="history-progress">
                          <i style={{ width: `${progress}%` }} />
                          <span>{progress}%</span>
                        </div>
                      </td>
                      <td>
                        <span className={`session-status ${session.status}`}>
                          {session.status}
                        </span>
                      </td>
                      <td>
                        <div
                          className="row-actions"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {session.status === "paused" && (
                            <Button
                              size="sm"
                              className="resume-button"
                              disabled={Boolean(active)}
                              onClick={() => resume(session)}
                            >
                              <Play /> Start
                            </Button>
                          )}
                          {session.status === "active" && (
                            <span className="active-label">Running</span>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => downloadCsv(session)}
                          >
                            <Download /> CSV
                          </Button>
                          {session.status !== "active" && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="delete-order-button"
                              aria-label={`Delete order ${session.orderId}`}
                              onClick={() => void remove(session)}
                            >
                              <Trash2 /> Delete
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {!ordered.length && (
                  <tr>
                    <td colSpan={8} className="empty-table">
                      No session found for that Order ID.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
        {selected && (
          <OrderSummary
            session={selected}
            onResume={resume}
            active={Boolean(active)}
          />
        )}
      </main>
    </>
  );
}

// -------------------- Production Analytics page --------------------

/** Saved session history use charts and forecast values . */
function AnalyticsPage({
  sessions,
  active,
  online,
}: {
  sessions: ProductionSession[];
  active: ProductionSession | null;
  online: boolean;
}) {
  // packed count size-wise .
  const sizeTotals = counts();
  sessions.forEach((session) =>
    SIZES.forEach((size) => {
      sizeTotals[size] += session.packed[size];
    }),
  );
  const packed = total(sizeTotals),
    target = sessions.reduce(
      (sum, session) => sum + total(session.schedule.targets),
      0,
    );
  // Pie chart size colours.
  const palette: Record<Size, string> = {
    S: "#2087ed",
    M: "#7b5bd6",
    L: "#f0a23a",
    XL: "#1fb47d",
  };
  let angle = 0;
  const stops = SIZES.map((size) => {
    const start = angle;
    angle += packed ? (sizeTotals[size] / packed) * 360 : 0;
    return `${palette[size]} ${start}deg ${angle}deg`;
  }).join(",");
  // Trend chart production new sessions 7 only.
  const recent = [...sessions]
    .filter((s) => total(s.packed) > 0)
    .sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt))
    .slice(-7);
  const average = recent.length
      ? Math.round(
          recent.reduce((sum, s) => sum + total(s.packed), 0) / recent.length,
        )
      : 0,
    forecast = Math.round(average * 1.06);
  // Trend chart scale: one shared pcs axis for packed bars, session targets
  // and the forecast, rounded up to a "nice" maximum with 4-5 gridlines.
  const trendScale = niceScale(
    Math.max(
      ...recent.map((s) => Math.max(total(s.packed), total(s.schedule.targets))),
      forecast,
      1,
    ),
  );
  const pct = (value: number) => (value / trendScale.max) * 100;
  const trendSummary = recent.length
    ? recent
        .map(
          (s, index) =>
            `Session ${index + 1} (${s.orderId}): ${total(s.packed)} pieces packed`,
        )
        .join("; ") + `; next-session forecast: ${forecast} pieces.`
    : "No completed sessions yet.";
  return (
    <>
      <Header title="Production Analytics" online={online} />
      <main className="content">
        <div className="page-intro">
          <div>
            <h2>Performance & Forecast Analytics</h2>
            <p>Charts are calculated from saved session history.</p>
          </div>
          <span className="config-badge">
            <Database size={16} /> {sessions.length} sessions analysed
          </span>
        </div>
        <section className="summary-strip">
          <SummaryStat
            label="HISTORICAL OUTPUT"
            value={packed}
            detail="all packed pieces"
          />
          <SummaryStat
            label="AVG. COMPLETION"
            value={`${target ? Math.round((packed / target) * 100) : 0}%`}
            detail="across targets"
          />
          <SummaryStat
            label="AVG. SESSION"
            value={average}
            detail="recent 7 sessions"
          />
          <SummaryStat
            label="NEXT FORECAST"
            value={forecast}
            detail="moving average + trend"
          />
        </section>
        <div className="analytics-grid">
          {/* Analytics card 1: packed garment size distribution pie chart */}
          <section className="panel analytics-card">
            <div className="panel-heading">
              <div>
                <h2>Size Distribution</h2>
                <p>Share of packed garments.</p>
              </div>
              <PieChart />
            </div>
            <div className="pie-layout">
              <div
                className="analytics-pie"
                style={{
                  background: packed ? `conic-gradient(${stops})` : "#e8eef5",
                }}
              >
                <div>
                  <strong>{packed}</strong>
                  <span>PIECES</span>
                </div>
              </div>
              <div className="pie-legend">
                {SIZES.map((size) => (
                  <div key={size}>
                    <i style={{ background: palette[size] }} />
                    <b>Size {size}</b>
                    <span>{sizeTotals[size]}</span>
                    <small>
                      {packed
                        ? Math.round((sizeTotals[size] / packed) * 100)
                        : 0}
                      %
                    </small>
                  </div>
                ))}
              </div>
            </div>
          </section>
          {/* Analytics card 2: historical target vs actual bars */}
          <section className="panel analytics-card">
            <div className="panel-heading">
              <div>
                <h2>Target vs Actual</h2>
                <p>Historical production by size.</p>
              </div>
              <BarChart3 />
            </div>
            <div className="analytics-bars">
              {SIZES.map((size) => {
                const goal = sessions.reduce(
                    (sum, session) => sum + session.schedule.targets[size],
                    0,
                  ),
                  scale = Math.max(goal, sizeTotals[size], 1);
                return (
                  <div key={size}>
                    <b>{size}</b>
                    <span className="metric-label">Target {goal}</span>
                    <div className="metric-track target">
                      <i style={{ width: `${(goal / scale) * 100}%` }} />
                    </div>
                    <span className="metric-label">
                      Actual {sizeTotals[size]}
                    </span>
                    <div className="metric-track actual">
                      <i
                        style={{
                          width: `${(sizeTotals[size] / scale) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
          {/* Analytics card 3: recent session output trend + next forecast */}
          <section className="panel analytics-card trend-card">
            <div className="panel-heading">
              <div>
                <h2>Session Output Trend</h2>
                <p>
                  Garments packed in each of the last {recent.length || 7}{" "}
                  sessions, and the forecast for the next session.
                </p>
              </div>
              <TrendingUp />
            </div>
            {recent.length ? (
              <>
                <div className="trend-legend" aria-hidden="true">
                  <span>
                    <i className="key-packed" /> Packed in session
                  </span>
                  <span>
                    <i className="key-target" /> Session target
                  </span>
                  <span>
                    <i className="key-average" /> Average ({average} pcs)
                  </span>
                  <span>
                    <i className="key-forecast" /> Next-session forecast
                  </span>
                </div>
                <div className="trend-figure" role="img" aria-label={`Session output trend. ${trendSummary}`}>
                  <div className="trend-y-title">Garments packed (pcs)</div>
                  <div className="trend-body">
                    <div className="trend-plot-row">
                      <div className="trend-y-axis">
                        {trendScale.ticks.map((tick) => (
                          <span key={tick} style={{ bottom: `${pct(tick)}%` }}>
                            {tick}
                          </span>
                        ))}
                      </div>
                      <div className="trend-plot">
                        {trendScale.ticks.map((tick) => (
                          <i
                            key={tick}
                            className={`trend-grid ${tick === 0 ? "baseline" : ""}`}
                            style={{ bottom: `${pct(tick)}%` }}
                          />
                        ))}
                        <i
                          className="trend-average"
                          style={{ bottom: `${pct(average)}%` }}
                        />
                        {recent.map((session, index) => {
                          const value = total(session.packed),
                            goal = total(session.schedule.targets),
                            done = goal ? Math.round((value / goal) * 100) : null;
                          return (
                            <div
                              className="trend-column"
                              key={session.id}
                              title={`Session ${index + 1} - order ${session.orderId}\n${formatDateTime(session.startedAt || session.createdAt)}\nPacked: ${value} pcs${goal ? `\nTarget: ${goal} pcs (${done}% achieved)` : ""}`}
                            >
                              {/* The number sits above the bar or its target
                                  marker, whichever is higher, so they never overlap. */}
                              <span
                                className="trend-value"
                                style={{ bottom: `${pct(Math.max(value, goal))}%` }}
                              >
                                {value}
                              </span>
                              <i
                                className="trend-bar"
                                style={{ height: `${pct(value)}%` }}
                              />
                              {goal > 0 && (
                                <i
                                  className="trend-target"
                                  style={{ bottom: `${pct(goal)}%` }}
                                />
                              )}
                            </div>
                          );
                        })}
                        <div
                          className="trend-column forecast"
                          title={`Next-session forecast: ${forecast} pcs\n(average of the last ${recent.length} sessions, ${average} pcs, plus 6%)`}
                        >
                          <span
                            className="trend-value"
                            style={{ bottom: `${pct(forecast)}%` }}
                          >
                            {forecast}
                          </span>
                          <i
                            className="trend-bar"
                            style={{ height: `${pct(forecast)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                    <div className="trend-label-row">
                      <div className="trend-y-axis-spacer" />
                      <div className="trend-labels">
                        {recent.map((session, index) => (
                          <div key={session.id}>
                            <b>Session {index + 1}</b>
                            <small>
                              {new Date(
                                session.startedAt || session.createdAt,
                              ).toLocaleDateString("en-GB", {
                                day: "2-digit",
                                month: "short",
                              })}
                            </small>
                            <small className="order" title={`Order ${session.orderId}`}>
                              {session.orderId.length > 8
                                ? `…${session.orderId.slice(-6)}`
                                : session.orderId}
                            </small>
                          </div>
                        ))}
                        <div className="forecast">
                          <b>Forecast</b>
                          <small>Next session</small>
                        </div>
                      </div>
                    </div>
                    <div className="trend-x-title">
                      Recent sessions (oldest &rarr; newest)
                    </div>
                  </div>
                </div>
                <p className="trend-note">
                  Forecast = average of these {recent.length} sessions ({average}{" "}
                  pcs) + 6% trend allowance. Hover a bar for order, date and target.
                </p>
              </>
            ) : (
              <p className="chart-empty trend-empty">
                Complete a session to create the trend.
              </p>
            )}
          </section>
          {/* Analytics card 4: current active order outlook */}
          <section className="panel analytics-card prediction-summary-card">
            <div className="panel-heading">
              <div>
                <h2>Current Order Outlook</h2>
                <p>Running-session indicators.</p>
              </div>
              <Gauge />
            </div>
            <div className="outlook-list">
              <div>
                <span>Active order</span>
                <strong>{active?.orderId ?? "No active session"}</strong>
              </div>
              <div>
                <span>Configured target</span>
                <strong>
                  {active ? total(active.schedule.targets) : 0} pcs
                </strong>
              </div>
              <div>
                <span>Saved output</span>
                <strong>{active ? total(active.packed) : 0} pcs</strong>
              </div>
              <div>
                <span>Forecast method</span>
                <strong>Recent-session moving average</strong>
              </div>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}

// -------------------- Downtime Log page --------------------

/** Production interruption events add, summarize and delete page . */
function DowntimePage({
  entries,
  sessions,
  active,
  online,
  add,
  remove,
}: {
  entries: DowntimeEntry[];
  sessions: ProductionSession[];
  active: ProductionSession | null;
  online: boolean;
  add: (entry: DowntimeEntry) => void;
  remove: (id: string) => void;
}) {
  // new downtime event form temporary values.
  const [draft, setDraft] = useState({
    orderId: active?.orderId ?? "",
    date: today(),
    reason: "Machine setup",
    start: "08:00",
    end: "08:10",
    note: "",
  });
  const totalMinutes = entries.reduce((sum, entry) => sum + entry.minutes, 0),
    reasons = entries.reduce<Record<string, number>>(
      (map, entry) => ({
        ...map,
        [entry.reason]: (map[entry.reason] ?? 0) + entry.minutes,
      }),
      {},
    ),
    topReason =
      Object.entries(reasons).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "--";
  const orderIds = Array.from(new Set(sessions.map((s) => s.orderId)));
  
  const submit = () => {
    const duration = minutesBetween(draft.start, draft.end);
    if (!draft.orderId) return toast.error("Select an Order ID");
    if (!duration) return toast.error("End time must be after start time");
    const session = sessions.find((s) => s.orderId === draft.orderId);
    add({
      id: `DT-${Date.now()}`,
      sessionId: session?.id,
      orderId: draft.orderId,
      date: draft.date,
      reason: draft.reason,
      start: draft.start,
      end: draft.end,
      minutes: duration,
      note: draft.note.trim(),
      createdAt: new Date().toISOString(),
    });
    setDraft((current) => ({ ...current, note: "" }));
  };
  return (
    <>
      <Header title="Downtime Log" online={online} />
      <main className="content">
        <div className="page-intro">
          <div>
            <h2>Production Downtime</h2>
            <p>Record interruptions against an Order ID.</p>
          </div>
          <span className="config-badge downtime-badge">
            <TimerReset size={16} /> {totalMinutes} minutes logged
          </span>
        </div>
        <section className="summary-strip">
          <SummaryStat
            label="TOTAL DOWNTIME"
            value={`${totalMinutes} min`}
            detail="all events"
          />
          <SummaryStat
            label="EVENTS"
            value={entries.length}
            detail="interruptions"
          />
          <SummaryStat
            label="AVERAGE"
            value={`${entries.length ? Math.round(totalMinutes / entries.length) : 0} min`}
            detail="per event"
          />
          <SummaryStat
            label="TOP REASON"
            value={topReason}
            detail="largest contributor"
          />
        </section>
        <section className="panel downtime-form">
          <div className="panel-heading">
            <div>
              <h2>Add Downtime Event</h2>
              <p>The event is linked to its production order.</p>
            </div>
          </div>
          <div className="downtime-form-grid">
            <Field label="Order ID">
              <NativeSelect
                className="w-full"
                value={draft.orderId}
                onChange={(e) =>
                  setDraft({ ...draft, orderId: e.target.value })
                }
              >
                <NativeSelectOption value="">Select order</NativeSelectOption>
                {orderIds.map((id) => (
                  <NativeSelectOption key={id} value={id}>
                    {id}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Reason">
              <NativeSelect
                className="w-full"
                value={draft.reason}
                onChange={(e) => setDraft({ ...draft, reason: e.target.value })}
              >
                <NativeSelectOption>Machine setup</NativeSelectOption>
                <NativeSelectOption>Camera / device issue</NativeSelectOption>
                <NativeSelectOption>Material shortage</NativeSelectOption>
                <NativeSelectOption>Quality inspection</NativeSelectOption>
                <NativeSelectOption>Power interruption</NativeSelectOption>
                <NativeSelectOption>Planned maintenance</NativeSelectOption>
                <NativeSelectOption>Other</NativeSelectOption>
              </NativeSelect>
            </Field>
            <Field label="Date">
              <Input
                type="date"
                value={draft.date}
                onChange={(e) => setDraft({ ...draft, date: e.target.value })}
              />
            </Field>
            <Field label="Start">
              <Input
                type="time"
                value={draft.start}
                onChange={(e) => setDraft({ ...draft, start: e.target.value })}
              />
            </Field>
            <Field label="End">
              <Input
                type="time"
                value={draft.end}
                onChange={(e) => setDraft({ ...draft, end: e.target.value })}
              />
            </Field>
            <Field label="Note">
              <Input
                placeholder="Optional note"
                value={draft.note}
                onChange={(e) => setDraft({ ...draft, note: e.target.value })}
              />
            </Field>
            <Button onClick={submit}>
              <Plus /> Add event
            </Button>
          </div>
        </section>
        <section className="panel downtime-table-panel">
          <div className="panel-heading">
            <div>
              <h2>Downtime Events</h2>
              <p>Newest events first.</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>DATE</th>
                  <th>ORDER ID</th>
                  <th>REASON</th>
                  <th>START</th>
                  <th>END</th>
                  <th>DURATION</th>
                  <th>NOTE</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {[...entries]
                  .sort(
                    (a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt),
                  )
                  .map((entry) => (
                    <tr key={entry.id}>
                      <td>{entry.date}</td>
                      <td>
                        <strong>{entry.orderId}</strong>
                      </td>
                      <td>{entry.reason}</td>
                      <td>{entry.start}</td>
                      <td>{entry.end}</td>
                      <td>
                        <b>{entry.minutes} min</b>
                      </td>
                      <td>{entry.note || "--"}</td>
                      <td>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => remove(entry.id)}
                        >
                          <Trash2 />
                        </Button>
                      </td>
                    </tr>
                  ))}
                {!entries.length && (
                  <tr>
                    <td colSpan={8} className="empty-table">
                      No downtime recorded.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </>
  );
}


function SimplePage({
  page,
  online,
}: {
  page: "alerts" | "settings";
  online: boolean;
}) {
  const alerts = page === "alerts";
  return (
    <>
      <Header
        title={alerts ? "Production Alerts" : "System Settings"}
        online={online}
      />
      <main className="content">
        <section className="panel simple-module">
          {alerts ? <Bell /> : <Settings />}
          <div>
            <h2>
              {alerts ? "Operational alerts" : "Device and backend settings"}
            </h2>
            <p>
              {alerts
                ? "Target risk and backend connectivity notifications appear here."
                : "Electron uses the isolated local Size Detection service."}
            </p>
          </div>
          <span className={online ? "module-ok" : "module-warning"}>
            {online ? "System ready" : "Backend offline"}
          </span>
        </section>
      </main>
    </>
  );
}

function makeSessionId() {
  return `SES-${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;
}

// -------------------- Main application controller --------------------


export default function Home({ onExit }: { onExit: () => void }) {
  
  const [page, setPage] = useState<Page>("dashboard");

  
  const [navOpen, setNavOpen] = useState(false);

  
  const [schedule, setSchedule] = useState<Schedule>(() => createInitialSchedule());

  
  const [sessions, setSessions] = useState<ProductionSession[]>([]);

  
  const [active, setActive] = useState<ProductionSession | null>(null);

  
  const [downtime, setDowntime] = useState<DowntimeEntry[]>([]);

  
  const [raw, setRaw] = useState<Counts>(counts());

  
  const [online, setOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  
  const [hydrated, setHydrated] = useState(false);
  const orderSaveErrorShown = useRef(false);

  
  useEffect(() => {
    let cancelled = false;
    const open = () => setNavOpen(true);
    addEventListener("open-nav", open);

    const load = async () => {
      try {
        const downtimeJson = localStorage.getItem(STORE.downtime);
        if (downtimeJson) setDowntime(JSON.parse(downtimeJson));

        const response = await apiGet("/orders");
        const databaseOrders =
          response &&
          typeof response === "object" &&
          "orders" in response &&
          Array.isArray(response.orders)
            ? (response.orders as ProductionSession[])
            : [];
        let loadedOrders = databaseOrders;

        if (!databaseOrders.length) {
          const legacyJson = localStorage.getItem(STORE.legacySessions);
          const legacyActiveJson = localStorage.getItem(STORE.legacyActive);
          const legacyOrders: ProductionSession[] = legacyJson
            ? JSON.parse(legacyJson)
            : [];
          const legacyActive: ProductionSession | null = legacyActiveJson
            ? JSON.parse(legacyActiveJson)
            : null;
          if (legacyActive) {
            const index = legacyOrders.findIndex(
              (item) => item.id === legacyActive.id,
            );
            if (index >= 0) legacyOrders[index] = legacyActive;
            else legacyOrders.push(legacyActive);
          }

          const migrationOrder = [
            ...legacyOrders.filter((item) => item.status !== "active"),
            ...legacyOrders.filter((item) => item.status === "active"),
          ];
          const migrated: ProductionSession[] = [];
          for (const item of migrationOrder) {
            try {
              migrated.push(await persistOrder(item));
            } catch (error) {
              console.error("Legacy order migration failed:", error);
            }
          }
          if (migrated.length) {
            loadedOrders = migrated;
            toast.success(`${migrated.length} existing order(s) moved to SQLite`);
          }
        }

        if (cancelled) return;
        const running = loadedOrders.find((item) => item.status === "active") ?? null;
        setSessions(loadedOrders);
        setActive(running);
        setSchedule(running?.schedule ?? createInitialSchedule());
        localStorage.removeItem(STORE.legacySchedule);
        localStorage.removeItem(STORE.legacySessions);
        localStorage.removeItem(STORE.legacyActive);
      } catch (error) {
        console.error("Order database load failed:", error);
        toast.error("Saved orders could not be loaded from the database");
        setSchedule(createInitialSchedule());
      } finally {
        if (!cancelled) setHydrated(true);
      }
    };
    void load();
    return () => {
      cancelled = true;
      removeEventListener("open-nav", open);
    };
  }, []);
  
  useEffect(() => {
    if (hydrated)
      localStorage.setItem(STORE.downtime, JSON.stringify(downtime));
  }, [hydrated, downtime]);
  
  const refresh = useCallback(async () => {
    try {
      // Connectivity is decided only by /health. A temporary /counts problem
      // must not incorrectly label a healthy backend as offline.
      await apiGet("/health");
      setOnline(true);
      setLastUpdated(new Date());

      try {
        const countResponse = await apiGet("/counts");
        setRaw(normalizeCounts(countResponse, schedule.garmentType));
      } catch (countError) {
        console.error("Backend /counts request failed:", countError);
      }
    } catch (healthError) {
      console.error("Backend /health request failed:", healthError);
      setOnline(false);
    } finally {
      setLoading(false);
    }
  }, [schedule.garmentType]);

  useEffect(() => {
    const initial = setTimeout(refresh, 0),
      timer = setInterval(refresh, 1500);
    return () => {
      clearTimeout(initial);
      clearInterval(timer);
    };
  }, [refresh]);
  
  const production = useMemo(
    () => liveSessionCounts(active, raw),
    [active, raw],
  );

  useEffect(() => {
    if (!hydrated || !active || sameCounts(active.packed, production)) return;
    const updated = { ...active, packed: counts(production) };
    setActive(updated);
    setSessions((current) =>
      current.map((session) => (session.id === updated.id ? updated : session)),
    );
    void persistOrder(updated)
      .then(() => {
        orderSaveErrorShown.current = false;
      })
      .catch((error) => {
        console.error("Live order database update failed:", error);
        if (!orderSaveErrorShown.current) {
          orderSaveErrorShown.current = true;
          toast.error("Live order progress could not be saved to the database");
        }
      });
  }, [active, hydrated, production]);
 
  const saveSchedule = async (next: Schedule): Promise<void> => {
    if (active && active.orderId !== next.orderId) {
      toast.error(`End ${active.orderId} before starting another order`);
      return;
    }
    if (
      !active &&
      sessions.some(
        (session) => session.orderId.toLowerCase() === next.orderId.toLowerCase(),
      )
    ) {
      toast.error(`Order ID ${next.orderId} already exists`);
      return;
    }

    try {
      if (active) {
        const stored = await persistOrder({
          ...active,
          orderId: next.orderId,
          garmentType: next.garmentType,
          schedule: next,
        });
        setSchedule(stored.schedule);
        setActive(stored);
        setSessions((current) =>
          current.map((session) =>
            session.id === stored.id ? stored : session,
          ),
        );
        toast.success("Active session updated in SQLite");
      } else {
        const reset = await apiMutation<Record<string, unknown>>(
          "POST",
          "/counts/reset",
        );
        const freshCounts = normalizeCounts(reset, next.garmentType);
        setRaw(freshCounts);
        const now = new Date().toISOString();
        const session: ProductionSession = {
          id: makeSessionId(),
          orderId: next.orderId,
          garmentType: next.garmentType,
          status: "active",
          schedule: next,
          packed: counts(),
          carriedCounts: counts(),
          baselineCounts: freshCounts,
          createdAt: now,
          startedAt: now,
          activeStartedAt: now,
          accumulatedMinutes: 0,
          measurementSessionId:
            typeof reset.session_id === "number" ? reset.session_id : undefined,
        };
        const stored = await persistOrder(session);
        setSchedule(stored.schedule);
        setActive(stored);
        setSessions((current) => [stored, ...current]);
        toast.success(`${stored.orderId} started with fresh counts`);
      }
      setPage("dashboard");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Order could not be saved";
      toast.error(message);
    }
  };
  
  const endSession = async () => {
    if (!active) return;
    const now = new Date().toISOString(),
      packed = counts(production),
      hasTarget = total(active.schedule.targets) > 0;
    const complete =
      hasTarget &&
      SIZES.every(
        (size) =>
          !active.schedule.targets[size] ||
          packed[size] >= active.schedule.targets[size],
      );
    const ended: ProductionSession = {
      ...active,
      status: complete ? "completed" : "paused",
      packed,
      carriedCounts: packed,
      endedAt: now,
      completedAt: complete ? now : undefined,
      accumulatedMinutes:
        active.accumulatedMinutes + elapsedMinutes(active.activeStartedAt, now),
    };
    try {
      const stored = await persistOrder(ended);
      setSessions((current) =>
        current.map((session) =>
          session.id === stored.id ? stored : session,
        ),
      );
      setActive(null);
      setSchedule(createInitialSchedule());
      setPage("history");
      toast.success(
        complete
          ? `${stored.orderId} completed`
          : `${stored.orderId} paused; Start it from History to continue`,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Order could not be ended");
    }
  };
  
  const resume = async (session: ProductionSession): Promise<void> => {
    if (active) {
      toast.error(`End active session ${active.orderId} first`);
      return;
    }
    try {
      const reset = await apiMutation<Record<string, unknown>>(
        "POST",
        "/counts/reset",
      );
      const freshCounts = normalizeCounts(reset, session.garmentType);
      setRaw(freshCounts);
      const now = new Date().toISOString();
      const resumed: ProductionSession = {
        ...session,
        status: "active",
        baselineCounts: freshCounts,
        carriedCounts: counts(session.packed),
        activeStartedAt: now,
        endedAt: undefined,
        measurementSessionId:
          typeof reset.session_id === "number"
            ? reset.session_id
            : session.measurementSessionId,
      };
      const stored = await persistOrder(resumed);
      setSchedule(stored.schedule);
      setActive(stored);
      setSessions((current) =>
        current.map((item) => (item.id === stored.id ? stored : item)),
      );
      setPage("dashboard");
      toast.success(
        `${stored.orderId} resumed from ${total(stored.packed)} pieces`,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Order could not be resumed");
    }
  };
  const removeOrder = async (session: ProductionSession): Promise<void> => {
    if (session.status === "active") {
      toast.error("End the active order before deleting it");
      return;
    }
    if (!window.confirm(`Delete ${session.orderId} permanently from the database?`)) {
      return;
    }
    try {
      await apiMutation("DELETE", `/orders/${encodeURIComponent(session.id)}`);
      setSessions((current) => current.filter((item) => item.id !== session.id));
      setDowntime((current) =>
        current.filter(
          (entry) =>
            entry.sessionId !== session.id && entry.orderId !== session.orderId,
        ),
      );
      toast.success(`${session.orderId} deleted from SQLite`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Order could not be deleted");
    }
  };
  
  return (
    <div className="garment-size-module app-shell">
      <Sidebar
        page={page}
        setPage={(nextPage) => {
          if (nextPage === "schedule" && !active) {
            setSchedule(createInitialSchedule());
          }
          setPage(nextPage);
        }}
        open={navOpen}
        close={() => setNavOpen(false)}
        onExit={onExit}
      />
      <div className="main-shell">
        {/* Main dashboard */}
        {page === "dashboard" && (
          <Dashboard
            schedule={schedule}
            production={active ? production : counts()}
            online={online}
            loading={loading}
            lastUpdated={lastUpdated}
            active={active}
            edit={() => {
              if (!active) setSchedule(createInitialSchedule());
              setPage("schedule");
            }}
            end={endSession}
          />
        )}

        {/* Order target and schedule configuration */}
        {page === "schedule" && (
          <TargetSchedule
            value={schedule}
            online={online}
            active={active}
            onSave={saveSchedule}
          />
        )}

        {/* Saved production sessions */}
        {page === "history" && (
          <HistoryPage
            sessions={sessions}
            online={online}
            active={active}
            resume={resume}
            remove={removeOrder}
          />
        )}

        {/* Historical charts and forecast */}
        {page === "analytics" && (
          <AnalyticsPage sessions={sessions} active={active} online={online} />
        )}

        {/* Downtime event form සහ table */}
        {page === "downtime" && (
          <DowntimePage
            entries={downtime}
            sessions={sessions}
            active={active}
            online={online}
            add={(entry) => {
              setDowntime((current) => [...current, entry]);
              toast.success("Downtime saved");
            }}
            remove={(id) => {
              setDowntime((current) =>
                current.filter((entry) => entry.id !== id),
              );
              toast.success("Downtime removed");
            }}
          />
        )}

        {/* Alert / Settings placeholder pages */}
        {(page === "alerts" || page === "settings") && (
          <SimplePage page={page} online={online} />
        )}
      </div>
      <Toaster position="top-right" richColors />
    </div>
  );
}
