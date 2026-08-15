"use client";
import { Activity } from "lucide-react";

export interface LineData {
  id: string;
  name: string;
  status: "running" | "idle" | "stopped";
  output: number;
  target: number;
  operator: string;
  trend: number[];
}

// TODO: replace with a real fetch (e.g. fetchLineStatus() in lib/api.ts) once
// the backend exposes per-line throughput. Shape matches LineData above.
const LINES: LineData[] = [
  { id: "L01", name: "Line 01 — Shirts", status: "running", output: 312, target: 400, operator: "K. Perera", trend: [4, 6, 5, 7, 8, 6, 9, 10, 8, 11] },
  { id: "L02", name: "Line 02 — Trousers", status: "running", output: 278, target: 350, operator: "N. Silva", trend: [3, 4, 4, 5, 6, 5, 6, 7, 6, 8] },
  { id: "L03", name: "Line 03 — Vision Floor", status: "running", output: 124, target: 200, operator: "System (AI)", trend: [2, 3, 3, 4, 5, 5, 6, 6, 7, 7] },
  { id: "L04", name: "Line 04 — Jackets", status: "idle", output: 0, target: 150, operator: "Unassigned", trend: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
];

const STATUS_STYLES: Record<LineData["status"], string> = {
  running: "text-brandGreen bg-brandGreen/10 border-brandGreen/30",
  idle: "text-brandAmber bg-brandAmber/10 border-brandAmber/30",
  stopped: "text-brandRed bg-brandRed/10 border-brandRed/30",
};

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const max = Math.max(...data, 1);
  const points = data
    .map((v, i) => `${(i / (data.length - 1)) * 100},${100 - (v / max) * 100}`)
    .join(" ");
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-16 h-6 flex-shrink-0">
      <polyline fill="none" stroke={color} strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" points={points} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export default function ProductionLineMonitor({ lines = LINES }: { lines?: LineData[] }) {
  return (
    <div className="bg-panel border border-borderStrong rounded-lg flex flex-col">
      <div className="px-5 py-4 border-b border-borderSoft flex items-center gap-2">
        <Activity size={14} className="text-brandBlue" />
        <h3 className="text-textDim font-bold text-[11px] tracking-widest uppercase">Production Lines</h3>
      </div>
      <div className="flex flex-col divide-y divide-borderSoft">
        {lines.map((line) => (
          <div key={line.id} className="px-5 py-3.5 flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-medium text-[13px] text-textMain truncate">{line.name}</span>
                <span className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded border flex-shrink-0 ${STATUS_STYLES[line.status]}`}>
                  {line.status}
                </span>
              </div>
              <div className="text-[10px] text-textFaint font-mono">{line.operator}</div>
              <div className="mt-1.5 h-1 bg-borderSoft rounded-full overflow-hidden">
                <div
                  className="h-full bg-brandBlue rounded-full transition-[width]"
                  style={{ width: `${Math.min((line.output / line.target) * 100, 100)}%` }}
                />
              </div>
            </div>
            <Sparkline data={line.trend} color={line.status === "running" ? "#3fe0a1" : "#58655e"} />
            <div className="text-right font-mono flex-shrink-0">
              <div className="text-textMain text-sm font-bold">{line.output}</div>
              <div className="text-textFaint text-[9px]">/ {line.target}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
