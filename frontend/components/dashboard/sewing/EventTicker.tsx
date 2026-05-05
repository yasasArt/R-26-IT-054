// components/dashboard/sewing/EventTicker.tsx
"use client";
import { useEffect, useRef } from "react";
import { useSewingStore } from "@/store/sewingStore";
import { formatTime } from "@/lib/utils";
import type { IDetectionEvent, IIoTEvent } from "@/lib/types";

type TickEvent = {
  id: string; time: Date; label: string; kind: "det" | "rework" | "down";
};

const KIND_COLOR = { det: "#22C55E", rework: "#FACC15", down: "#EF4444" };

function buildEvents(dets: IDetectionEvent[], iot: IIoTEvent[]): TickEvent[] {
  return [
    ...dets.slice(0, 10).map(d => ({
      id: d.id, time: new Date(d.timestamp), kind: "det" as const,
      label: `Piece #${d.pieceNumber} detected — ${d.cycleTimeSeconds}s · conf ${(d.confidenceScore * 100).toFixed(0)}%`,
    })),
    ...iot.slice(0, 8).map(e => ({
      id: e.id, time: new Date(e.timestamp),
      kind: (e.type.includes("rework") ? "rework" : "down") as TickEvent["kind"],
      label:
        e.type === "rework_triggered"   ? "Rework triggered by operator"
      : e.type === "rework_resolved"    ? `Rework resolved — ${e.durationSeconds ?? 0}s`
      : e.type === "downtime_triggered" ? "Downtime started — machine stopped"
      :                                   `Downtime resolved — ${e.durationSeconds ?? 0}s`,
    })),
  ]
    .sort((a, b) => b.time.getTime() - a.time.getTime())
    .slice(0, 14);
}

export function EventTicker() {
  const { detectionLog, iotEvents } = useSewingStore();
  const listRef = useRef<HTMLDivElement>(null);
  const events  = buildEvents(detectionLog, iotEvents);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = 0;
  }, [detectionLog.length]);

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 shrink-0"
        style={{ height: 44, background: "#131B26", borderBottom: "1px solid #243044" }}
      >
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
          Production Events
        </span>
        <div className="flex items-center gap-1.5">
          <div
            className="rounded-full animate-pulse-slow"
            style={{ width: 5, height: 5, background: "#22C55E", boxShadow: "0 0 5px #22C55E" }}
          />
          <span className="font-mono text-success" style={{ fontSize: 9 }}>Live</span>
        </div>
      </div>

      {/* Event list */}
      <div
        ref={listRef}
        className="overflow-y-auto"
        style={{ flex: 1 }}
      >
        {events.length === 0 && (
          <div
            className="flex items-center justify-center font-mono text-dim"
            style={{ height: 60, fontSize: 11 }}
          >
            Waiting for events…
          </div>
        )}
        {events.map((ev, i) => (
          <div
            key={ev.id}
            className="flex items-start gap-3 px-4 py-2.5"
            style={{
              borderBottom: i < events.length - 1 ? "1px solid rgba(36,48,68,0.35)" : "none",
              background: i === 0 ? "rgba(255,255,255,0.015)" : "transparent",
            }}
          >
            <div
              className="rounded-full shrink-0"
              style={{
                width: 5, height: 5, marginTop: 5,
                background: KIND_COLOR[ev.kind],
                boxShadow: `0 0 5px ${KIND_COLOR[ev.kind]}80`,
              }}
            />
            <div className="flex-1 min-w-0">
              <div className="font-display text-text-primary truncate" style={{ fontSize: 12 }}>
                {ev.label}
              </div>
            </div>
            <span className="font-mono text-dim shrink-0" style={{ fontSize: 9 }}>
              {formatTime(ev.time)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}