// components/layout/TopBar.tsx
"use client";
import { useState, useEffect } from "react";
import { format } from "date-fns";
import { Clock } from "lucide-react";
import { useWorkstationStore } from "@/store/workstationStore";
import { useSewingStore }      from "@/store/sewingStore";
import { useQualityStore }     from "@/store/qualityStore";
import { SessionTimer }        from "./SessionTimer";
import { cn }                  from "@/lib/utils";

function VBar() {
  return (
    <div className="shrink-0" style={{ width: 1, height: 16, background: "#243044" }} />
  );
}

function StatusDot({
  ok, pulse, label, value,
}: {
  ok: boolean; pulse?: boolean; label: string; value?: string;
}) {
  const color = ok ? "#22C55E" : "#EF4444";
  return (
    <div className="flex items-center gap-1.5">
      <div
        className={cn("rounded-full shrink-0", pulse && "animate-pulse-slow")}
        style={{ width: 6, height: 6, background: color, boxShadow: `0 0 5px ${color}` }}
      />
      <span className="font-mono text-text-muted" style={{ fontSize: 10 }}>
        {label}
      </span>
      {value && (
        <span className="font-mono" style={{ fontSize: 10, color: ok ? "#22C55E" : "#EF4444" }}>
          {value}
        </span>
      )}
    </div>
  );
}

export function TopBar() {
  const { config, sessionStartTime } = useWorkstationStore();
  const sewing  = useSewingStore();
  const quality = useQualityStore();
  const [clock, setClock] = useState("");

  useEffect(() => {
    const tick = () => setClock(format(new Date(), "HH:mm:ss"));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const mode = config.mode;
  const camStatus = mode === "sewing" ? sewing.cameraStatus : quality.cameraStatus;
  const camOk     = camStatus === "live" || camStatus === "calibrating";
  const iotOk     = mode === "sewing" && sewing.iotStatus === "connected";

  const modeColor = mode === "sewing" ? "#22C55E" : mode === "quality" ? "#3B82F6" : "#6B7A8D";
  const modeLabel =
    mode === "sewing"  ? "Sewing Operator Area"
    : mode === "quality" ? "Quality Checker Area"
    : "No Mode Selected";

  return (
    <header
      className="flex items-center px-5 gap-4 shrink-0"
      style={{ height: 56, background: "#1A2536", borderBottom: "1px solid #243044" }}
    >
      {/* Left: current mode label */}
      <div className="flex-1 flex items-center gap-2">
        <div
          className="rounded-full shrink-0 animate-pulse-slow"
          style={{ width: 6, height: 6, background: modeColor, boxShadow: `0 0 6px ${modeColor}` }}
        />
        <span
          className="font-mono font-semibold uppercase tracking-wider"
          style={{ fontSize: 10, color: modeColor }}
        >
          {modeLabel}
        </span>
      </div>

      {/* Right: status row */}
      <div className="flex items-center gap-3.5">
        {/* Camera */}
        <StatusDot ok={camOk} pulse={camOk} label="Camera" value={camOk ? "Live" : "Offline"} />

        {/* IoT — sewing only */}
        {mode === "sewing" && (
          <>
            <VBar />
            <StatusDot ok={iotOk} pulse={iotOk} label="IoT" value={iotOk ? "Paired" : "Offline"} />
          </>
        )}

        <VBar />

        {/* Session timer */}
        <SessionTimer startTime={sessionStartTime} showLabel />

        <VBar />

        {/* Wall clock */}
        <div className="flex items-center gap-1.5">
          <Clock size={11} className="text-text-muted shrink-0" />
          <span
            className="font-mono tabular-nums"
            style={{ fontSize: 14, color: clock ? "#E8ECF1" : "#3A4A5C" }}
          >
            {clock || "──:──:──"}
          </span>
        </div>

        <VBar />

        {/* Station chip */}
        <span
          className="font-mono text-text-muted rounded"
          style={{
            fontSize: 11, padding: "3px 10px",
            background: "#131B26", border: "1px solid #243044",
          }}
        >
          {config.stationId}
        </span>
      </div>
    </header>
  );
}