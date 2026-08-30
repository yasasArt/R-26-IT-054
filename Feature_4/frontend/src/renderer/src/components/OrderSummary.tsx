import { CheckCircle2, ClipboardCheck, Clock, TrendingUp, Gauge, AlertTriangle } from "lucide-react";
import { CATEGORIES, CATEGORY_LABEL, DecisionSummary, GarmentScan } from "../lib/api";

function StatTile({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div className="bg-surface border border-line rounded-xl p-5 shadow-sm relative overflow-hidden">
      {accent && <div className={`absolute top-0 left-0 h-1 w-full ${accent}`} />}
      <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-2">{label}</div>
      <div className="font-mono text-2xl font-bold text-ink">{value}</div>
      {sub && <div className="text-ink-secondary text-[11px] mt-1.5">{sub}</div>}
    </div>
  );
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function OrderSummary({ summary, history }: { summary: DecisionSummary | null; history: GarmentScan[] }) {
  if (!summary) {
    return (
      <div className="bg-surface border border-dashed border-line rounded-xl p-10 text-center text-ink-soft font-mono text-sm">
        No production target configured yet. Go to Target &amp; Schedule to set one up.
      </div>
    );
  }

  if (!summary.is_completed) {
    return (
      <div className="w-full">
        <h1 className="text-ink text-2xl font-bold mb-1.5">Order Summary</h1>
        <p className="text-ink-secondary text-[13px] mb-7">Fills in automatically once the current target is completed.</p>
        <div className="bg-surface border border-dashed border-line rounded-xl p-10 text-center text-ink-soft font-mono text-sm flex flex-col items-center gap-3">
          <ClipboardCheck size={28} className="opacity-40" />
          <div>
            {summary.total_packed} / {summary.target_pieces} pcs packed so far - order not yet completed.
          </div>
        </div>
      </div>
    );
  }

  const varianceHours = summary.total_hours_allocated - (summary.elapsed_hours ?? 0);
  const aheadOfSchedule = varianceHours >= 0;

  // Colours/styles distribution across the whole session's history - a
  // relevant "production insight" alongside the target-completion numbers,
  // reusing the same raw scan data Analytics shows.
  const colorCounts: Record<string, number> = {};
  history.forEach((scan) => {
    colorCounts[scan.main_color] = (colorCounts[scan.main_color] || 0) + 1;
  });
  const topColors = Object.entries(colorCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  return (
    <div className="w-full flex flex-col gap-6">
      <div>
        <h1 className="text-ink text-2xl font-bold mb-1.5">Order Summary</h1>
        <p className="text-ink-secondary text-[13px]">Completed order report - counting is frozen until a new target is saved.</p>
      </div>

      <div className="bg-success-soft border-2 border-success rounded-2xl p-6 shadow-sm flex items-center gap-4">
        <div className="w-14 h-14 rounded-full bg-success/15 flex items-center justify-center flex-shrink-0">
          <CheckCircle2 size={28} className="text-success" />
        </div>
        <div>
          <div className="text-success font-bold text-2xl">Target Completed!</div>
          <div className="text-ink-secondary text-[13px] mt-1">
            {summary.total_packed} of {summary.target_pieces} pcs packed - completed {formatDateTime(summary.completed_at)}.
            {summary.overrun > 0 && (
              <span className="text-warning">
                {" "}
                {summary.overrun} additional piece{summary.overrun === 1 ? "" : "s"} detected afterward, not counted
                toward this target.
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile
          label="Days Taken"
          value={`${summary.elapsed_days ?? "—"}`}
          sub={`Allocated: ${summary.total_days_allocated} day${summary.total_days_allocated === 1 ? "" : "s"}`}
          accent="bg-accent"
        />
        <StatTile
          label="Actual Time"
          value={`${(summary.elapsed_hours ?? 0).toFixed(1)} hrs`}
          sub={`Estimated: ${summary.total_hours_allocated.toFixed(1)} hrs`}
          accent={aheadOfSchedule ? "bg-success" : "bg-error"}
        />
        <StatTile
          label={aheadOfSchedule ? "Ahead By" : "Over By"}
          value={`${Math.abs(varianceHours).toFixed(1)} hrs`}
          sub={aheadOfSchedule ? "Finished ahead of the allocated schedule" : "Took longer than allocated"}
          accent={aheadOfSchedule ? "bg-success" : "bg-error"}
        />
        <StatTile
          label="Achieved Efficiency"
          value={summary.efficiency_pct !== null ? `${Math.round(summary.efficiency_pct)}%` : "—"}
          sub={`Actual ${summary.current_rate_per_hour.toFixed(1)} vs required ${summary.required_rate_per_hour.toFixed(1)} pcs/hr`}
          accent="bg-violet"
        />
      </div>

      <div className="bg-surface border border-line rounded-xl p-5 shadow-sm">
        <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase mb-4 border-b border-line pb-3 flex items-center gap-2">
          <ClipboardCheck size={14} className="text-accent" /> Category Completion
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {CATEGORIES.map((category) => {
            const cat = summary.categories[category];
            return (
              <div
                key={category}
                className="flex items-center justify-between gap-3 bg-surface-muted border border-line rounded-lg px-4 py-3"
              >
                <div>
                  <div className="text-ink font-semibold text-[13px]">{CATEGORY_LABEL[category]}</div>
                  <div className="text-ink-soft text-[11px] font-mono mt-0.5">
                    {cat.total_packed} / {cat.target_pieces} pcs
                    {cat.is_completed && cat.elapsed_days ? ` · ${cat.elapsed_days}d` : ""}
                  </div>
                </div>
                {cat.is_completed ? (
                  <span className="flex items-center gap-1 text-[10px] font-semibold text-success bg-success-soft px-2 py-1 rounded-full flex-shrink-0">
                    <CheckCircle2 size={11} /> Completed
                  </span>
                ) : (
                  <span className="text-[10px] font-semibold text-ink-soft bg-line-soft px-2 py-1 rounded-full flex-shrink-0">
                    {cat.remaining} left
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-surface border border-line rounded-xl p-5 shadow-sm">
          <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase mb-4 border-b border-line pb-3 flex items-center gap-2">
            <Gauge size={14} className="text-accent" /> Schedule Performance
          </h3>
          <div className="flex flex-col gap-3 text-[13px]">
            <div className="flex justify-between">
              <span className="text-ink-secondary">Due date</span>
              <span className="font-mono text-ink">{summary.due_date}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-secondary">Planned daily hours</span>
              <span className="font-mono text-ink">{summary.planned_daily_hours.toFixed(1)} hrs</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-secondary">Required pace</span>
              <span className="font-mono text-ink">{summary.required_rate_per_hour.toFixed(2)} pcs/hr</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-secondary">Actual pace</span>
              <span className="font-mono text-ink">{summary.current_rate_per_hour.toFixed(2)} pcs/hr</span>
            </div>
            <div className="flex justify-between pt-3 border-t border-line-soft">
              <span className="text-ink-secondary flex items-center gap-1.5">
                {aheadOfSchedule ? <TrendingUp size={13} className="text-success" /> : <AlertTriangle size={13} className="text-error" />}
                Result
              </span>
              <span className={`font-mono font-bold ${aheadOfSchedule ? "text-success" : "text-error"}`}>
                {aheadOfSchedule ? "Ahead of schedule" : "Behind schedule"}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-surface border border-line rounded-xl p-5 shadow-sm">
          <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase mb-4 border-b border-line pb-3 flex items-center gap-2">
            <Clock size={14} className="text-accent" /> Top Colours Packed
          </h3>
          {topColors.length === 0 ? (
            <div className="text-ink-soft font-mono text-xs">No colour data recorded.</div>
          ) : (
            <div className="flex flex-col gap-2.5">
              {topColors.map(([color, count]) => (
                <div key={color} className="flex items-center justify-between text-[13px]">
                  <span className="text-ink-secondary uppercase">{color}</span>
                  <span className="font-mono font-bold text-ink">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
