// components/dashboard/sewing/ShiftSummaryCard.tsx
"use client";
import { useState, useEffect } from "react";
import { useWorkstationStore } from "@/store/workstationStore";
import { useSewingStore } from "@/store/sewingStore";
import { formatDuration, formatTime } from "@/lib/utils";
import { differenceInSeconds, addSeconds } from "date-fns";

export function ShiftSummaryCard() {
  const { sessionStartTime, config } = useWorkstationStore();
  const { pieceCount, averageCycleTimeSeconds, totalDowntimeSeconds } = useSewingStore();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!sessionStartTime) return;
    const tick = () => setElapsed(differenceInSeconds(new Date(), new Date(sessionStartTime)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [sessionStartTime]);

  const target    = config.shiftTarget;
  const pct       = Math.min((pieceCount / target) * 100, 100);
  const pph       = elapsed > 0 ? Math.round((pieceCount / elapsed) * 3600) : 0;
  const remaining = Math.max(target - pieceCount, 0);
  const secNeeded = remaining > 0 && averageCycleTimeSeconds > 0 ? remaining * averageCycleTimeSeconds : 0;
  const projEnd   = secNeeded > 0 ? addSeconds(new Date(), secNeeded) : null;
  const barColor  = pct >= 100 ? "#22C55E" : pct >= 75 ? "#3B82F6" : "#FACC15";

  return (
    <div className="flex flex-col overflow-hidden" style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 shrink-0" style={{ height: 48, background: "#131B26", borderBottom: "1px solid #243044" }}>
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>Shift Summary</span>
        {sessionStartTime && <span className="font-mono text-dim" style={{ fontSize: 9 }}>{formatTime(new Date(sessionStartTime))}</span>}
      </div>

      {/* Body */}
      <div style={{ padding: "16px 18px", flex: 1, display: "flex", flexDirection: "column", gap: 14 }}>
        {/* Target progress */}
        <div>
          <div className="flex items-end justify-between" style={{ marginBottom: 10 }}>
            <div>
              <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 4 }}>Production Target</div>
              <div style={{ lineHeight: 1 }}>
                <span key={pieceCount} className="font-mono font-bold text-text-primary" style={{ fontSize: 28, animation: "countUp 0.3s ease-out", letterSpacing: "-0.02em" }}>{pieceCount}</span>
                <span className="font-mono text-text-muted" style={{ fontSize: 13, marginLeft: 4 }}>/ {target}</span>
              </div>
            </div>
            <div className="font-mono font-bold" style={{ fontSize: 20, color: pct >= 100 ? "#22C55E" : pct >= 75 ? "#3B82F6" : "#E8ECF1" }}>{pct.toFixed(0)}%</div>
          </div>
          <div className="rounded-full overflow-hidden" style={{ height: 6, background: "#243044" }}>
            <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: barColor, boxShadow: pct >= 100 ? "0 0 10px rgba(34,197,94,0.5)" : "none" }} />
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-2">
          {[
            { l: "Elapsed",   v: formatDuration(elapsed), c: "#E8ECF1" },
            { l: "Rate/hr",   v: `${pph} pcs`,            c: "#3B82F6" },
            { l: "Downtime",  v: formatDuration(totalDowntimeSeconds), c: totalDowntimeSeconds > 600 ? "#EF4444" : "#6B7A8D" },
            { l: "Proj. End", v: projEnd ? formatTime(projEnd) : "On track", c: "#22C55E" },
          ].map(({ l, v, c }) => (
            <div key={l} style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 7, padding: "11px 13px" }}>
              <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 5 }}>{l}</div>
              <div className="font-mono font-semibold" style={{ fontSize: 12, color: c }}>{v}</div>
            </div>
          ))}
        </div>

        {remaining > 0 ? (
          <div className="text-center rounded-lg font-mono" style={{ padding: "9px 12px", fontSize: 11, background: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.18)", color: "#6B7A8D" }}>
            <span className="text-accent font-semibold">{remaining}</span> pieces remaining
          </div>
        ) : (
          <div className="text-center rounded-lg font-mono font-bold text-success" style={{ padding: "9px 12px", fontSize: 11, background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.28)" }}>
            ✓ Target Reached
          </div>
        )}
      </div>
    </div>
  );
}