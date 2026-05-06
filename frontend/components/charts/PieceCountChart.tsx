// components/charts/PieceCountChart.tsx
"use client";
import { useSewingStore } from "@/store/sewingStore";
import { format } from "date-fns";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const TT = { background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 8, fontFamily: "var(--font-ibm-plex-mono)", fontSize: 10, color: "var(--text)", boxShadow: "0 4px 20px rgba(0,0,0,0.45)" };

export function PieceCountChart() {
  const { cycleHistory } = useSewingStore();
  const data = cycleHistory.map((r, i) => ({ time: format(new Date(r.timestamp), "HH:mm"), pieces: i + 1 }));

  return (
    <div className="flex flex-col overflow-hidden" style={{ background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 12 }}>
      <div className="flex items-center justify-between px-5 shrink-0" style={{ height: 54, background: "var(--surface)", borderBottom: "1px solid var(--card-border)" }}>
        <div>
          <div className="font-display font-semibold text-text-primary" style={{ fontSize: 13 }}>Production Accumulation</div>
          <div className="font-mono text-text-muted" style={{ fontSize: 9, marginTop: 2 }}>Cumulative pieces completed this shift</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded" style={{ width: 20, height: 2, background: "#3B82F6" }} />
          <span className="font-mono text-text-muted" style={{ fontSize: 9 }}>Pieces</span>
        </div>
      </div>
      <div style={{ flex: 1, padding: "16px 12px 10px", minHeight: 188 }}>
        {data.length < 2 ? (
          <div className="flex items-center justify-center h-full font-mono text-dim" style={{ fontSize: 11 }}>Collecting data…</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 14, bottom: 0, left: -14 }}>
              <defs>
                <linearGradient id="pieceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#3B82F6" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fill: "var(--muted)", fontSize: 9, fontFamily: "var(--font-ibm-plex-mono)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "var(--muted)", fontSize: 9, fontFamily: "var(--font-ibm-plex-mono)" }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={TT} labelStyle={{ color: "var(--muted)", marginBottom: 4 }} itemStyle={{ color: "#3B82F6" }} formatter={(v) => [`${v ?? "—"} pcs`, ""]} isAnimationActive={false} />
              <Area type="monotone" dataKey="pieces" stroke="#3B82F6" strokeWidth={2} fill="url(#pieceGrad)" dot={false} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}