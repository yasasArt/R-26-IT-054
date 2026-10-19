import { useEffect, useRef, useState } from "react";
import { ScanLine, Camera, CheckCircle2, AlertCircle, VideoOff, RefreshCw, Hand, Power, Loader2 } from "lucide-react";
import { FabricSwatch, colorHex } from "./FabricSwatch";
import {
  CATEGORY_LABEL,
  CV_API_BASE,
  fetchPipelineStatus,
  GarmentCategory,
  PipelineStatus,
  recalibrateZone,
  startCamera,
} from "../lib/api";

export interface ScanResult {
  style_name: string;
  confidence: number;
  main_color: string;
  other_colors?: string;
  image_base64?: string;
}

const STATUS_LABEL: Record<string, string> = {
  STARTING: "Starting...",
  CALIBRATING: "Learning empty table",
  EMPTY: "Waiting for garment",
  DETECTING: "Garment detected",
  ANALYSING: "Analysing style",
  UNCERTAIN: "Style unclear",
  CAPTURED: "Captured",
  WAITING_REMOVAL: "Captured - remove garment",
};

const STATUS_CLASS: Record<string, string> = {
  STARTING: "text-ink-soft bg-line-soft",
  CALIBRATING: "text-ink-secondary bg-line-soft",
  EMPTY: "text-ink-soft bg-line-soft",
  DETECTING: "text-warning bg-warning-soft",
  ANALYSING: "text-accent bg-accent-soft",
  UNCERTAIN: "text-warning bg-warning-soft",
  CAPTURED: "text-success bg-success-soft",
  WAITING_REMOVAL: "text-violet bg-violet-soft",
};

function styleLabel(style: string | null | undefined): string {
  if (!style) return "";
  return CATEGORY_LABEL[style as GarmentCategory]?.replace(/s$/, "") ?? style;
}

