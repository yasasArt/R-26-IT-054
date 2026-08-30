import { CheckCircle2, Shirt } from "lucide-react";
import { CATEGORIES, CATEGORY_LABEL, CategorySummary, GarmentCategory } from "../lib/api";

function MetricTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="text-ink-soft text-[9px] uppercase font-bold tracking-widest mb-1">{label}</div>
      <div className="font-mono text-[13px] font-bold text-ink leading-tight">{value}</div>
      {sub && <div className="text-ink-soft text-[10px] mt-0.5 leading-tight">{sub}</div>}
    </div>
  );
}

function CategoryCard({ category, data }: { category: GarmentCategory; data: CategorySummary }) {
  const progressPct = data.target_pieces > 0 ? Math.min(100, (data.total_packed / data.target_pieces) * 100) : 0;

  const cycleTimeSec = data.current_rate_per_hour > 0 ? 3600 / data.current_rate_per_hour : 0;

  const deliveryText =
    data.estimated_days_to_target === null
      ? "Awaiting data"
      : data.on_track
      ? `On track — ${data.projected_completion_date}`
      : `Delayed by ${data.delayed_days} day(s)`;

  return (
    <div className="bg-surface border border-line rounded-xl p-5 shadow-sm relative overflow-hidden flex flex-col gap-4">
      <div className={`absolute top-0 left-0 h-1 w-full ${data.is_completed ? "bg-success" : "bg-accent"}`} />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shirt size={14} className="text-accent" />
          <h4 className="text-ink font-bold text-[13px] uppercase tracking-wide">{CATEGORY_LABEL[category]}</h4>
        </div>
        {data.is_completed && (
          <span className="flex items-center gap-1 text-[10px] font-semibold text-success bg-success-soft px-2 py-0.5 rounded-full">
            <CheckCircle2 size={11} /> Completed
          </span>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between items-baseline">
          <span className="font-mono text-xl font-bold text-ink">
            {data.total_packed}
            <span className="text-ink-soft text-sm font-normal"> / {data.target_pieces} pcs</span>
          </span>
          <span className="text-[11px] text-ink-secondary">{progressPct.toFixed(0)}%</span>
        </div>
        <div className="h-1.5 w-full bg-line-soft rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${data.is_completed ? "bg-success" : "bg-accent"}`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 pt-1 border-t border-line-soft">
        <MetricTile label="Remaining" value={`${data.remaining} pcs`} />
        <MetricTile
          label="Remaining Time"
          value={
            data.current_rate_per_hour > 0
              ? `${(data.remaining / data.current_rate_per_hour).toFixed(1)} hrs`
              : "Waiting..."
          }
        />
        <MetricTile label="Efficiency" value={data.efficiency_pct !== null ? `${Math.round(data.efficiency_pct)}%` : "—"} />
        <MetricTile label="Delivery" value={deliveryText} />
        <MetricTile
          label="Suggested OT"
          value={data.extra_hours_per_day ? `${data.extra_hours_per_day.toFixed(1)} hrs/day` : "None"}
        />
        <MetricTile label="Avg Cycle Time" value={cycleTimeSec > 0 ? `${cycleTimeSec.toFixed(1)} sec/pc` : "—"} />
      </div>
    </div>
  );
}

export default function CategoryBreakdown({ categories }: { categories: Record<GarmentCategory, CategorySummary> }) {
  return (
    <div>
      <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-3">Category Breakdown</div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {CATEGORIES.map((category) => (
          <CategoryCard key={category} category={category} data={categories[category]} />
        ))}
      </div>
    </div>
  );
}
