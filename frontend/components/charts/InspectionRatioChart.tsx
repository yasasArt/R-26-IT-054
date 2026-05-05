// components/charts/InspectionRatioChart.tsx
"use client";
import { useQualityStore } from "@/store/qualityStore";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
} from "recharts";

const TT = {
  background: "#1A2536", border: "1px solid #243044", borderRadius: 8,
  fontFamily: "var(--font-ibm-plex-mono)", fontSize: 10, color: "#E8ECF1",
  boxShadow: "0 4px 20px rgba(0,0,0,0.45)",
};

const SLICES = [
  { key: "PASS",     color: "#22C55E" },
  { key: "REWORK",   color: "#FACC15" },
  { key: "MISMATCH", color: "#EF4444" },
];

export function InspectionRatioChart() {
  const { approvedCount, reworkCount, mismatchCount } = useQualityStore();
  const total = approvedCount + reworkCount + mismatchCount;

  const counts = { PASS: approvedCount, REWORK: reworkCount, MISMATCH: mismatchCount };

  const data = total === 0
    ? [{ name: "Pending", value: 1, color: "#3A4A5C" }]
    : SLICES.filter(s => counts[s.key as keyof typeof counts] > 0).map(s => ({
        name:  s.key,
        value: counts[s.key as keyof typeof counts],
        color: s.color,
      }));

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}
    >
      <div
        className="flex items-center justify-between px-5 shrink-0"
        style={{ height: 54, background: "#131B26", borderBottom: "1px solid #243044" }}
      >
        <div>
          <div className="font-display font-semibold text-text-primary" style={{ fontSize: 13 }}>
            Inspection Results
          </div>
          <div className="font-mono text-text-muted" style={{ fontSize: 9, marginTop: 2 }}>
            PASS / REWORK / MISMATCH ratio
          </div>
        </div>
        <div className="font-mono text-dim" style={{ fontSize: 9 }}>{total} total</div>
      </div>

      <div style={{ flex: 1, padding: "12px 8px 8px", minHeight: 170 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%" cy="50%"
              innerRadius="42%" outerRadius="68%"
              paddingAngle={2}
              dataKey="value"
              isAnimationActive={false}
            >
              {data.map((entry, i) => (
                <Cell
                  key={`cell-${i}`}
                  fill={entry.color}
                  stroke={`${entry.color}40`}
                  strokeWidth={1}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={TT}
              formatter={(v: unknown) => [String(v), ""]}
              isAnimationActive={false}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div
        className="flex items-center justify-center gap-5 pb-3"
        style={{ borderTop: "1px solid rgba(36,48,68,0.4)" }}
      >
        {[
          { l: "PASS",     c: "#22C55E", v: approvedCount  },
          { l: "REWORK",   c: "#FACC15", v: reworkCount    },
          { l: "MISMATCH", c: "#EF4444", v: mismatchCount  },
        ].map(({ l, c, v }) => (
          <div key={l} className="flex items-center gap-1.5">
            <div className="rounded-sm" style={{ width: 8, height: 8, background: c }} />
            <span className="font-mono text-text-muted" style={{ fontSize: 9 }}>{l}</span>
            <span className="font-mono font-semibold text-text-primary" style={{ fontSize: 9 }}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}