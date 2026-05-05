// components/dashboard/sewing/OperatorStatusCard.tsx
"use client";
import { useEffect, useState } from "react";
import { useSewingStore } from "@/store/sewingStore";
import { formatDuration } from "@/lib/utils";
import type { OperatorStatus } from "@/lib/types";

const CFG: Record<OperatorStatus, { label: string; icon: string; color: string; bg: string; border: string; desc: string }> = {
  active:   { label: "ACTIVE",   icon: "▶", color: "#22C55E", bg: "rgba(34,197,94,0.08)",   border: "rgba(34,197,94,0.22)",   desc: "Producing normally"     },
  idle:     { label: "IDLE",     icon: "⏸", color: "#6B7A8D", bg: "rgba(107,122,141,0.08)", border: "rgba(107,122,141,0.22)", desc: "Waiting for material"   },
  rework:   { label: "REWORK",   icon: "↩", color: "#FACC15", bg: "rgba(250,204,21,0.08)",  border: "rgba(250,204,21,0.22)",  desc: "Fixing defective piece" },
  downtime: { label: "DOWNTIME", icon: "⛔", color: "#EF4444", bg: "rgba(239,68,68,0.08)",   border: "rgba(239,68,68,0.22)",   desc: "Machine stopped"        },
};

export function OperatorStatusCard() {
  const { operatorStatus, totalReworkCount } = useSewingStore();
  const cfg = CFG[operatorStatus];
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    let seconds = 0;
    const id = window.setInterval(() => { seconds += 1; setElapsedSeconds(seconds); }, 1000);
    return () => window.clearInterval(id);
  }, [operatorStatus]);

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{
        background: "#1A2536",
        border: `1px solid ${cfg.border}`,
        borderRadius: 12,
        boxShadow: operatorStatus === "downtime" ? "0 0 20px rgba(239,68,68,0.1)" : operatorStatus === "rework" ? "0 0 16px rgba(250,204,21,0.08)" : "none",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 shrink-0" style={{ height: 48, background: "#131B26", borderBottom: `1px solid ${cfg.border}` }}>
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>Operator Status</span>
        <div className="animate-pulse-slow rounded-full" style={{ width: 7, height: 7, background: cfg.color, boxShadow: `0 0 6px ${cfg.color}` }} />
      </div>

      {/* Body — increased padding + gap */}
      <div style={{ padding: "16px 18px", flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
        <div className="flex items-center gap-3 rounded-lg" style={{ padding: "11px 14px", background: cfg.bg, border: `1px solid ${cfg.border}` }}>
          <span className="font-mono shrink-0" style={{ fontSize: 18, color: cfg.color, lineHeight: 1 }}>{cfg.icon}</span>
          <div>
            <div className="font-mono font-bold" style={{ fontSize: 13, color: cfg.color, letterSpacing: "0.06em" }}>{cfg.label}</div>
            <div className="font-mono text-text-muted" style={{ fontSize: 9, marginTop: 2 }}>{cfg.desc}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 7, padding: "11px 13px" }}>
            <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 5 }}>Duration</div>
            <div className="font-mono font-semibold" style={{ fontSize: 13, color: cfg.color }}>{formatDuration(elapsedSeconds)}</div>
          </div>
          <div style={{ background: "#0B1017", border: "1px solid #243044", borderRadius: 7, padding: "11px 13px" }}>
            <div className="font-mono text-dim uppercase" style={{ fontSize: 7.5, letterSpacing: "0.09em", marginBottom: 5 }}>Reworks</div>
            <div className="font-mono font-semibold text-warning" style={{ fontSize: 13 }}>{totalReworkCount}</div>
          </div>
        </div>
      </div>
    </div>
  );
}