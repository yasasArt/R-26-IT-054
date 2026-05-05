// components/layout/TopBar.tsx
"use client";
import { useState, useEffect } from "react";
import { format } from "date-fns";
import { Clock } from "lucide-react";
import { useWorkstationStore } from "@/store/workstationStore";
import { useSewingStore } from "@/store/sewingStore";
import { useQualityStore } from "@/store/qualityStore";
import { ModeIndicator } from "./ModeIndicator";
import { SessionTimer } from "./SessionTimer";
import { StatusDot } from "@/components/ui/StatusDot";
import { cn } from "@/lib/utils";
import type { DotStatus } from "@/components/ui/StatusDot";

function Divider() {
  return <div className="w-px h-4 bg-card-border flex-shrink-0" />;
}

export function TopBar() {
  const { config, sessionStartTime } = useWorkstationStore();
  const sewingStore = useSewingStore();
  const qualityStore = useQualityStore();

  const [clock, setClock] = useState("");

  useEffect(() => {
    const tick = () => setClock(format(new Date(), "HH:mm:ss"));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const mode = config.mode;

  // Derive camera status dot
  const rawCameraStatus =
    mode === "sewing" ? sewingStore.cameraStatus : qualityStore.cameraStatus;

  const cameraDotStatus: DotStatus =
    rawCameraStatus === "live" ? "live"
    : rawCameraStatus === "calibrating" ? "calibrating"
    : "disconnected";

  // IoT dot — sewing only
  const iotDotStatus: DotStatus | null =
    mode === "sewing"
      ? sewingStore.iotStatus === "connected"
        ? "live"
        : "disconnected"
      : null;

  return (
    <header className="h-14 bg-card border-b border-card-border flex items-center px-5 gap-4 flex-shrink-0">
      {/* Mode badge — left anchor */}
      <div className="flex-1 flex items-center">
        {mode && <ModeIndicator mode={mode} size="sm" />}
      </div>

      {/* Right: status row */}
      <div className="flex items-center gap-3.5">
        {/* Camera */}
        <div className="flex items-center gap-1.5">
          <StatusDot status={cameraDotStatus} size="sm" />
          <span className="text-[11px] font-mono text-text-muted">
            {config.cameraLabel}
          </span>
        </div>

        {/* IoT — sewing only */}
        {iotDotStatus && (
          <>
            <Divider />
            <div className="flex items-center gap-1.5">
              <StatusDot status={iotDotStatus} size="sm" />
              <span className="text-[11px] font-mono text-text-muted">
                IoT
              </span>
            </div>
          </>
        )}

        <Divider />

        {/* Session timer */}
        <SessionTimer
          startTime={sessionStartTime}
          showLabel
        />

        <Divider />

        {/* Wall clock */}
        <div className="flex items-center gap-1.5">
          <Clock size={11} className="text-text-muted flex-shrink-0" />
          <span
            className={cn(
              "text-sm font-mono tabular-nums",
              clock ? "text-text-primary" : "text-dim"
            )}
          >
            {clock || "──:──:──"}
          </span>
        </div>

        <Divider />

        {/* Station ID chip */}
        <span className="text-[11px] font-mono text-text-muted bg-surface border border-card-border rounded px-2 py-0.5">
          {config.stationId}
        </span>
      </div>
    </header>
  );
}