// components/dashboard/quality/CalibrationStatusCard.tsx
"use client";
import { useQualityStore } from "@/store/qualityStore";
import { cn } from "@/lib/utils";

export function CalibrationStatusCard() {
  const { calibration } = useQualityStore();
  const isCalibrated = calibration.status === "calibrated";
  const calColor =
    calibration.status === "calibrated"   ? "#22C55E"
    : calibration.status === "uncalibrated" ? "#EF4444"
    : "#FACC15";

  const lastTime = calibration.lastCalibratedAt
    ? new Date(calibration.lastCalibratedAt).toLocaleTimeString([], {
        hour: "2-digit", minute: "2-digit",
      })
    : "—";

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{
        background: "#1A2536",
        border: `1px solid ${isCalibrated ? "#243044" : "rgba(239,68,68,0.3)"}`,
        borderRadius: 12,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 shrink-0"
        style={{ height: 48, background: "#131B26", borderBottom: "1px solid #243044" }}
      >
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
          Calibration Status
        </span>
        <div
          className={cn("rounded-full shrink-0", isCalibrated && "animate-pulse-slow")}
          style={{ width: 7, height: 7, background: calColor, boxShadow: `0 0 6px ${calColor}` }}
        />
      </div>

      {/* Body */}
      <div style={{ padding: "16px 18px", flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Status badge */}
        <div
          className="flex items-center gap-2.5 rounded-lg"
          style={{
            padding: "11px 14px",
            background: isCalibrated ? "rgba(34,197,94,0.07)" : "rgba(239,68,68,0.07)",
            border: `1px solid ${isCalibrated ? "rgba(34,197,94,0.22)" : "rgba(239,68,68,0.22)"}`,
          }}
        >
          <div
            className={cn("rounded-full shrink-0", isCalibrated && "animate-pulse-slow")}
            style={{ width: 7, height: 7, background: calColor, boxShadow: `0 0 5px ${calColor}` }}
          />
          <div
            className="font-mono font-bold uppercase"
            style={{ fontSize: 12, color: calColor, letterSpacing: "0.06em" }}
          >
            {calibration.status}
          </div>
        </div>

        {/* Specs grid */}
        <div className="grid grid-cols-2 gap-2">
          {[
            { l: "px/cm Ratio",      v: String(calibration.pixelPerCmRatio)     },
            { l: "Reference Obj.",   v: `${calibration.referenceObjectSizeCm} cm` },
            { l: "Camera",           v: calibration.cameraId                     },
            { l: "Last Calibrated",  v: lastTime                                  },
          ].map(({ l, v }) => (
            <div key={l} style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 7, padding: "11px 13px" }}>
              <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 5 }}>
                {l}
              </div>
              <div className="font-mono text-text-primary" style={{ fontSize: 11 }}>{v}</div>
            </div>
          ))}
        </div>

        {/* Feature note */}
        <div
          className="text-center rounded font-mono text-dim"
          style={{
            padding: "7px 12px", fontSize: 9,
            background: "#0B1017", border: "1px solid #243044", borderRadius: 7,
          }}
        >
          Feature 4 · Pixel-to-centimetre calibration
        </div>
      </div>
    </div>
  );
}