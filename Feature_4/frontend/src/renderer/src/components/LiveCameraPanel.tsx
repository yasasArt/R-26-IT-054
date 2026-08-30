import { useEffect, useRef, useState } from "react";
import { ScanLine, Camera, CheckCircle2, AlertCircle, VideoOff } from "lucide-react";
import { FabricSwatch, colorHex } from "./FabricSwatch";
import { CV_API_BASE, fetchPipelineStatus, PipelineStatus } from "../lib/api";

export interface ScanResult {
  style_name: string;
  confidence: number;
  main_color: string;
  other_colors?: string;
  image_base64?: string;
}

const STATUS_LABEL: Record<string, string> = {
  STARTING: "Starting...",
  EMPTY: "Waiting for item",
  UNCERTAIN: "Uncertain - not a garment",
  DETECTING: "Detecting...",
  CAPTURED: "Captured",
  WAITING_REMOVAL: "Please remove item",
};

const STATUS_CLASS: Record<string, string> = {
  STARTING: "text-ink-soft bg-line-soft",
  EMPTY: "text-ink-soft bg-line-soft",
  UNCERTAIN: "text-warning bg-warning-soft",
  DETECTING: "text-accent bg-accent-soft",
  CAPTURED: "text-success bg-success-soft",
  WAITING_REMOVAL: "text-violet bg-violet-soft",
};

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

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      const result = await fetchPipelineStatus();
      if (cancelled) return;
      setStatus(result);

      const isActive = result?.camera_active ?? false;
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

  return (
    <div className="bg-surface border border-line rounded-xl flex flex-col overflow-hidden shadow-sm">
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
            {status?.confidence != null ? ` (${status.confidence}%)` : ""}
          </span>
          {scan && (
            <span className="font-mono text-[10px] text-success bg-success-soft border border-success/20 px-2 py-1 rounded-full flex items-center gap-1">
              <CheckCircle2 size={12} /> {scan.confidence}% CONF
            </span>
          )}
        </div>
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
              src={`${CV_API_BASE}/video_feed`}
              alt="AI Live Feed"
              className="w-full h-full object-contain relative z-0"
              onLoad={(e) => {
                const { naturalWidth, naturalHeight } = e.currentTarget;
                if (naturalWidth > 0 && naturalHeight > 0) {
                  setVideoAspect(naturalWidth / naturalHeight);
                }
              }}
              onError={(e) => {
                e.currentTarget.style.display = "none";
                e.currentTarget.nextElementSibling?.classList.remove("hidden");
              }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 text-nav-text font-mono text-xs text-center px-6">
              <VideoOff size={22} className="opacity-60" />
              Camera is currently turned off.
            </div>
          )}

          <div className="hidden absolute inset-0 flex flex-col items-center justify-center gap-2 text-nav-text font-mono text-xs z-20 bg-sidebar text-center px-6">
            AI Camera Feed Offline... Make sure the Python capture pipeline is running.
          </div>
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
                <div className="font-mono text-xl font-bold text-ink uppercase tracking-wide">{scan.style_name}</div>
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
