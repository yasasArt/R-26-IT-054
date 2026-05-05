"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronLeft, ChevronRight, CheckCircle2,
  User, Target, Clock,
} from "lucide-react";
import { useWorkstationStore } from "@/store/workstationStore";
import { ModeIndicator } from "@/components/layout/ModeIndicator";
import { cn } from "@/lib/utils";
import { PRODUCTION_SPECS, ROUTES, APP_NAME } from "@/lib/constants";
import type { AreaMode } from "@/lib/types";

// ═════════════════════════════════════════════════════════════
// ANIMATED VISUALS (private)
// ═════════════════════════════════════════════════════════════

function SewingCardVisual() {
  const [sigA, setSigA]       = useState(false);
  const [sigB, setSigB]       = useState(false);
  const [garment, setGarment] = useState(false);
  const [count, setCount]     = useState(47);

  useEffect(() => {
    let mounted = true;
    const timers: ReturnType<typeof setTimeout>[] = [];

    function runCycle() {
      if (!mounted) return;
      setSigB(true);
      timers.push(
        setTimeout(() => { if (mounted) { setSigA(true); setGarment(true); } }, 700),
        setTimeout(() => { if (mounted) setCount(c => c + 1); }, 1050),
        setTimeout(() => { if (mounted) { setSigA(false); setSigB(false); } }, 1900),
        setTimeout(() => { if (mounted) setGarment(false); }, 2700)
      );
    }

    timers.push(setTimeout(runCycle, 600));
    const id = setInterval(runCycle, 4700);
    return () => {
      mounted = false;
      clearInterval(id);
      timers.forEach(clearTimeout);
    };
  }, []);

  return (
    <div
      className="relative overflow-hidden"
      style={{ height: 180, background: "#060C12" }}
    >
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(34,197,94,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(34,197,94,0.07) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />

      <div
        className="absolute flex flex-col items-center justify-center gap-1"
        style={{
          left: 28, top: "50%", transform: "translateY(-50%)",
          width: 80, height: 62,
          background: "rgba(59,130,246,0.06)",
          border: "1px solid rgba(59,130,246,0.2)",
          borderRadius: 7,
        }}
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="rgba(59,130,246,0.35)"
          stroke="rgba(59,130,246,0.6)"
          strokeWidth="1"
        >
          <rect x="2" y="3" width="20" height="14" rx="2" />
          <line x1="8" y1="21" x2="8" y2="17" />
          <line x1="16" y1="21" x2="16" y2="17" />
          <line x1="12" y1="17" x2="12" y2="21" />
        </svg>
        <span
          className="font-mono"
          style={{ fontSize: 7, color: "rgba(59,130,246,0.5)", letterSpacing: "0.1em" }}
        >
          MACHINE
        </span>
      </div>

      <div
        className="absolute"
        style={{
          left: 114, right: 128, top: "50%",
          height: 1, transform: "translateY(-50%)",
          background: "linear-gradient(90deg, rgba(59,130,246,0.2), rgba(34,197,94,0.38))",
        }}
      >
        <div
          className="absolute right-0 top-1/2 -translate-y-1/2"
          style={{
            borderLeft: "5px solid rgba(34,197,94,0.5)",
            borderTop: "3px solid transparent",
            borderBottom: "3px solid transparent",
          }}
        />
      </div>

      <div
        className="absolute transition-all duration-300"
        style={{
          right: 28, top: "50%", transform: "translateY(-50%)",
          width: 90, height: 110,
          border: `2px dashed ${garment ? "rgba(34,197,94,0.7)" : "rgba(34,197,94,0.22)"}`,
          borderRadius: 7,
          boxShadow: garment ? "0 0 22px rgba(34,197,94,0.18)" : "none",
        }}
      >
        <span
          className="absolute font-mono whitespace-nowrap"
          style={{
            top: -15, left: "50%", transform: "translateX(-50%)",
            fontSize: 7, color: "rgba(34,197,94,0.4)", letterSpacing: "0.1em",
          }}
        >
          OUTPUT ZONE
        </span>
        {garment && (
          <div
            className="absolute inset-2.5 flex items-center justify-center animate-fade-in"
            style={{
              background: "rgba(34,197,94,0.08)",
              border: "1px solid rgba(34,197,94,0.38)",
              borderRadius: 5,
            }}
          >
            <svg
              width="28"
              height="36"
              viewBox="0 0 24 24"
              fill="rgba(34,197,94,0.25)"
              stroke="rgba(34,197,94,0.6)"
              strokeWidth="0.9"
            >
              <path d="M20.38 3.46L16 2a4 4 0 01-8 0L3.62 3.46a2 2 0 00-1.34 2.23l.58 3.57a1 1 0 00.99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 002-2V10h2.15a1 1 0 00.99-.84l.58-3.57a2 2 0 00-1.34-2.23z" />
            </svg>
          </div>
        )}
      </div>

      <div
        className="absolute flex items-center gap-1.5"
        style={{
          top: 10, right: 10, padding: "3px 10px", borderRadius: 6,
          background: "rgba(0,0,0,0.65)", border: "1px solid #243044",
        }}
      >
        <span className="font-mono text-text-muted" style={{ fontSize: 8 }}>
          COUNT
        </span>
        <span
          key={count}
          className="font-mono font-bold text-success"
          style={{ fontSize: 22, lineHeight: 1, animation: "countUp 0.3s ease-out" }}
        >
          {count}
        </span>
      </div>

      <div className="absolute bottom-2.5 left-4 flex items-center gap-1.5">
        {[
          { id: "SIG-A", active: sigA, color: "#22C55E" },
          { id: "SIG-B", active: sigB, color: "#3B82F6" },
        ].map(s => (
          <div
            key={s.id}
            className="font-mono font-semibold transition-all duration-200"
            style={{
              fontSize: 8, padding: "3px 7px", borderRadius: 4, letterSpacing: "0.08em",
              background: s.active ? `${s.color}15` : "rgba(255,255,255,0.02)",
              border: `1px solid ${s.active ? s.color : "#3A4A5C"}`,
              color: s.active ? s.color : "#3A4A5C",
              boxShadow: s.active ? `0 0 8px ${s.color}35` : "none",
            }}
          >
            {s.id}
          </div>
        ))}
        {sigA && sigB && (
          <div
            className="font-mono font-semibold animate-fade-in"
            style={{
              fontSize: 8, padding: "3px 8px", borderRadius: 4, letterSpacing: "0.08em",
              background: "rgba(34,197,94,0.15)", border: "1px solid #22C55E", color: "#22C55E",
            }}
          >
            ✓ COUNT
          </div>
        )}
      </div>
    </div>
  );
}

function QualityCardVisual() {
  const [scanY, setScanY] = useState(0);
  const [showResults, setResults] = useState(false);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    let mounted = true;
    const tick = (ts: number) => {
      if (!mounted) return;
      if (!startRef.current) startRef.current = ts;
      const p = Math.min((ts - startRef.current) / 2600, 1);
      setScanY(p * 148);
      if (p > 0.46) setResults(true);
      if (p < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setTimeout(() => {
          if (!mounted) return;
          setScanY(0);
          setResults(false);
          startRef.current = null;
          rafRef.current = requestAnimationFrame(tick);
        }, 1600);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      mounted = false;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <div className="relative overflow-hidden flex" style={{ height: 180, background: "#060C12" }}>
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, transparent, transparent 5px, rgba(59,130,246,0.018) 5px, rgba(59,130,246,0.018) 6px)",
        }}
      />

      <div
        className="relative overflow-hidden shrink-0"
        style={{
          width: 156, margin: 14, background: "#0A0E14",
          border: "1px solid #243044", borderRadius: 9,
        }}
      >
        <div
          className="absolute flex items-center justify-center"
          style={{
            inset: 16, background: "rgba(59,130,246,0.05)",
            border: "1px solid rgba(59,130,246,0.14)", borderRadius: 5,
          }}
        >
          <svg
            width="36"
            height="44"
            viewBox="0 0 24 24"
            fill="rgba(59,130,246,0.13)"
            stroke="rgba(59,130,246,0.28)"
            strokeWidth="0.8"
          >
            <path d="M20.38 3.46L16 2a4 4 0 01-8 0L3.62 3.46a2 2 0 00-1.34 2.23l.58 3.57a1 1 0 00.99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 002-2V10h2.15a1 1 0 00.99-.84l.58-3.57a2 2 0 00-1.34-2.23z" />
          </svg>
          {showResults && (
            <div
              className="absolute flex items-center justify-center"
              style={{ top: "15%", left: 5, right: 5, height: 1, background: "rgba(250,204,21,0.5)" }}
            >
              <span
                className="font-mono absolute"
                style={{ fontSize: 7, color: "#FACC15", background: "#0A0E14", padding: "0 2px" }}
              >
                48.2cm
              </span>
            </div>
          )}
        </div>
        <div
          className="absolute left-0 right-0 pointer-events-none"
          style={{
            height: 2, top: scanY,
            background: "linear-gradient(90deg, transparent, #3B82F6, transparent)",
            boxShadow: "0 0 10px #3B82F6",
            transition: "top 0.04s linear",
          }}
        />
        <div className="absolute flex items-center gap-1" style={{ top: 6, left: 6 }}>
          <div
            className="rounded-full animate-pulse-slow"
            style={{ width: 4, height: 4, background: "#EF4444", boxShadow: "0 0 5px #EF4444" }}
          />
          <span className="font-mono font-semibold" style={{ fontSize: 7, color: "#EF4444" }}>
            LIVE
          </span>
        </div>
      </div>

      <div className="flex-1 flex flex-col gap-2 py-3.5 pr-3.5">
        <div
          className="flex-1 px-3 py-2.5 transition-all duration-300"
          style={{
            background: showResults ? "rgba(59,130,246,0.08)" : "rgba(255,255,255,0.02)",
            border: `1px solid ${showResults ? "rgba(59,130,246,0.28)" : "#243044"}`,
            borderRadius: 7,
          }}
        >
          <div className="font-mono text-text-muted mb-1" style={{ fontSize: 7 }}>
            SIZE
          </div>
          <div
            className="font-mono font-bold transition-colors duration-300"
            style={{ fontSize: 30, lineHeight: 1, color: showResults ? "#3B82F6" : "#3A4A5C" }}
          >
            {showResults ? "M" : "—"}
          </div>
        </div>
        <div
          className="flex-1 px-3 py-2.5"
          style={{ background: "rgba(255,255,255,0.02)", border: "1px solid #243044", borderRadius: 7 }}
        >
          <div className="font-mono text-text-muted mb-2" style={{ fontSize: 7 }}>
            COLOUR
          </div>
          <div className="flex gap-1.5">
            {showResults ? (
              [{ h: "#1E3A5F" }, { h: "#F8F8F8" }].map((c, i) => (
                <div
                  key={i}
                  className="rounded-full shrink-0 animate-fade-in"
                  style={{
                    width: 20, height: 20, background: c.h,
                    border: "1px solid #243044", boxShadow: `0 0 7px ${c.h}55`,
                  }}
                />
              ))
            ) : (
              <div className="rounded-full" style={{ width: 20, height: 20, background: "#3A4A5C" }} />
            )}
          </div>
        </div>
        {showResults && (
          <div
            className="text-center animate-fade-in px-2 py-2"
            style={{
              background: "rgba(34,197,94,0.1)",
              border: "1px solid rgba(34,197,94,0.38)",
              borderRadius: 7,
            }}
          >
            <span className="font-mono font-bold text-success" style={{ fontSize: 11, letterSpacing: "0.08em" }}>
              ✓ PASS
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// STEP COMPONENTS
// ═════════════════════════════════════════════════════════════

function StepModeSelect({
  mode,
  setMode,
  error,
}: {
  mode: AreaMode | null;
  setMode: (m: AreaMode) => void;
  error?: string;
}) {
  const MODES = [
    {
      id: "sewing" as AreaMode,
      title: "Sewing Operator Area",
      sub: "Feature 2 · Counting & Cycle Time",
      color: "#22C55E",
      visual: <SewingCardVisual />,
      features: [
        "Dual-signal piece counting (YOLOv8 + Pose)",
        "Operator cycle time analysis & tracking",
        "IoT-based rework & downtime controls",
        "Shift KPIs, charts, and production log",
      ],
      iotNote: "Requires ESP32 IoT device",
      hasIoT: true,
    },
    {
      id: "quality" as AreaMode,
      title: "Quality Checker Area",
      sub: "Feature 3 + 4 · Inspection & Measurement",
      color: "#3B82F6",
      visual: <QualityCardVisual />,
      features: [
        "Colour & style recognition (HSV + CNN)",
        "Cloth size measurement using px/cm ratio",
        "Pass / rework / mismatch decision engine",
        "Production specification matching",
      ],
      iotNote: "Camera only · no IoT device",
      hasIoT: false,
    },
  ] as const;

  return (
    <div>
      <div className="text-center" style={{ marginBottom: 48 }}>
        <p
          className="font-mono text-dim uppercase"
          style={{ fontSize: 9, letterSpacing: "0.2em", marginBottom: 12 }}
        >
          {APP_NAME} · Setup — Step 1 of 3
        </p>
        <h2 className="font-display font-bold text-text-primary" style={{ fontSize: 28, marginBottom: 12 }}>
          Select Area Mode
        </h2>
        <p
          className="font-display text-text-muted"
          style={{ fontSize: 14, maxWidth: 460, margin: "0 auto", lineHeight: 1.6 }}
        >
          Choose the factory area this workstation will monitor. All dashboard
          widgets, device connections, and analysis features adapt to your selection.
        </p>
        {error && (
          <p className="font-mono text-danger animate-fade-in" style={{ fontSize: 11, marginTop: 14 }}>
            {error}
          </p>
        )}
      </div>

      <div
        className="grid gap-8"
        style={{ gridTemplateColumns: "repeat(2, minmax(420px, 1fr))" }}
      >
        {MODES.map(card => {
          const sel = mode === card.id;
          return (
            <button
              key={card.id}
              type="button"
              onClick={() => setMode(card.id)}
              className={cn(
                "text-left cursor-pointer overflow-hidden transition-all duration-250",
                sel && card.id === "sewing" && "mode-selected-sewing",
                sel && card.id === "quality" && "mode-selected-quality",
              )}
              style={{
                borderRadius: 16,
                background: "#1A2536",
                border: `2px solid ${sel ? card.color : "#243044"}`,
                padding: 0,
                transform: sel ? "translateY(-4px)" : "translateY(0)",
                boxShadow: sel ? "0 16px 48px rgba(0,0,0,0.4)" : "0 4px 16px rgba(0,0,0,0.25)",
              }}
            >
              {card.visual}

              <div style={{ padding: "24px 26px 22px" }}>
                <div className="flex items-start justify-between" style={{ marginBottom: 16 }}>
                  <div>
                    <div
                      className="font-display font-bold transition-colors duration-200"
                      style={{ fontSize: 17, color: sel ? card.color : "#E8ECF1", marginBottom: 4 }}
                    >
                      {card.title}
                    </div>
                    <div className="font-mono text-text-muted" style={{ fontSize: 9, letterSpacing: "0.04em" }}>
                      {card.sub}
                    </div>
                  </div>
                  {sel && (
                    <div
                      className="flex items-center justify-center shrink-0 animate-fade-in"
                      style={{ width: 22, height: 22, borderRadius: "50%", background: card.color }}
                    >
                      <svg
                        width="11"
                        height="11"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#000"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                  )}
                </div>

                <div style={{ marginBottom: 20 }}>
                  {card.features.map(f => (
                    <div
                      key={f}
                      className="flex items-start gap-2.5 text-text-muted"
                      style={{ fontSize: 12.5, marginBottom: 9, lineHeight: 1.4 }}
                    >
                      <div
                        className="rounded-full shrink-0 transition-colors duration-200"
                        style={{
                          width: 4, height: 4,
                          marginTop: 5,
                          background: sel ? card.color : "#3A4A5C",
                        }}
                      />
                      {f}
                    </div>
                  ))}
                </div>

                <div
                  className="flex items-center justify-between"
                  style={{ paddingTop: 16, borderTop: "1px solid #243044" }}
                >
                  <div className="flex items-center gap-1.5">
                    <div
                      className="rounded-full"
                      style={{
                        width: 5, height: 5,
                        background: card.hasIoT ? "#22C55E" : "#3A4A5C",
                      }}
                    />
                    <span className="font-mono text-text-muted" style={{ fontSize: 9 }}>
                      {card.iotNote}
                    </span>
                  </div>
                  <span className="font-mono" style={{ fontSize: 9, color: sel ? card.color : "#3A4A5C" }}>
                    {sel ? "✓ Selected" : "Click to select"}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function StepDevices({
  mode,
  activeSpecId,
  setSpec,
}: {
  mode: AreaMode;
  activeSpecId: string;
  setSpec: (v: string) => void;
}) {
  const activeSpec = PRODUCTION_SPECS.find(s => s.specId === activeSpecId);

  return (
    <div style={{ width: "100%", maxWidth: 1320, margin: "0 auto" }}>
      <div className="text-center" style={{ marginBottom: 40 }}>
        <p
          className="font-mono text-dim uppercase"
          style={{ fontSize: 9, letterSpacing: "0.2em", marginBottom: 12 }}
        >
          {APP_NAME} · Setup — Step 2 of 3
        </p>
        <h2 className="font-display font-bold text-text-primary" style={{ fontSize: 28, marginBottom: 14 }}>
          Device Configuration
        </h2>
        <div className="flex justify-center">
          <ModeIndicator mode={mode} size="sm" />
        </div>
      </div>

      <div
        className="grid gap-8"
        style={{ gridTemplateColumns: "repeat(2, minmax(460px, 1fr))" }}
      >
        <div style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 14 }}>
          <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: "1px solid #243044" }}>
            <div className="flex items-center gap-3">
              <div
                className="flex items-center justify-center"
                style={{
                  width: 34, height: 34, borderRadius: 9,
                  background: "rgba(59,130,246,0.1)",
                  border: "1px solid rgba(59,130,246,0.25)",
                }}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#3B82F6"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M23 7l-7 5 7 5V7z" />
                  <rect x="1" y="5" width="15" height="14" rx="2" />
                </svg>
              </div>
              <div>
                <div className="font-display font-semibold text-text-primary" style={{ fontSize: 14 }}>
                  Camera Device
                </div>
                <div className="font-mono text-text-muted" style={{ fontSize: 9 }}>
                  Primary input — output zone monitor
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <div
                className="rounded-full animate-pulse-slow"
                style={{ width: 6, height: 6, background: "#22C55E", boxShadow: "0 0 6px #22C55E" }}
              />
              <span className="font-mono text-success" style={{ fontSize: 11 }}>
                Live
              </span>
            </div>
          </div>

          <div style={{ padding: "24px" }}>
            <div
              className="relative flex items-center justify-center overflow-hidden"
              style={{
                height: 80, marginBottom: 20,
                background: "#0A0E14",
                border: "1px solid #243044",
                borderRadius: 10,
              }}
            >
              <div
                className="absolute inset-0"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(59,130,246,0.02) 3px, rgba(59,130,246,0.02) 4px)",
                }}
              />
              <span className="font-mono text-dim" style={{ fontSize: 9, letterSpacing: "0.1em" }}>
                CAMERA FEED PREVIEW
              </span>
              <div className="absolute flex items-center gap-1" style={{ top: 7, right: 10 }}>
                <div
                  className="rounded-full animate-pulse-slow"
                  style={{ width: 4, height: 4, background: "#EF4444", boxShadow: "0 0 4px #EF4444" }}
                />
                <span className="font-mono" style={{ fontSize: 7, color: "#EF4444" }}>
                  REC
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3" style={{ marginBottom: 16 }}>
              {[
                { l: "Device", v: "Logitech C922" },
                { l: "Camera ID", v: "cam-0" },
                { l: "Resolution", v: "1920 × 1080" },
                { l: "Frame Rate", v: "30 fps" },
              ].map(({ l, v }) => (
                <div
                  key={l}
                  style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 8, padding: "10px 14px" }}
                >
                  <div
                    className="font-mono text-dim uppercase"
                    style={{ fontSize: 8, letterSpacing: "0.09em", marginBottom: 4 }}
                  >
                    {l}
                  </div>
                  <div className="font-mono text-text-primary" style={{ fontSize: 11 }}>
                    {v}
                  </div>
                </div>
              ))}
            </div>

            <div
              className="flex items-center gap-2 font-mono"
              style={{
                padding: "9px 14px", borderRadius: 8, fontSize: 10,
                background: "rgba(34,197,94,0.06)",
                border: "1px solid rgba(34,197,94,0.2)",
                color: "#22C55E",
              }}
            >
              <div
                className="rounded-full animate-pulse-slow"
                style={{ width: 5, height: 5, background: "#22C55E", boxShadow: "0 0 5px #22C55E" }}
              />
              {mode === "quality" ? "Calibrated · 18.4 px/cm ratio" : "Camera feed active · 30fps"}
            </div>
          </div>
        </div>

        {mode === "sewing" ? (
          <div style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 14 }}>
            <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: "1px solid #243044" }}>
              <div className="flex items-center gap-3">
                <div
                  className="flex items-center justify-center"
                  style={{
                    width: 34, height: 34, borderRadius: 9,
                    background: "rgba(34,197,94,0.1)",
                    border: "1px solid rgba(34,197,94,0.25)",
                  }}
                >
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#22C55E"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M5 12.55a11 11 0 0 1 14.08 0" />
                    <path d="M1.42 9a16 16 0 0 1 21.16 0" />
                    <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
                    <line x1="12" y1="20" x2="12.01" y2="20" />
                  </svg>
                </div>
                <div>
                  <div className="font-display font-semibold text-text-primary" style={{ fontSize: 14 }}>
                    IoT Device
                  </div>
                  <div className="font-mono text-text-muted" style={{ fontSize: 9 }}>
                    ESP32 · Rework & Downtime switches
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="rounded-full animate-pulse-slow"
                  style={{ width: 6, height: 6, background: "#22C55E", boxShadow: "0 0 6px #22C55E" }}
                />
                <span className="font-mono text-success" style={{ fontSize: 11 }}>
                  Paired
                </span>
              </div>
            </div>

            <div style={{ padding: "24px" }}>
              <div style={{ marginBottom: 20 }}>
                <div
                  className="font-mono text-dim uppercase"
                  style={{ fontSize: 8, letterSpacing: "0.1em", marginBottom: 10 }}
                >
                  Signal Strength
                </div>
                <div className="flex items-end gap-1.5" style={{ height: 30 }}>
                  {[38, 55, 68, 82, 100].map((h, i) => (
                    <div
                      key={i}
                      style={{
                        width: 10, height: `${h}%`, borderRadius: 2.5,
                        background: i < 4 ? "#22C55E" : "rgba(34,197,94,0.2)",
                        boxShadow: i < 4 ? "0 0 5px rgba(34,197,94,0.45)" : "none",
                      }}
                    />
                  ))}
                  <span className="font-mono text-success" style={{ fontSize: 10, marginLeft: 8 }}>
                    Strong · 4 ms
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3" style={{ marginBottom: 16 }}>
                {[
                  { l: "Model", v: "ESP32-WROOM" },
                  { l: "IP", v: "192.168.1.105" },
                  { l: "Firmware", v: "v2.1.3" },
                  { l: "Latency", v: "4 ms" },
                ].map(({ l, v }) => (
                  <div
                    key={l}
                    style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 8, padding: "10px 14px" }}
                  >
                    <div
                      className="font-mono text-dim uppercase"
                      style={{ fontSize: 8, letterSpacing: "0.09em", marginBottom: 4 }}
                    >
                      {l}
                    </div>
                    <div className="font-mono text-text-primary" style={{ fontSize: 11 }}>
                      {v}
                    </div>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-3" style={{ marginBottom: 16 }}>
                {[
                  { label: "Rework Button", color: "#FACC15" },
                  { label: "Downtime Button", color: "#EF4444" },
                ].map(sw => (
                  <div
                    key={sw.label}
                    style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 8, padding: "10px 14px" }}
                  >
                    <div
                      className="font-mono text-dim uppercase"
                      style={{ fontSize: 8, letterSpacing: "0.09em", marginBottom: 6 }}
                    >
                      {sw.label}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div
                        className="rounded-full"
                        style={{ width: 5, height: 5, background: "#22C55E", boxShadow: "0 0 4px #22C55E" }}
                      />
                      <span className="font-mono text-success" style={{ fontSize: 10 }}>
                        Ready
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <div
                className="flex items-center gap-2 font-mono"
                style={{
                  padding: "9px 14px", borderRadius: 8, fontSize: 10,
                  background: "rgba(34,197,94,0.06)",
                  border: "1px solid rgba(34,197,94,0.2)", color: "#22C55E",
                }}
              >
                <div
                  className="rounded-full animate-pulse-slow"
                  style={{ width: 5, height: 5, background: "#22C55E", boxShadow: "0 0 5px #22C55E" }}
                />
                Device paired · Strong signal
              </div>
            </div>
          </div>
        ) : (
          <div style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 14 }}>
            <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: "1px solid #243044" }}>
              <div className="flex items-center gap-3">
                <div
                  className="flex items-center justify-center"
                  style={{
                    width: 34, height: 34, borderRadius: 9,
                    background: "rgba(59,130,246,0.1)",
                    border: "1px solid rgba(59,130,246,0.25)",
                  }}
                >
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#3B82F6"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" />
                    <polyline points="10 9 9 9 8 9" />
                  </svg>
                </div>
                <div>
                  <div className="font-display font-semibold text-text-primary" style={{ fontSize: 14 }}>
                    Production Specification
                  </div>
                  <div className="font-mono text-text-muted" style={{ fontSize: 9 }}>
                    Defines expected garment attributes
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="rounded-full animate-pulse-slow"
                  style={{ width: 6, height: 6, background: "#3B82F6", boxShadow: "0 0 6px #3B82F6" }}
                />
                <span className="font-mono text-accent" style={{ fontSize: 11 }}>
                  Active
                </span>
              </div>
            </div>

            <div style={{ padding: "24px" }}>
              <div style={{ marginBottom: 20 }}>
                <div
                  className="font-mono text-dim uppercase"
                  style={{ fontSize: 8, letterSpacing: "0.1em", marginBottom: 10 }}
                >
                  Active Specification
                </div>
                <select
                  value={activeSpecId}
                  onChange={e => setSpec(e.target.value)}
                  className="w-full font-display text-text-primary cursor-pointer focus:outline-none"
                  style={{
                    height: 44, padding: "0 14px", fontSize: 13,
                    background: "#0B1017",
                    border: "1px solid #243044",
                    borderRadius: 9,
                  }}
                >
                  {PRODUCTION_SPECS.map(s => (
                    <option key={s.specId} value={s.specId}>
                      {s.specLabel} — {s.expectedStyle} {s.expectedSize}
                    </option>
                  ))}
                </select>
              </div>

              {activeSpec && (
                <div style={{ marginBottom: 16 }}>
                  <div
                    className="font-mono text-dim uppercase"
                    style={{ fontSize: 8, letterSpacing: "0.1em", marginBottom: 10 }}
                  >
                    Expected Attributes
                  </div>
                  <div style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 9, overflow: "hidden" }}>
                    <div
                      className="grid font-mono text-dim uppercase px-4 py-2.5"
                      style={{
                        fontSize: 7.5, letterSpacing: "0.1em",
                        gridTemplateColumns: "1fr 1fr",
                        borderBottom: "1px solid #243044",
                      }}
                    >
                      <span>Attribute</span>
                      <span>Expected Value</span>
                    </div>
                    {[
                      ["Style", activeSpec.expectedStyle],
                      ["Size", activeSpec.expectedSize],
                      ["Colour(s)", activeSpec.expectedColours.join(", ")],
                    ].map(([k, v], i, arr) => (
                      <div
                        key={k}
                        className="flex justify-between px-4 py-3"
                        style={{ borderBottom: i < arr.length - 1 ? "1px solid rgba(36,48,68,0.5)" : "none" }}
                      >
                        <span className="font-mono text-text-muted" style={{ fontSize: 11 }}>
                          {k}
                        </span>
                        <span className="font-mono text-text-primary" style={{ fontSize: 11 }}>
                          {v}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div
                className="flex items-center gap-2 font-mono"
                style={{
                  padding: "9px 14px", borderRadius: 8, fontSize: 10,
                  background: "rgba(34,197,94,0.06)",
                  border: "1px solid rgba(34,197,94,0.2)", color: "#22C55E",
                }}
              >
                <div
                  className="rounded-full animate-pulse-slow"
                  style={{ width: 5, height: 5, background: "#22C55E", boxShadow: "0 0 5px #22C55E" }}
                />
                Camera calibrated · 18.4 px/cm ratio
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StepSession({
  mode,
  operatorName,
  setOperator,
  shiftTarget,
  setTarget,
  activeSpecId,
  stationLabel,
  stationId,
  errors,
}: {
  mode: AreaMode;
  operatorName: string;
  setOperator: (v: string) => void;
  shiftTarget: number;
  setTarget: (v: number) => void;
  activeSpecId: string;
  stationLabel: string;
  stationId: string;
  errors: Record<string, string>;
}) {
  const pph = Math.round(shiftTarget / 8);

  return (
    <div style={{ width: "100%", maxWidth: 1100, margin: "0 auto" }}>
      <div className="text-center" style={{ marginBottom: 40 }}>
        <p
          className="font-mono text-dim uppercase"
          style={{ fontSize: 9, letterSpacing: "0.2em", marginBottom: 12 }}
        >
          {APP_NAME} · Setup — Step 3 of 3
        </p>
        <h2 className="font-display font-bold text-text-primary" style={{ fontSize: 28, marginBottom: 10 }}>
          Session Details
        </h2>
        <p className="font-display text-text-muted" style={{ fontSize: 14, lineHeight: 1.6 }}>
          Enter the operator name and confirm the shift parameters before starting.
        </p>
      </div>

      <div
        className="grid gap-8"
        style={{ gridTemplateColumns: "repeat(2, minmax(320px, 1fr))", marginBottom: 20 }}
      >
        <div style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 14, padding: "26px" }}>
          <div className="flex items-center gap-2.5" style={{ marginBottom: 24 }}>
            <div
              style={{
                width: 30, height: 30, borderRadius: 8,
                background: "rgba(59,130,246,0.1)",
                border: "1px solid rgba(59,130,246,0.25)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              <User size={14} className="text-accent" />
            </div>
            <div>
              <div className="font-display font-semibold text-text-primary" style={{ fontSize: 14 }}>
                Operator
              </div>
              <div className="font-mono text-text-muted" style={{ fontSize: 9 }}>
                Person running this session
              </div>
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label
              className="font-mono text-text-muted uppercase block"
              style={{ fontSize: 9, letterSpacing: "0.12em", marginBottom: 10 }}
            >
              Name *
            </label>
            <input
              type="text"
              value={operatorName}
              onChange={e => setOperator(e.target.value)}
              placeholder="Enter operator name"
              autoFocus
              className="w-full font-display text-text-primary focus:outline-none transition-all duration-200"
              style={{
                height: 46,
                padding: "0 14px",
                fontSize: 14,
                background: "#0B1017",
                border: `1px solid ${errors.operatorName ? "#EF4444" : operatorName ? "#3B82F6" : "#243044"}`,
                borderRadius: 9,
                boxShadow: operatorName && !errors.operatorName ? "0 0 0 3px rgba(59,130,246,0.12)" : "none",
              }}
            />
            {errors.operatorName && (
              <p className="font-mono text-danger animate-fade-in" style={{ fontSize: 10, marginTop: 6 }}>
                {errors.operatorName}
              </p>
            )}
          </div>

          <div style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 9, padding: "12px 14px" }}>
            <div className="font-mono text-dim uppercase" style={{ fontSize: 8, letterSpacing: "0.09em", marginBottom: 5 }}>
              Station
            </div>
            <div className="font-mono text-text-primary" style={{ fontSize: 12 }}>
              {stationLabel}
            </div>
          </div>
        </div>

        <div style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 14, padding: "26px" }}>
          <div className="flex items-center gap-2.5" style={{ marginBottom: 24 }}>
            <div
              style={{
                width: 30, height: 30, borderRadius: 8,
                background: "rgba(59,130,246,0.1)",
                border: "1px solid rgba(59,130,246,0.25)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              {mode === "sewing" ? (
                <Target size={14} className="text-accent" />
              ) : (
                <Clock size={14} className="text-accent" />
              )}
            </div>
            <div>
              <div className="font-display font-semibold text-text-primary" style={{ fontSize: 14 }}>
                Shift Parameters
              </div>
              <div className="font-mono text-text-muted" style={{ fontSize: 9 }}>
                Production targets for this session
              </div>
            </div>
          </div>

          <div
            style={{
              background: "#0B1017",
              border: "1px solid #243044",
              borderRadius: 9,
              padding: "12px 14px",
              marginBottom: 14,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <Clock size={12} className="text-text-muted shrink-0" />
            <div>
              <div className="font-mono text-dim uppercase" style={{ fontSize: 8, letterSpacing: "0.09em" }}>
                Start Time
              </div>
              <div className="font-mono text-text-primary" style={{ fontSize: 11 }}>
                Now (set automatically)
              </div>
            </div>
          </div>

          {mode === "sewing" && (
            <div style={{ marginBottom: 14 }}>
              <label
                className="font-mono text-text-muted uppercase block"
                style={{ fontSize: 9, letterSpacing: "0.12em", marginBottom: 10 }}
              >
                Piece Target (pcs)
              </label>
              <input
                type="number"
                value={shiftTarget}
                onChange={e => setTarget(Number(e.target.value))}
                min={1}
                max={500}
                className="w-full font-mono text-text-primary focus:outline-none"
                style={{
                  height: 46, padding: "0 14px", fontSize: 20, fontWeight: 700,
                  background: "#0B1017", border: "1px solid #243044", borderRadius: 9,
                }}
              />
              <p className="font-mono text-dim" style={{ fontSize: 9, marginTop: 7 }}>
                ≈ {pph} pieces per hour over an 8-hour shift
              </p>
            </div>
          )}

          {mode === "quality" && (
            <div style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 9, padding: "12px 14px" }}>
              <div
                className="font-mono text-dim uppercase"
                style={{ fontSize: 8, letterSpacing: "0.09em", marginBottom: 5 }}
              >
                Active Spec
              </div>
              <div className="font-mono text-accent" style={{ fontSize: 13, fontWeight: 600 }}>
                {activeSpecId}
              </div>
            </div>
          )}
        </div>
      </div>

      <div
        style={{
          background: "#131B26",
          border: "1px solid #243044",
          borderRadius: 12,
          padding: "18px 24px",
        }}
      >
        <div className="font-mono text-dim uppercase" style={{ fontSize: 8, letterSpacing: "0.15em", marginBottom: 14 }}>
          Session Preview
        </div>
        <div className="grid grid-cols-4 gap-4">
          {[
            {
              l: "Mode",
              v: mode === "sewing" ? "Sewing" : "Quality",
              c: mode === "sewing" ? "#22C55E" : "#3B82F6",
            },
            { l: "Station", v: stationId, c: "#E8ECF1" },
            { l: "Operator", v: operatorName || "—", c: operatorName ? "#E8ECF1" : "#3A4A5C" },
            {
              l: mode === "sewing" ? "Target" : "Spec",
              v: mode === "sewing" ? `${shiftTarget} pcs` : activeSpecId,
              c: "#E8ECF1",
            },
          ].map(({ l, v, c }) => (
            <div key={l}>
              <div className="font-mono text-dim uppercase" style={{ fontSize: 8, letterSpacing: "0.1em", marginBottom: 6 }}>
                {l}
              </div>
              <div className="font-mono font-semibold" style={{ fontSize: 13, color: c }}>
                {v}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// MAIN PAGE
// ═════════════════════════════════════════════════════════════

type WizardStep = 1 | 2 | 3;
const STEP_LABELS = ["Area Mode", "Devices", "Session"];

export default function SetupPage() {
  const router = useRouter();
  const { setConfig, startSession, config } = useWorkstationStore();

  const [step, setStep] = useState<WizardStep>(1);
  const [mode, setMode] = useState<AreaMode | null>(null);
  const [operatorName, setOperator] = useState("");
  const [shiftTarget, setTarget] = useState(150);
  const [activeSpecId, setSpec] = useState(PRODUCTION_SPECS[0].specId);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function validate(s: WizardStep): boolean {
    const e: Record<string, string> = {};
    if (s === 1 && !mode) e.mode = "Please select an area mode to continue.";
    if (s === 3 && !operatorName.trim()) e.operatorName = "Operator name is required.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function next() {
    if (!validate(step)) return;
    if (step < 3) {
      setStep(s => (s + 1) as WizardStep);
    } else if (mode) {
      setConfig({ shiftTarget });
      startSession(operatorName.trim(), mode);
      router.push(mode === "sewing" ? ROUTES.DASHBOARD_SEWING : ROUTES.DASHBOARD_QUALITY);
    }
  }

  function back() {
    if (step === 1) {
      router.push(ROUTES.LOGIN);
      return;
    }
    setStep(s => (s - 1) as WizardStep);
  }

  const canProceed =
    step === 1 ? !!mode
    : step === 3 ? !!operatorName.trim()
    : true;

  const btnBg =
    !canProceed ? "rgba(59,130,246,0.18)"
    : step === 3 && mode === "sewing" ? "#22C55E"
    : "#3B82F6";

  const btnColor =
    !canProceed ? "#4A5A6A"
    : step === 3 && mode === "sewing" ? "#000"
    : "#fff";

  const btnShadow =
    !canProceed ? "none"
    : step === 3 && mode === "sewing" ? "0 0 24px rgba(34,197,94,0.4)"
    : "0 0 22px rgba(59,130,246,0.4)";

  return (
    <main className="flex flex-col" style={{ minHeight: "100vh", background: "#0B1017" }}>
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: "radial-gradient(circle, rgba(59,130,246,0.07) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
        }}
      />

      <header
        className="flex items-center justify-between shrink-0 relative z-10"
        style={{
          height: 60,
          padding: "0 40px",
          background: "rgba(19,27,38,0.9)",
          borderBottom: "1px solid #243044",
          backdropFilter: "blur(8px)",
        }}
      >
        <button
          type="button"
          onClick={back}
          className="flex items-center gap-1.5 font-display text-text-muted transition-colors duration-150 cursor-pointer"
          style={{ fontSize: 13, background: "none", border: "none" }}
          onMouseEnter={e => (e.currentTarget.style.color = "#E8ECF1")}
          onMouseLeave={e => (e.currentTarget.style.color = "#6B7A8D")}
        >
          <ChevronLeft size={15} />
          {step === 1 ? "Back to Login" : "Previous Step"}
        </button>

        <div className="flex items-center">
          {STEP_LABELS.map((label, i) => {
            const n = i + 1;
            const isActive = n === step;
            const isDone = n < step;
            return (
              <div key={label} className="flex items-center">
                <div className="flex items-center gap-2.5">
                  <div
                    className="flex items-center justify-center font-mono font-bold transition-all duration-300"
                    style={{
                      width: 26, height: 26, borderRadius: "50%", fontSize: 11,
                      background: isDone ? "#22C55E" : isActive ? "#3B82F6" : "#1A2536",
                      color: isDone ? "#000" : isActive ? "#fff" : "#6B7A8D",
                      border: `1px solid ${isDone ? "#22C55E" : isActive ? "#3B82F6" : "#243044"}`,
                      boxShadow: isActive ? "0 0 14px rgba(59,130,246,0.45)" : "none",
                    }}
                  >
                    {isDone ? <CheckCircle2 size={13} strokeWidth={2.5} /> : n}
                  </div>
                  <span
                    className="font-display"
                    style={{
                      fontSize: 13,
                      fontWeight: isActive ? 600 : 400,
                      color: isActive ? "#E8ECF1" : isDone ? "#6B7A8D" : "#3A4A5C",
                    }}
                  >
                    {label}
                  </span>
                </div>
                {i < 2 && (
                  <div
                    className="transition-all duration-300"
                    style={{
                      width: 48, height: 1,
                      margin: "0 16px",
                      background: isDone ? "#22C55E" : "#243044",
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>

        <span className="font-mono text-dim" style={{ fontSize: 10 }}>
          Step {step} of 3
        </span>
      </header>

      <div
        className="flex-1 overflow-y-auto relative z-10"
        style={{ padding: "52px 56px 32px" }}
      >
        <div
          className="w-full mx-auto animate-slide-up"
          style={{ maxWidth: step === 3 ? 1100 : 1320 }}
        >
          {step === 1 && (
            <StepModeSelect
              mode={mode}
              setMode={m => {
                setMode(m);
                setErrors({});
              }}
              error={errors.mode}
            />
          )}

          {step === 2 && mode && (
            <StepDevices
              mode={mode}
              activeSpecId={activeSpecId}
              setSpec={setSpec}
            />
          )}

          {step === 3 && mode && (
            <StepSession
              mode={mode}
              operatorName={operatorName}
              setOperator={v => {
                setOperator(v);
                setErrors(p => ({ ...p, operatorName: "" }));
              }}
              shiftTarget={shiftTarget}
              setTarget={setTarget}
              activeSpecId={activeSpecId}
              stationLabel={config.stationLabel}
              stationId={config.stationId}
              errors={errors}
            />
          )}

          <div className="flex items-center justify-between" style={{ marginTop: 44 }}>
            <button
              type="button"
              onClick={back}
              className="flex items-center gap-2 font-display text-text-muted transition-all duration-150 cursor-pointer"
              style={{
                height: 44, padding: "0 22px",
                background: "#1A2536",
                border: "1px solid #243044",
                borderRadius: 10, fontSize: 14,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.color = "#E8ECF1";
                e.currentTarget.style.borderColor = "#3A4A5C";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.color = "#6B7A8D";
                e.currentTarget.style.borderColor = "#243044";
              }}
            >
              <ChevronLeft size={14} />
              {step === 1 ? "Login" : "Back"}
            </button>

            <button
              type="button"
              onClick={next}
              disabled={!canProceed}
              className="flex items-center gap-2 font-display font-semibold transition-all duration-200 disabled:cursor-not-allowed"
              style={{
                height: step === 3 ? 50 : 44,
                padding: step === 3 ? "0 32px" : "0 24px",
                border: "none", borderRadius: 10,
                fontSize: step === 3 ? 15 : 14,
                cursor: canProceed ? "pointer" : "not-allowed",
                background: btnBg, color: btnColor,
                boxShadow: btnShadow,
              }}
            >
              {step === 3 ? "Start Session" : "Continue"}
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}