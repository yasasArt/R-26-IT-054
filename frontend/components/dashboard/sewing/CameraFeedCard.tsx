// components/dashboard/sewing/CameraFeedCard.tsx
"use client";
import { useState, useEffect, useRef } from "react";
import { useSewingStore } from "@/store/sewingStore";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

function SignalChip({
  id, desc, active, color,
}: {
  id: string; desc: string; active: boolean; color: string;
}) {
  return (
    <div
      className="flex items-center gap-2 rounded-lg transition-all duration-200"
      style={{
        padding: "7px 12px",
        background: active ? `${color}12` : "rgba(255,255,255,0.02)",
        border: `1px solid ${active ? color : "#3A4A5C"}`,
        boxShadow: active ? `0 0 10px ${color}28` : "none",
        minWidth: 100,
      }}
    >
      <div
        className={cn("rounded-full shrink-0", active && "animate-pulse-slow")}
        style={{
          width: 7, height: 7,
          background: active ? color : "#3A4A5C",
          boxShadow: active ? `0 0 5px ${color}` : "none",
        }}
      />
      <div>
        <div
          className="font-mono font-bold"
          style={{ fontSize: 11, color: active ? color : "#3A4A5C", letterSpacing: "0.06em" }}
        >
          {id}
        </div>
        <div
          className="font-mono"
          style={{ fontSize: 8, color: active ? `${color}99` : "#3A4A5C" }}
        >
          {desc}
        </div>
      </div>
    </div>
  );
}

