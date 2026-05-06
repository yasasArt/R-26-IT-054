// components/dashboard/sewing/DowntimeCard.tsx
"use client";
import { useEffect, useState } from "react";
import { useSewingStore } from "@/store/sewingStore";
import { formatDuration } from "@/lib/utils";

export function DowntimeCard() {
  const { downtimeActive, downtimeStartTime, totalDowntimeSeconds, iotEvents } = useSewingStore();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!downtimeActive || !downtimeStartTime) return;
    const startTime = new Date(downtimeStartTime).getTime();
    const id = window.setInterval(() => { setElapsed(Math.floor((Date.now() - startTime) / 1000)); }, 1000);
    return () => window.clearInterval(id);
  }, [downtimeActive, downtimeStartTime]);

  const displayedElapsed = downtimeActive ? elapsed : 0;
  const events       = iotEvents.filter(e => e.type === "downtime_triggered").length;
  const totalCurrent = totalDowntimeSeconds + displayedElapsed;

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ background: "var(--card)", border: `1px solid ${downtimeActive ? "rgba(239,68,68,0.4)" : "var(--card-border)"}`, borderRadius: 12, boxShadow: downtimeActive ? "0 0 20px rgba(239,68,68,0.12)" : "none", transition: "border-color 0.3s, box-shadow 0.3s" }}
    >
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between px-4" style={{ height: 48, background: "var(--surface)", borderBottom: `1px solid ${downtimeActive ? "rgba(239,68,68,0.2)" : "var(--card-border)"}` }}>
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>Downtime</span>
        <div className={downtimeActive ? "animate-pulse-slow rounded-full" : "rounded-full"} style={{ width: 7, height: 7, background: downtimeActive ? "#EF4444" : "var(--dim)", boxShadow: downtimeActive ? "0 0 6px #EF4444" : "none" }} />
      </div>

      {/* Body */}
      <div style={{ padding: "16px 18px", flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
        <div className="flex items-center justify-between rounded-lg transition-all duration-300" style={{ padding: "11px 14px", background: downtimeActive ? "rgba(239,68,68,0.08)" : "rgba(255,255,255,0.02)", border: `1px solid ${downtimeActive ? "rgba(239,68,68,0.25)" : "var(--card-border)"}` }}>
          <div className="font-mono font-bold" style={{ fontSize: 13, color: downtimeActive ? "#EF4444" : "var(--dim)" }}>{downtimeActive ? "STOPPED" : "Running"}</div>
          {downtimeActive && <div className="font-mono font-bold text-danger" style={{ fontSize: 13 }}>{formatDuration(displayedElapsed)}</div>}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div style={{ background: "var(--bg)", border: "1px solid var(--card-border)", borderRadius: 7, padding: "11px 13px" }}>
            <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 5 }}>Total Lost</div>
            <div className="font-mono font-bold" style={{ fontSize: 13, color: totalCurrent > 600 ? "#EF4444" : "var(--muted)" }}>{formatDuration(totalCurrent)}</div>
          </div>
          <div style={{ background: "var(--bg)", border: "1px solid var(--card-border)", borderRadius: 7, padding: "11px 13px" }}>
            <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 5 }}>Events</div>
            <div className="font-mono font-bold text-danger" style={{ fontSize: 18, lineHeight: 1 }}>{events}</div>
          </div>
        </div>
      </div>
    </div>
  );
}