export default function LiveCameraPanel({ scan }: { scan: ScanResult | null }) {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [feedKey, setFeedKey] = useState(0);
  // The camera's real resolution (e.g. 640x480, a 4:3 frame) doesn't match
  // a generic 16:9 video box - forcing one via a fixed aspect-video
  // container used to crop the top/bottom of the actual frame, which is
  // exactly where the backend's ROI "FOLDING ZONE" rectangle extends to
  // (compute_roi draws it up to 95% of frame height), so part of the
  // detection box was getting cropped out of view. Measuring the actual
  // streamed frame once it loads and sizing the container to match means
  // the full frame - and the full box - is always visible, whatever
  // camera is active.
  const [videoAspect, setVideoAspect] = useState<number | null>(null);
  const wasCameraActive = useRef(false);
  const [recalibrating, setRecalibrating] = useState(false);
  // Stream problems are tracked in React state (not by editing the DOM), so
  // a temporary failure - e.g. the vision service restarting - shows a
  // message and then retries by itself instead of hiding the feed for good.
  const [feedError, setFeedError] = useState(false);
  const [startingCamera, setStartingCamera] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const autoStartAttempted = useRef(false);
  const retryTimer = useRef<number | undefined>(undefined);

  const turnCameraOn = async () => {
    setStartingCamera(true);
    setCameraError("");
    const result = await startCamera();
    if (!result.success) {
      setCameraError(result.error || "The saved camera could not be opened. Choose a camera in Device Setup.");
    } else {
      setFeedError(false);
      setFeedKey((k) => k + 1);
    }
    setStartingCamera(false);
  };

  const handleFeedError = () => {
    setFeedError(true);
    window.clearTimeout(retryTimer.current);
    retryTimer.current = window.setTimeout(() => {
      setFeedError(false);
      setFeedKey((k) => k + 1);
    }, 2000);
  };

  useEffect(() => () => window.clearTimeout(retryTimer.current), []);

  const handleRecalibrate = async () => {
    setRecalibrating(true);
    await recalibrateZone();
    // The pipeline reports CALIBRATING until it has seen ~1 s of stillness;
    // the status poll below shows when learning has finished.
    setTimeout(() => setRecalibrating(false), 1500);
  };

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      const result = await fetchPipelineStatus();
      if (cancelled) return;
      setStatus(result);

      const isActive = result?.camera_active ?? false;

      // The desktop app releases the camera whenever the operator switches to
      // another feature. Coming back to the Live Dashboard turns it on again
      // automatically - unless it was switched off on purpose (Downtime Log).
      if (result && !isActive && result.camera_stopped_by !== "operator" && !autoStartAttempted.current) {
        autoStartAttempted.current = true;
        void turnCameraOn();
      }

      if (isActive && !wasCameraActive.current) {
        // Camera just came back on (Device Setup switched it, or it was
        // reopened after being stopped) - force a fresh <img> mount instead
        // of possibly resuming a stale/closed stream connection. The newly
        // active device may have a different native resolution than
        // whichever camera was active before, so drop the measured aspect
        // ratio and let it be re-measured from this device's real frames.
        setFeedKey((k) => k + 1);
        setVideoAspect(null);
      }
      wasCameraActive.current = isActive;
    };

    poll();
    const interval = setInterval(poll, 700);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const statusKey = status?.state || "STARTING";
  const cameraActive = status?.camera_active ?? false;
  const progress = status?.progress && status.progress[1] > 0 ? status.progress[0] / status.progress[1] : null;
  const showsStyle = statusKey === "ANALYSING" || statusKey === "UNCERTAIN" || statusKey === "CAPTURED" || statusKey === "WAITING_REMOVAL";

  return (
    <div className="bg-surface border border-line rounded-xl flex flex-col overflow-hidden shadow-sm shrink-0">
      <div className="px-5 py-4 border-b border-line flex justify-between items-center bg-surface-muted">
        <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase flex items-center gap-2">
          <ScanLine size={14} className="text-accent" />
          Live AI Recognition Floor
        </h3>
        <div className="flex items-center gap-2">
          <span
            className={`font-mono text-[10px] px-2 py-1 rounded-full flex items-center gap-1 ${STATUS_CLASS[statusKey]}`}
          >
            {statusKey === "UNCERTAIN" ? <AlertCircle size={12} /> : null}
            {STATUS_LABEL[statusKey] || statusKey}
            {showsStyle && status?.detected_style ? ` · ${styleLabel(status.detected_style)}` : ""}
            {showsStyle && status?.confidence != null ? ` (${Math.round(status.confidence)}%)` : ""}
          </span>
          {scan && (
            <span className="font-mono text-[10px] text-success bg-success-soft border border-success/20 px-2 py-1 rounded-full flex items-center gap-1">
              <CheckCircle2 size={12} /> {scan.confidence}% CONF
            </span>
          )}
        </div>
      </div>

      {/* Operator guidance from the vision service: what the detector is
          waiting for right now (hands out of the zone, garment settling,
          voting progress) and a control to re-learn the empty table after
          lighting or camera position changes. */}
      <div className="px-5 py-2.5 border-b border-line flex items-center gap-3 bg-surface">
        {statusKey === "DETECTING" && status?.detail?.toLowerCase().includes("hand") ? (
          <Hand size={13} className="text-warning flex-shrink-0" />
        ) : (
          <ScanLine size={13} className="text-ink-soft flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-[12px] text-ink-secondary truncate">
            {cameraActive ? status?.detail || "Waiting for the vision service..." : "Camera is turned off."}
          </div>
          {progress !== null && (statusKey === "ANALYSING" || statusKey === "CALIBRATING") && (
            <div className="h-1 w-full bg-line-soft rounded-full mt-1.5 overflow-hidden">
              <div className="h-full bg-accent transition-all duration-300" style={{ width: `${Math.min(100, progress * 100)}%` }} />
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={handleRecalibrate}
          disabled={!cameraActive || recalibrating}
          title="Clear the folding zone, then press to re-learn the empty table (after a lighting or camera change)."
          className="flex items-center gap-1.5 px-2.5 py-1.5 border border-line rounded-md text-[11px] font-medium text-ink-secondary hover:text-ink hover:bg-surface-muted disabled:opacity-50 transition-colors flex-shrink-0"
        >
          <RefreshCw size={12} className={recalibrating || statusKey === "CALIBRATING" ? "animate-spin" : ""} />
          Re-learn empty table
        </button>
      </div>

      {/* xl:items-start: without it, flex's default stretch makes the video
          box match the height of its sibling (Best Frame Capture), which
          fights the aspect-ratio set on the video box below and reintroduces
          letterboxing/mismatch instead of a clean fit to the real frame. */}
      <div className="flex flex-col xl:flex-row divide-y xl:divide-y-0 xl:divide-x divide-line xl:items-start">
        <div
          className="relative xl:w-[58%] bg-sidebar overflow-hidden flex items-center justify-center"
          style={{ aspectRatio: videoAspect ?? 16 / 9 }}
        >
          {cameraActive ? (
            <img
              key={feedKey}
              src={`${CV_API_BASE}/video_feed?stream=${feedKey}`}
              alt="AI Live Feed"
              className="w-full h-full object-contain relative z-0"
              onLoad={(e) => {
                setFeedError(false);
                const { naturalWidth, naturalHeight } = e.currentTarget;
                if (naturalWidth > 0 && naturalHeight > 0) {
                  setVideoAspect(naturalWidth / naturalHeight);
                }
              }}
              onError={handleFeedError}
            />
          ) : (
            <div className="flex flex-col items-center justify-center gap-3 text-nav-text font-mono text-xs text-center px-6">
              {startingCamera ? (
                <>
                  <Loader2 size={22} className="opacity-70 animate-spin" />
                  Turning the camera on...
                </>
              ) : (
                <>
                  <VideoOff size={22} className="opacity-60" />
                  {status?.camera_stopped_by === "operator"
                    ? "Camera was turned off from the Downtime Log."
                    : status
                    ? "Camera is currently turned off."
                    : "Connecting to the vision service..."}
                  {status && (
                    <button
                      type="button"
                      onClick={() => void turnCameraOn()}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white/10 hover:bg-white/15 text-nav-text-active font-sans text-[12px] font-medium transition-colors"
                    >
                      <Power size={13} /> Turn camera on
                    </button>
                  )}
                  {cameraError && <span className="text-[11px] text-error max-w-[320px] font-sans">{cameraError}</span>}
                </>
              )}
            </div>
          )}

          {cameraActive && feedError && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-nav-text font-mono text-xs z-20 bg-sidebar text-center px-6">
              <Loader2 size={20} className="opacity-70 animate-spin" />
              Live feed interrupted - reconnecting...
            </div>
          )}
        </div>

        <div className="flex-1 bg-surface flex flex-col p-5">
          <h4 className="text-[10px] uppercase font-bold tracking-widest text-ink-soft mb-1 flex items-center gap-2">
            <Camera size={12} /> Best Frame Capture
          </h4>
          <p className="text-ink-soft text-[11px] mb-4">The exact frame used for style &amp; colour analysis.</p>

          {scan ? (
            <div className="flex flex-col gap-4">
              {/* The raw captured frame, exactly as the camera saw it - no
                  masking/segmentation artifacts are ever shown here, only
                  used internally (backend) to measure colour. object-contain
                  (not object-cover) so a tall/narrow capture like trousers
                  is never cropped out of view. */}
              <div className="w-full aspect-square bg-surface-muted border border-line rounded-lg overflow-hidden relative">
                {scan.image_base64 ? (
                  <img
                    src={`data:image/jpeg;base64,${scan.image_base64}`}
                    alt="Captured garment frame"
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center font-mono text-ink-soft text-3xl font-bold uppercase">
                    {scan.style_name}
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-1">
                <div className="text-ink-soft text-[10px] uppercase tracking-widest font-bold">Garment Style</div>
                <div className="font-mono text-xl font-bold text-ink uppercase tracking-wide">{styleLabel(scan.style_name)}</div>
              </div>

              <div className="flex flex-col gap-1.5">
                <div className="text-ink-soft text-[10px] uppercase tracking-widest font-bold">Main Color</div>
                <div className="flex items-center gap-2.5">
                  <div
                    className="w-9 h-9 rounded-full shadow-sm flex-shrink-0"
                    style={{
                      backgroundColor: colorHex(scan.main_color),
                      border: ["white", "beige", "yellow"].includes(scan.main_color.toLowerCase().trim())
                        ? "1px solid var(--color-line)"
                        : "1px solid rgba(0,0,0,0.06)",
                    }}
                  />
                  <span className="font-mono text-lg font-bold text-ink uppercase tracking-wide">{scan.main_color}</span>
                </div>
              </div>

              {(() => {
                const subColors = scan.other_colors
                  ?.split(",")
                  .map((c) => c.trim())
                  .filter(Boolean) ?? [];
                // Dynamically adapts: with no sub-colors detected, only
                // Garment Style and Main Color above are shown - no empty
                // "Sub Colors" section left dangling.
                return subColors.length > 0 ? (
                  <div className="flex flex-col gap-1.5">
                    <div className="text-ink-soft text-[10px] uppercase tracking-widest font-bold">Sub Colors</div>
                    <div className="flex flex-wrap gap-2">
                      {subColors.map((c) => (
                        <FabricSwatch key={c} label={c} hex={colorHex(c)} />
                      ))}
                    </div>
                  </div>
                ) : null;
              })()}
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-ink-soft font-mono text-xs gap-3 py-10">
              <div className="w-16 h-16 border border-dashed border-line rounded-full flex items-center justify-center">
                <Camera size={18} className="opacity-50" />
              </div>
              Waiting for garment...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
