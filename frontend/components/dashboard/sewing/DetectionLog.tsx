// components/dashboard/sewing/DetectionLog.tsx
"use client";
import { useState } from "react";
import { useSewingStore } from "@/store/sewingStore";
import { formatTime } from "@/lib/utils";
import { CYCLE_TIME } from "@/lib/constants";

const PAGE = 8;

export function DetectionLog() {
  const { detectionLog } = useSewingStore();
  const [page, setPage]  = useState(0);

  const totalPages = Math.ceil(detectionLog.length / PAGE);
  const rows       = detectionLog.slice(page * PAGE, (page + 1) * PAGE);

  const cycleColor  = (s: number) => s <= CYCLE_TIME.TARGET_SECONDS ? "#22C55E" : s <= CYCLE_TIME.WARNING_SECONDS ? "#FACC15" : "#EF4444";
  const statusColor = (s: string) => s === "active" ? "#22C55E" : s === "rework" ? "#FACC15" : "#EF4444";

  return (
    <div className="overflow-hidden" style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 shrink-0" style={{ height: 48, background: "#131B26", borderBottom: "1px solid #243044" }}>
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>Detection Log</span>
        <span className="font-mono text-dim" style={{ fontSize: 9 }}>{detectionLog.length} records</span>
      </div>

      {/* Column headers */}
      <div className="grid font-mono text-dim uppercase px-5" style={{ fontSize: 8, letterSpacing: "0.1em", gridTemplateColumns: "48px 90px 70px 84px 56px 1fr", gap: "0 12px", borderBottom: "1px solid #243044", padding: "10px 20px" }}>
        <span>#</span><span>Time</span><span>Cycle</span><span>Status</span><span>Conf</span><span>Signals</span>
      </div>

      {/* Rows */}
      <div className="overflow-y-auto" style={{ maxHeight: 260 }}>
        {rows.length === 0 && (
          <div className="flex items-center justify-center font-mono text-dim" style={{ height: 64, fontSize: 11 }}>No detections yet</div>
        )}
        {rows.map((ev, i) => (
          <div key={ev.id} className="grid items-center font-mono" style={{ gridTemplateColumns: "48px 90px 70px 84px 56px 1fr", gap: "0 12px", fontSize: 11, borderBottom: i < rows.length - 1 ? "1px solid rgba(36,48,68,0.3)" : "none", background: i === 0 && page === 0 ? "rgba(34,197,94,0.03)" : "transparent", padding: "11px 20px" }}>
            <span className="font-semibold text-text-primary">#{ev.pieceNumber}</span>
            <span className="text-text-muted">{formatTime(new Date(ev.timestamp))}</span>
            <span className="font-semibold" style={{ color: cycleColor(ev.cycleTimeSeconds) }}>{ev.cycleTimeSeconds}s</span>
            <span style={{ fontSize: 9, letterSpacing: "0.06em", textTransform: "uppercase", color: statusColor(ev.operatorStatus) }}>{ev.operatorStatus}</span>
            <span className="text-text-muted">{(ev.confidenceScore * 100).toFixed(0)}%</span>
            <div className="flex items-center gap-1">
              {[{ lbl: "A", active: ev.signalA, color: "#22C55E" }, { lbl: "B", active: ev.signalB, color: "#3B82F6" }].map(sig => (
                <span key={sig.lbl} className="font-mono" style={{ fontSize: 8, padding: "2px 6px", borderRadius: 3, background: sig.active ? `${sig.color}18` : "rgba(255,255,255,0.03)", border: `1px solid ${sig.active ? `${sig.color}50` : "#243044"}`, color: sig.active ? sig.color : "#3A4A5C" }}>{sig.lbl}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-5 py-3" style={{ borderTop: "1px solid #243044" }}>
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="font-mono text-text-muted transition-colors hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer" style={{ fontSize: 10, background: "none", border: "none" }}>← Prev</button>
          <span className="font-mono text-dim" style={{ fontSize: 9 }}>Page {page + 1} of {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} className="font-mono text-text-muted transition-colors hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer" style={{ fontSize: 10, background: "none", border: "none" }}>Next →</button>
        </div>
      )}
    </div>
  );
}