import { AlertTriangle, AlertOctagon, Info } from "lucide-react";

export interface AlertItem {
  id: string;
  severity: "info" | "warning" | "critical";
  message: string;
  time: string;
}

const ICON = { critical: AlertOctagon, warning: AlertTriangle, info: Info } as const;
const STYLE = {
  critical: "text-error border-l-error bg-error-soft/40",
  warning: "text-warning border-l-warning bg-warning-soft/40",
  info: "text-accent border-l-accent bg-accent-soft/40",
} as const;

export default function AlertsFeed({ alerts }: { alerts: AlertItem[] }) {
  return (
    <div className="bg-surface border border-line rounded-xl flex flex-col h-full shadow-sm">
      <div className="px-5 py-4 border-b border-line flex items-center justify-between">
        <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase flex items-center gap-2">
          <AlertTriangle size={14} className="text-warning" />
          AI Vision Alerts
        </h3>
        <span className="font-mono text-[10px] text-ink-soft">{alerts.length} recent</span>
      </div>

      <div className="flex flex-col divide-y divide-line-soft max-h-[300px] overflow-y-auto">
        {alerts.length === 0 ? (
          <div className="p-6 text-center text-ink-soft font-mono text-xs">No alerts. System operating normally.</div>
        ) : (
          alerts.map((a) => {
            const Icon = ICON[a.severity];
            return (
              <div key={a.id} className={`px-5 py-3 flex gap-3 border-l-[3px] ${STYLE[a.severity]}`}>
                <Icon size={15} className="mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[12.5px] text-ink leading-snug">{a.message}</div>
                  <div className="text-[10px] text-ink-soft font-mono mt-1">{a.time}</div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
