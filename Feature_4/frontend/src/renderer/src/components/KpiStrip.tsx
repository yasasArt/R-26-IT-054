interface KpiStripProps {
  totalScans: number;
  target: number;
  ratePerHour: number;
  efficiency: number;
}

export default function KpiStrip({ totalScans, target, ratePerHour, efficiency }: KpiStripProps) {
  const remaining = Math.max(0, target - totalScans);

  const etaHours = ratePerHour > 0 ? remaining / ratePerHour : 0;
  const etaText = ratePerHour > 0 ? `${etaHours.toFixed(1)} hrs` : "Waiting...";

  let effTextColor = "text-error";
  let effBarColor = "bg-error";
  if (efficiency >= 100) {
    effTextColor = "text-success";
    effBarColor = "bg-success";
  } else if (efficiency >= 85) {
    effTextColor = "text-warning";
    effBarColor = "bg-warning";
  }

  const items = [
    {
      label: "Total Packed",
      sub: "AI real-time piece count",
      value: totalScans.toLocaleString(),
      accent: "accent" as const,
    },
    {
      label: "Remaining to Target",
      sub: `of ${target.toLocaleString()} pcs target`,
      value: `${remaining.toLocaleString()} pcs`,
      accent: "violet" as const,
    },
    {
      label: "Est. Time Remaining",
      sub: `Speed: ${ratePerHour.toFixed(1)} pcs/hr`,
      value: etaText,
      accent: "warning" as const,
    },
  ];

  const accentClasses: Record<string, { text: string; bg: string; bar: string }> = {
    accent: { text: "text-accent", bg: "bg-accent-soft", bar: "bg-accent" },
    violet: { text: "text-violet", bg: "bg-violet-soft", bar: "bg-violet" },
    warning: { text: "text-warning", bg: "bg-warning-soft", bar: "bg-warning" },
  };

  return (
    <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2">
      {items.map((item) => {
        const c = accentClasses[item.accent];
        return (
          <div key={item.label} className="bg-surface border border-line rounded-xl p-5 shadow-sm relative overflow-hidden">
            <div className={`absolute top-0 left-0 h-1 w-full ${c.bar}`} />
            <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-3">{item.label}</div>
            <div className="text-3xl font-mono font-bold text-ink">{item.value}</div>
            <div className="text-ink-secondary text-[11px] mt-2 font-medium">{item.sub}</div>
          </div>
        );
      })}

      <div className="bg-surface border border-line rounded-xl p-5 shadow-sm relative overflow-hidden">
        <div className={`absolute top-0 left-0 h-1 w-full ${effBarColor}`} />
        <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-3">Production Efficiency</div>
        <div className={`text-3xl font-mono font-bold ${effTextColor}`}>{Math.round(efficiency)}%</div>
        <div className="w-full h-1.5 bg-line-soft rounded-full mt-3 overflow-hidden">
          <div className={`h-full ${effBarColor} transition-all duration-500`} style={{ width: `${Math.min(100, efficiency)}%` }} />
        </div>
        <div className="text-ink-secondary text-[11px] mt-2 font-medium">Compared to required pace</div>
      </div>
    </div>
  );
}
