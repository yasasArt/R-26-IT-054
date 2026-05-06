// components/charts/SizeDistributionChart.tsx
"use client";
import { useQualityStore } from "@/store/qualityStore";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts";

const TT = {
  background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 8,
  fontFamily: "var(--font-ibm-plex-mono)", fontSize: 10, color: "var(--text)",
  boxShadow: "0 4px 20px rgba(0,0,0,0.45)",
};

const SIZE_COLORS: Record<string, string> = {
  S: "#3B82F6", M: "#22C55E", L: "#FACC15", XL: "#F97316",
};

export function SizeDistributionChart() {
  const { inspectionLog } = useQualityStore();

  const counts: Record<string, number> = { S: 0, M: 0, L: 0, XL: 0 };
  inspectionLog.forEach(rec => {
    const sz = rec.garmentAnalysis.sizeMeasurement.detectedSize;
    if (sz in counts) counts[sz]++;
  });

  const data = Object.entries(counts).map(([size, count]) => ({
    size, count, color: SIZE_COLORS[size] ?? "var(--muted)",
  }));

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 12 }}
    >
      <div
        className="flex items-center justify-between px-5 shrink-0"
        style={{ height: 54, background: "var(--surface)", borderBottom: "1px solid var(--card-border)" }}
      >
        <div>
          <div className="font-display font-semibold text-text-primary" style={{ fontSize: 13 }}>
            Size Distribution
          </div>
          <div className="font-mono text-text-muted" style={{ fontSize: 9, marginTop: 2 }}>
            Detected sizes across inspections
          </div>
        </div>
      </div>

      <div style={{ flex: 1, padding: "16px 12px 10px", minHeight: 188 }}>
        {inspectionLog.length === 0 ? (
          <div className="flex items-center justify-center h-full font-mono text-dim" style={{ fontSize: 11 }}>
            Collecting data…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 14, bottom: 0, left: -14 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
                vertical={false}
              />
              <XAxis
                dataKey="size"
                tick={{ fill: "var(--muted)", fontSize: 12, fontFamily: "var(--font-ibm-plex-mono)", fontWeight: 600 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fill: "var(--muted)", fontSize: 9, fontFamily: "var(--font-ibm-plex-mono)" }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={TT}
                cursor={{ fill: "rgba(255,255,255,0.03)" }}
                formatter={(v: unknown) => [String(v), "pcs"]}
                isAnimationActive={false}
              />
              <Bar
                dataKey="count"
                radius={[4, 4, 0, 0]}
                maxBarSize={52}
                isAnimationActive={false}
              >
                {data.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.color}
                    fillOpacity={0.82}
                    stroke={entry.color}
                    strokeWidth={0}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}