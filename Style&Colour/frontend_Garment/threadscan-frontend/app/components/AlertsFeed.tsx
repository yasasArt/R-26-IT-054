"use client";
import { AlertTriangle, AlertOctagon, Info } from "lucide-react";

export interface AlertItem {
  id: string;
  severity: "info" | "warning" | "critical";
  message: string;
  time: string;
}

const ICON = { critical: AlertOctagon, warning: AlertTriangle, info: Info } as const;
const COLOR = {
  critical: "text-brandRed border-l-brandRed",
  warning: "text-brandAmber border-l-brandAmber",
  info: "text-brandBlue border-l-brandBlue",
} as const;

export default function AlertsFeed({ alerts }: { alerts: AlertItem[] }) {
  return (
    <div className="bg-panel border border-borderStrong rounded-lg flex flex-col h-full">
      <div className="px-5 py-4 border-b border-borderSoft flex items-center justify-between">
        <h3 className="text-textDim font-bold text-[11px] tracking-widest uppercase flex items-center gap-2">
          <AlertTriangle size={14} className="text-brandAmber" />
          AI Vision Alerts
        </h3>
        <span className="font-mono text-[10px] text-textFaint">{alerts.length} recent</span>
      </div>
      
      <div className="flex flex-col divide-y divide-borderSoft max-h-[300px] overflow-y-auto">
        {alerts.length === 0 ? (
          <div className="p-5 text-center text-textFaint font-mono text-xs">No alerts. System operating normally.</div>
        ) : (
          alerts.map((a) => {
            const Icon = ICON[a.severity];
            return (
              <div key={a.id} className={`px-5 py-3 flex gap-3 border-l-2 ${COLOR[a.severity]}`}>
                <Icon size={15} className="mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[12.5px] text-textMain leading-snug">{a.message}</div>
                  <div className="text-[10px] text-textFaint font-mono mt-1">{a.time}</div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}