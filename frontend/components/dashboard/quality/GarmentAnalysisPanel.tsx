// components/dashboard/quality/GarmentAnalysisPanel.tsx
"use client";
import { useState, useEffect, useRef } from "react";
import { useQualityStore } from "@/store/qualityStore";
import { cn } from "@/lib/utils";
import { format } from "date-fns";
import type { QualityDecision } from "@/lib/types";

const D_COLOR: Record<QualityDecision, string> = {
  PASS:     "#22C55E",
  REWORK:   "#FACC15",
  MISMATCH: "#EF4444",
};

const D_BG: Record<QualityDecision, string> = {
  PASS:     "rgba(34,197,94,0.12)",
  REWORK:   "rgba(250,204,21,0.12)",
  MISMATCH: "rgba(239,68,68,0.12)",
};

export function GarmentAnalysisPanel() {
  const { cameraStatus, currentGarment, isAnalysing, inspectionLog, calibration } = useQualityStore();

  const [scanPct, setScanPct]   = useState(0);
  const [tickStr, setTickStr]   = useState("");
  const rafRef   = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  const isLive      = cameraStatus === "live";
  const total       = inspectionLog.length;
  const decision    = currentGarment?.decision ?? null;
  const decColor    = decision ? D_COLOR[decision] : "#3A4A5C";
  const decBg       = decision ? D_BG[decision]    : "transparent";

  // Scan line rAF while analysing
  useEffect(() => {
  if (!isAnalysing) {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    startRef.current = null;
    return;
  }
  const tick = (ts: number) => {
    if (!startRef.current) startRef.current = ts;
    setScanPct(((ts - startRef.current) / 1600) % 1 * 100);
    rafRef.current = requestAnimationFrame(tick);
  };
  rafRef.current = requestAnimationFrame(tick);
  return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
}, [isAnalysing]);

  // Clock overlay
  useEffect(() => {
    const id = setInterval(() => setTickStr(format(new Date(), "HH:mm:ss")), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}
    >
      {/* ── Header ── */}
      <div
        className="flex items-center justify-between px-5 shrink-0"
        style={{ height: 58, background: "#131B26", borderBottom: "1px solid #243044" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="flex items-center justify-center shrink-0"
            style={{
              width: 30, height: 30, borderRadius: 8,
              background: isLive ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
              border: `1px solid ${isLive ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)"}`,
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
              stroke={isLive ? "#22C55E" : "#EF4444"}
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 7l-7 5 7 5V7z"/>
              <rect x="1" y="5" width="15" height="14" rx="2"/>
            </svg>
          </div>
          <div>
            <div className="font-display font-semibold text-text-primary" style={{ fontSize: 13 }}>
              Camera Feed · Quality Inspection
            </div>
            <div className="font-mono text-text-muted" style={{ fontSize: 9 }}>
              Logitech C922 · cam-0 · Fixed mount · 18.4 px/cm
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isAnalysing && (
            <div
              className="flex items-center gap-1.5 animate-fade-in"
              style={{
                padding: "4px 10px", borderRadius: 6,
                background: "rgba(59,130,246,0.12)",
                border: "1px solid rgba(59,130,246,0.3)",
              }}
            >
              <div
                className="rounded-full animate-pulse-slow"
                style={{ width: 5, height: 5, background: "#3B82F6", boxShadow: "0 0 5px #3B82F6" }}
              />
              <span className="font-mono font-semibold" style={{ fontSize: 9, color: "#3B82F6", letterSpacing: "0.08em" }}>
                ANALYSING
              </span>
            </div>
          )}
          <div className="flex items-center gap-2">
            <div
              className={cn("rounded-full shrink-0", isLive && "animate-pulse-slow")}
              style={{
                width: 7, height: 7,
                background: isLive ? "#22C55E" : "#EF4444",
                boxShadow: isLive ? "0 0 7px #22C55E" : "0 0 7px #EF4444",
              }}
            />
            <span className="font-mono font-medium" style={{ fontSize: 11, color: isLive ? "#22C55E" : "#EF4444" }}>
              {isLive ? "Live" : "Offline"}
            </span>
          </div>
        </div>
      </div>

      {/* ── Camera view ── */}
      <div
        className="relative overflow-hidden"
        style={{ flex: 1, minHeight: 260, background: "#060A0F" }}
      >
        {/* CRT texture */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,100,255,0.008) 2px, rgba(0,100,255,0.008) 3px)",
          }}
        />
        {/* Dot grid */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(circle, rgba(59,130,246,0.055) 1px, transparent 1px)",
            backgroundSize: "30px 30px",
          }}
        />

        {/* Moving scan line */}
        {isAnalysing && (
          <div
            className="absolute left-0 right-0 pointer-events-none z-10"
            style={{
              height: 2, top: `${scanPct}%`,
              background:
                "linear-gradient(90deg, transparent, rgba(59,130,246,0.55) 25%, rgba(59,130,246,0.85) 50%, rgba(59,130,246,0.55) 75%, transparent)",
              boxShadow: "0 0 14px rgba(59,130,246,0.65)",
            }}
          />
        )}

        {/* Inspection table frame */}
        <div
          className="absolute"
          style={{
            left: "50%", top: "50%", transform: "translate(-50%, -50%)",
            width: 230, height: 210,
          }}
        >
          {/* Outer ROI border */}
          <div
            className="absolute inset-0 transition-all duration-300"
            style={{
              border: `1px dashed ${isAnalysing
                ? "rgba(59,130,246,0.4)"
                : currentGarment
                ? `${decColor}60`
                : "rgba(255,255,255,0.07)"}`,
              borderRadius: 6,
            }}
          >
            <span
              className="absolute font-mono whitespace-nowrap transition-colors duration-300"
              style={{
                top: -14, left: "50%", transform: "translateX(-50%)",
                fontSize: 7, letterSpacing: "0.1em",
                color: isAnalysing
                  ? "rgba(59,130,246,0.55)"
                  : currentGarment ? `${decColor}95` : "rgba(255,255,255,0.14)",
              }}
            >
              INSPECTION TABLE
            </span>
          </div>

          {/* Garment bounding box — shown after analysis */}
          {currentGarment && !isAnalysing && (
            <div
              className="absolute animate-fade-in"
              style={{
                inset: 16,
                border: `2px solid ${decColor}`,
                borderRadius: 4,
                background: decBg,
                boxShadow: `0 0 20px ${decColor}30`,
              }}
            >
              {/* Decision label on box */}
              <div
                className="absolute font-mono font-bold"
                style={{
                  top: -1, left: -1,
                  background: decColor, padding: "2px 8px",
                  borderRadius: "4px 4px 4px 0",
                  fontSize: 8, letterSpacing: "0.06em", color: "#000",
                }}
              >
                {decision} · {(currentGarment.overallConfidence * 100).toFixed(0)}%
              </div>

              {/* Garment silhouette */}
              <div className="absolute inset-4 flex items-center justify-center">
                <svg width="54" height="68" viewBox="0 0 24 24"
                  fill={`${decColor}20`} stroke={`${decColor}55`} strokeWidth="0.8">
                  <path d="M20.38 3.46L16 2a4 4 0 01-8 0L3.62 3.46a2 2 0 00-1.34 2.23l.58 3.57a1 1 0 00.99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 002-2V10h2.15a1 1 0 00.99-.84l.58-3.57a2 2 0 00-1.34-2.23z"/>
                </svg>
              </div>

              {/* Width measurement line */}
              <div
                className="absolute flex items-center justify-center"
                style={{ top: "14%", left: 8, right: 8, height: 1, background: "rgba(250,204,21,0.55)" }}
              >
                <span
                  className="absolute font-mono"
                  style={{ fontSize: 7, color: "#FACC15", background: "#060A0F", padding: "0 3px" }}
                >
                  {currentGarment.sizeMeasurement.widthCm.toFixed(1)}cm
                </span>
              </div>

              {/* Height measurement line */}
              <div
                className="absolute"
                style={{ left: "12%", top: 8, bottom: 8, width: 1, background: "rgba(59,130,246,0.55)" }}
              />
            </div>
          )}

          {/* Waiting state */}
          {!currentGarment && !isAnalysing && (
            <div className="absolute inset-4 flex flex-col items-center justify-center gap-3">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="1">
                <path d="M20.38 3.46L16 2a4 4 0 01-8 0L3.62 3.46a2 2 0 00-1.34 2.23l.58 3.57a1 1 0 00.99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 002-2V10h2.15a1 1 0 00.99-.84l.58-3.57a2 2 0 00-1.34-2.23z"/>
              </svg>
              <span className="font-mono text-dim" style={{ fontSize: 8, letterSpacing: "0.12em" }}>
                PLACE GARMENT
              </span>
            </div>
          )}
        </div>

        {/* HUD overlays */}
        <div className="absolute flex items-center gap-1.5" style={{ top: 8, left: 8 }}>
          <div
            className="rounded-full animate-pulse-slow"
            style={{ width: 5, height: 5, background: "#EF4444", boxShadow: "0 0 5px #EF4444" }}
          />
          <span className="font-mono" style={{ fontSize: 8, color: "#EF4444", letterSpacing: "0.08em" }}>REC</span>
        </div>

        <div
          className="absolute font-mono"
          style={{ top: 8, right: 8, fontSize: 8, color: "rgba(107,122,141,0.5)" }}
        >
          {tickStr}
        </div>

        <div
          className="absolute flex items-center gap-1.5"
          style={{
            bottom: 8, left: 8,
            background: "rgba(0,0,0,0.72)", border: "1px solid #243044",
            borderRadius: 5, padding: "3px 9px",
          }}
        >
          <span className="font-mono text-text-muted" style={{ fontSize: 8 }}>TOTAL</span>
          <span
            key={total}
            className="font-mono font-bold text-accent"
            style={{ fontSize: 15, animation: "countUp 0.3s ease-out" }}
          >
            {total}
          </span>
        </div>

        {/* Analysing overlay text */}
        {isAnalysing && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div
              className="font-mono font-bold animate-pulse-slow"
              style={{ fontSize: 11, letterSpacing: "0.2em", color: "#3B82F6" }}
            >
              SCANNING GARMENT…
            </div>
          </div>
        )}
      </div>

      {/* ── Calibration strip ── */}
      <div
        className="flex items-center justify-between px-5 shrink-0"
        style={{ height: 42, borderTop: "1px solid #243044", background: "#131B26" }}
      >
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-1.5">
            <div
              className={cn("rounded-full shrink-0", calibration.status === "calibrated" && "animate-pulse-slow")}
              style={{
                width: 5, height: 5,
                background: calibration.status === "calibrated" ? "#22C55E" : "#FACC15",
                boxShadow: calibration.status === "calibrated" ? "0 0 5px #22C55E" : "0 0 5px #FACC15",
              }}
            />
            <span
              className="font-mono"
              style={{ fontSize: 10, color: calibration.status === "calibrated" ? "#22C55E" : "#FACC15" }}
            >
              {calibration.status === "calibrated" ? "Calibrated" : "Uncalibrated"}
            </span>
          </div>
          <span className="font-mono text-text-muted" style={{ fontSize: 9 }}>
            Ratio: <span className="text-text-primary">{calibration.pixelPerCmRatio} px/cm</span>
          </span>
          <span className="font-mono text-text-muted" style={{ fontSize: 9 }}>
            Ref: <span className="text-text-primary">{calibration.referenceObjectSizeCm} cm</span>
          </span>
        </div>
        <span className="font-mono text-dim" style={{ fontSize: 8 }}>Feature 4 · Cloth Size Measuring</span>
      </div>
    </div>
  );
}