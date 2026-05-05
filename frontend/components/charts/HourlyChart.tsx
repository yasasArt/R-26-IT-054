// components/charts/HourlyChart.tsx
"use client";

import { useSewingStore } from "@/store/sewingStore";
import { format } from "date-fns";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

function groupByHour(records: { timestamp: Date | string }[]) {
  const groups: Record<string, number> = {};
  const now = format(new Date(), "HH:00");

  records.forEach((r) => {
    const h = format(new Date(r.timestamp), "HH:00");
    groups[h] = (groups[h] || 0) + 1;
  });

  return Object.entries(groups)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([hour, count]) => ({
      hour,
      count,
      current: hour === now,
    }));
}

const tooltipStyle = {
  background: "#1A2536",
  border: "1px solid #243044",
  borderRadius: 8,
  fontFamily: "var(--font-ibm-plex-mono)",
  fontSize: 10,
  color: "#E8ECF1",
  boxShadow: "0 4px 20px rgba(0,0,0,0.45)",
};

export function HourlyChart() {
  const { cycleHistory } = useSewingStore();
  const data = groupByHour(cycleHistory);

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{
        background: "#1A2536",
        border: "1px solid #243044",
        borderRadius: 12,
      }}
    >
      <div
        className="flex shrink-0 items-center justify-between px-5"
        style={{
          height: 50,
          background: "#131B26",
          borderBottom: "1px solid #243044",
        }}
      >
        <div>
          <div
            className="font-display font-semibold text-text-primary"
            style={{ fontSize: 13 }}
          >
            Hourly Output
          </div>
          <div
            className="font-mono text-text-muted"
            style={{ fontSize: 9 }}
          >
            Pieces per hour · current highlighted
          </div>
        </div>
      </div>

      <div style={{ flex: 1, padding: "12px 8px 8px", minHeight: 180 }}>
        {data.length === 0 ? (
          <div
            className="flex h-full items-center justify-center font-mono text-dim"
            style={{ fontSize: 11 }}
          >
            Collecting data…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 4, right: 12, bottom: 0, left: -14 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
                vertical={false}
              />

              <XAxis
                dataKey="hour"
                tick={{
                  fill: "#6B7A8D",
                  fontSize: 9,
                  fontFamily: "var(--font-ibm-plex-mono)",
                }}
                tickLine={false}
                axisLine={false}
              />

              <YAxis
                tick={{
                  fill: "#6B7A8D",
                  fontSize: 9,
                  fontFamily: "var(--font-ibm-plex-mono)",
                }}
                tickLine={false}
                axisLine={false}
              />

              <Tooltip
                contentStyle={tooltipStyle}
                cursor={{ fill: "rgba(255,255,255,0.03)" }}
                formatter={(value) => [`${value ?? 0} pcs`, ""]}
                isAnimationActive={false}
              />

              <Bar
                dataKey="count"
                radius={[3, 3, 0, 0]}
                maxBarSize={42}
                isAnimationActive={false}
              >
                {data.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.current ? "#3B82F6" : "rgba(59,130,246,0.28)"}
                    stroke={entry.current ? "rgba(59,130,246,0.6)" : "none"}
                    strokeWidth={1}
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