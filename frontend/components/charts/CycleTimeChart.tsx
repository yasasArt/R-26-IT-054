// components/charts/CycleTimeChart.tsx
"use client";
import { useSewingStore } from "@/store/sewingStore";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { CYCLE_TIME } from "@/lib/constants";

const TT = { background: "#1A2536", border: "1px solid #243044", borderRadius: 8, fontFamily: "var(--font-ibm-plex-mono)", fontSize: 10, color: "#E8ECF1", boxShadow: "0 4px 20px rgba(0,0,0,0.45)" };

export function CycleTimeChart() {
  const { cycleHistory } = useSewingStore();
  const data = cycleHistory.slice(-30).map(r => ({ piece: `#${r.pieceNumber}`, cycleTime: r.durationSeconds }));

  return (
    <div className="flex flex-col overflow-hidden" style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}>
      <div className="flex items-center justify-between px-5 shrink-0" style={{ height: 54, background: "#131B26", borderBottom: "1px solid #243044" }}>
        <div>
          <div className="font-display font-semibold text-text-primary" style={{ fontSize: 13 }}>Cycle Time Trend</div>
          <div className="font-mono text-text-muted" style={{ fontSize: 9, marginTop: 2 }}>Seconds per piece · target ≤ {CYCLE_TIME.TARGET_SECONDS}s</div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex items-center gap-1.5"><div style={{ width: 14, height: 1, borderTop: "1px dashed #22C55E" }} /><span className="font-mono text-success" style={{ fontSize: 8 }}>Target</span></div>
          <div className="flex items-center gap-1.5"><div style={{ width: 14, height: 1, borderTop: "1px dashed #FACC15" }} /><span className="font-mono text-warning" style={{ fontSize: 8 }}>Warn</span></div>
        </div>
      </div>
      <div style={{ flex: 1, padding: "16px 12px 10px", minHeight: 188 }}>
        {data.length < 2 ? (
          <div className="flex items-center justify-center h-full font-mono text-dim" style={{ fontSize: 11 }}>Collecting data…</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 14, bottom: 0, left: -14 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis dataKey="piece" tick={{ fill: "#6B7A8D", fontSize: 9, fontFamily: "var(--font-ibm-plex-mono)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "#6B7A8D", fontSize: 9, fontFamily: "var(--font-ibm-plex-mono)" }} tickLine={false} axisLine={false} unit="s" />
              <Tooltip contentStyle={TT} labelStyle={{ color: "#6B7A8D", marginBottom: 4 }} formatter={(v) => [`${v ?? "—"}s`, "Cycle"]} isAnimationActive={false} />
              <ReferenceLine y={CYCLE_TIME.TARGET_SECONDS}  stroke="#22C55E" strokeDasharray="4 3" strokeOpacity={0.5} strokeWidth={1} />
              <ReferenceLine y={CYCLE_TIME.WARNING_SECONDS} stroke="#FACC15" strokeDasharray="4 3" strokeOpacity={0.35} strokeWidth={1} />
              <Line type="monotone" dataKey="cycleTime" stroke="#3B82F6" strokeWidth={2} dot={{ fill: "#3B82F6", r: 2.5, strokeWidth: 0 }} activeDot={{ r: 5, fill: "#3B82F6", strokeWidth: 0 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}