export function CameraFeedCard() {
  const { cameraStatus, dualSignal, pieceCount, detectionLog } = useSewingStore();
  const [scanPct, setScanPct]     = useState(0);
  const [showBBox, setShowBBox]   = useState(false);
  const [tickStr, setTickStr]     = useState("");
  const rafRef   = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  const sigA      = dualSignal.signalA === "triggered";
  const sigB      = dualSignal.signalB === "triggered";
  const bothFired = dualSignal.bothAgreed;
  const conf      = detectionLog[0]?.confidenceScore ?? 0.91;
  const isLive    = cameraStatus === "live";

  // Scanline
  useEffect(() => {
    if (!isLive) return;
    const tick = (ts: number) => {
      if (!startRef.current) startRef.current = ts;
      setScanPct(((ts - startRef.current) / 3000) % 1 * 100);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [isLive]);

  // Clock overlay
  useEffect(() => {
    const id = setInterval(() => setTickStr(format(new Date(), "HH:mm:ss")), 1000);
    return () => clearInterval(id);
  }, []);

  // Bounding box flash
  useEffect(() => {
    if (!bothFired) return;
    const showId = setTimeout(() => setShowBBox(true), 0);
    const hideId = setTimeout(() => setShowBBox(false), 1500);
    return () => {
      clearTimeout(showId);
      clearTimeout(hideId);
    };
  }, [bothFired, pieceCount]);

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}
    >
      {/* Card header */}
      <div
        className="flex items-center justify-between px-5 shrink-0"
        style={{ height: 54, background: "#131B26", borderBottom: "1px solid #243044" }}
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
              Camera Feed · Output Zone Monitor
            </div>
            <div className="font-mono text-text-muted" style={{ fontSize: 9 }}>
              Logitech C922 · cam-0 · 1920 × 1080 · 30 fps
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={cn("rounded-full shrink-0", isLive && "animate-pulse-slow")}
            style={{
              width: 7, height: 7,
              background: isLive ? "#22C55E" : "#EF4444",
              boxShadow: isLive ? "0 0 7px #22C55E" : "0 0 7px #EF4444",
            }}
          />
          <span
            className="font-mono font-medium"
            style={{ fontSize: 11, color: isLive ? "#22C55E" : "#EF4444" }}
          >
            {isLive ? "Live" : "Offline"}
          </span>
        </div>
      </div>

      {/* Camera view — flex-1 fills remaining card height */}
      <div
        className="relative overflow-hidden"
        style={{ flex: 1, minHeight: 190, background: "#060A0F" }}
      >
        {/* CRT texture */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,255,0,0.008) 2px, rgba(0,255,0,0.008) 3px)",
          }}
        />
        {/* Dot grid */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              "radial-gradient(circle, rgba(34,197,94,0.06) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        />

        {/* Moving scan line */}
        {isLive && (
          <div
            className="absolute left-0 right-0 pointer-events-none"
            style={{
              height: 1, top: `${scanPct}%`,
              background:
                "linear-gradient(90deg, transparent, rgba(34,197,94,0.45) 30%, rgba(34,197,94,0.65) 50%, rgba(34,197,94,0.45) 70%, transparent)",
              boxShadow: "0 0 8px rgba(34,197,94,0.4)",
            }}
          />
        )}

        {/* Machine area indicator */}
        <div
          className="absolute flex flex-col items-center justify-center gap-1"
          style={{
            left: 20, top: "50%", transform: "translateY(-50%)",
            width: 84, height: 64,
            background: "rgba(59,130,246,0.04)",
            border: "1px dashed rgba(59,130,246,0.18)",
            borderRadius: 6,
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24"
            fill="rgba(59,130,246,0.18)" stroke="rgba(59,130,246,0.4)" strokeWidth="1">
            <rect x="2" y="3" width="20" height="14" rx="2"/>
            <line x1="8" y1="21" x2="8" y2="17"/>
            <line x1="16" y1="21" x2="16" y2="17"/>
          </svg>
          <span
            className="font-mono"
            style={{ fontSize: 7, color: "rgba(59,130,246,0.35)", letterSpacing: "0.1em" }}
          >
            MACHINE
          </span>
        </div>

        {/* Output zone ROI */}
        <div
          className="absolute transition-all duration-300"
          style={{
            right: 20, top: "50%", transform: "translateY(-56%)",
            width: 124, height: 148,
            border: `1.5px dashed ${showBBox ? "rgba(34,197,94,0.85)" : "rgba(34,197,94,0.2)"}`,
            borderRadius: 6,
            boxShadow: showBBox
              ? "0 0 20px rgba(34,197,94,0.2), inset 0 0 14px rgba(34,197,94,0.06)"
              : "none",
          }}
        >
          <span
            className="absolute font-mono whitespace-nowrap transition-colors duration-200"
            style={{
              top: -13, left: "50%", transform: "translateX(-50%)",
              fontSize: 7, letterSpacing: "0.1em",
              color: showBBox ? "rgba(34,197,94,0.9)" : "rgba(34,197,94,0.32)",
            }}
          >
            OUTPUT ZONE
          </span>

          {/* Corner marks */}
          <div className="absolute top-0 left-0 w-3 h-3" style={{ borderLeft: `2px solid ${showBBox ? "#22C55E" : "rgba(34,197,94,0.3)"}`, borderTop: `2px solid ${showBBox ? "#22C55E" : "rgba(34,197,94,0.3)"}`, transition: "border-color 0.2s" }} />
          <div className="absolute top-0 right-0 w-3 h-3" style={{ borderRight: `2px solid ${showBBox ? "#22C55E" : "rgba(34,197,94,0.3)"}`, borderTop: `2px solid ${showBBox ? "#22C55E" : "rgba(34,197,94,0.3)"}`, transition: "border-color 0.2s" }} />
          <div className="absolute bottom-0 left-0 w-3 h-3" style={{ borderLeft: `2px solid ${showBBox ? "#22C55E" : "rgba(34,197,94,0.3)"}`, borderBottom: `2px solid ${showBBox ? "#22C55E" : "rgba(34,197,94,0.3)"}`, transition: "border-color 0.2s" }} />
          <div className="absolute bottom-0 right-0 w-3 h-3" style={{ borderRight: `2px solid ${showBBox ? "#22C55E" : "rgba(34,197,94,0.3)"}`, borderBottom: `2px solid ${showBBox ? "#22C55E" : "rgba(34,197,94,0.3)"}`, transition: "border-color 0.2s" }} />

          {/* Detected garment overlay */}
          {showBBox && (
            <div
              className="absolute animate-fade-in"
              style={{
                inset: 14, border: "2px solid #22C55E",
                borderRadius: 4, boxShadow: "0 0 14px rgba(34,197,94,0.35)",
              }}
            >
              <div
                className="absolute font-mono font-bold"
                style={{
                  top: -1, left: -1,
                  background: "#22C55E",
                  padding: "2px 7px", borderRadius: "4px 4px 4px 0",
                  fontSize: 8, letterSpacing: "0.05em", color: "#000",
                }}
              >
                GARMENT {(conf * 100).toFixed(0)}%
              </div>
              <div className="absolute inset-3 flex items-center justify-center">
                <svg width="40" height="50" viewBox="0 0 24 24"
                  fill="rgba(34,197,94,0.18)" stroke="rgba(34,197,94,0.55)" strokeWidth="0.9">
                  <path d="M20.38 3.46L16 2a4 4 0 01-8 0L3.62 3.46a2 2 0 00-1.34 2.23l.58 3.57a1 1 0 00.99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 002-2V10h2.15a1 1 0 00.99-.84l.58-3.57a2 2 0 00-1.34-2.23z"/>
                </svg>
              </div>
            </div>
          )}
        </div>

        {/* HUD overlays — all within overflow: hidden parent */}
        <div className="absolute flex items-center gap-1.5" style={{ top: 8, left: 8 }}>
          <div
            className="rounded-full animate-pulse-slow"
            style={{ width: 5, height: 5, background: "#EF4444", boxShadow: "0 0 5px #EF4444" }}
          />
          <span className="font-mono" style={{ fontSize: 8, color: "#EF4444", letterSpacing: "0.08em" }}>
            REC
          </span>
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
            key={pieceCount}
            className="font-mono font-bold text-success"
            style={{ fontSize: 15, animation: "countUp 0.3s ease-out" }}
          >
            {pieceCount}
          </span>
        </div>
      </div>

      {/* Dual-signal strip */}
      <div
        className="flex items-center gap-3 px-5 shrink-0"
        style={{ height: 62, borderTop: "1px solid #243044" }}
      >
        <span
          className="font-mono text-dim uppercase shrink-0"
          style={{ fontSize: 8, letterSpacing: "0.12em" }}
        >
          Dual Signal
        </span>

        <SignalChip id="SIG-A" desc="YOLOv8 Garment" active={sigA} color="#22C55E" />

        <span className="font-mono text-dim" style={{ fontSize: 16 }}>+</span>

        <SignalChip id="SIG-B" desc="Pose Wrist" active={sigB} color="#3B82F6" />

        <svg width="16" height="10" viewBox="0 0 16 10" className="shrink-0">
          <path
            d="M0 5H11M7.5 1.5L12 5L7.5 8.5"
            stroke={bothFired ? "#22C55E" : "#3A4A5C"}
            strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none"
          />
        </svg>

        {/* Count event badge */}
        <div
          className="flex items-center gap-1.5 font-mono font-bold transition-all duration-200 shrink-0"
          style={{
            fontSize: 10, letterSpacing: "0.06em",
            padding: "6px 12px", borderRadius: 8,
            background: bothFired ? "rgba(34,197,94,0.14)" : "rgba(255,255,255,0.02)",
            border: `1px solid ${bothFired ? "#22C55E" : "#3A4A5C"}`,
            color: bothFired ? "#22C55E" : "#3A4A5C",
            boxShadow: bothFired ? "0 0 12px rgba(34,197,94,0.3)" : "none",
          }}
        >
          {bothFired && (
            <div
              className="rounded-full animate-pulse-slow"
              style={{ width: 6, height: 6, background: "#22C55E", boxShadow: "0 0 5px #22C55E" }}
            />
          )}
          COUNT EVENT
        </div>

        <div
          className="ml-auto flex items-center gap-1.5 font-mono text-text-muted shrink-0"
          style={{
            fontSize: 8, padding: "4px 9px", borderRadius: 6,
            background: "#0B1017", border: "1px solid #243044",
          }}
        >
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          Overlap protected
        </div>
      </div>
    </div>
  );
}