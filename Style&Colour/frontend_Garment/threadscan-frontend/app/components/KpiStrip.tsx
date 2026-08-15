interface KpiStripProps {
  totalScans: number;
  avgConfidence: string;
  latestStyle: string;
  latestColor: string;
}

export default function KpiStrip({ totalScans, avgConfidence, latestStyle, latestColor }: KpiStripProps) {
  const items = [
    { label: "Total AI Scans", value: totalScans, borderColor: "#3fe0a1" },
    { label: "Avg Confidence", value: `${avgConfidence}%`, borderColor: "#3e6fd8" },
    { label: "Latest Style", value: latestStyle || "-", borderColor: "#f5b24a" },
    { label: "Latest Color", value: latestColor || "-", borderColor: "#c9915a" },
  ];

  return (
    <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2">
      {items.map((item) => (
        <div
          key={item.label}
          className="bg-panel border border-borderStrong rounded-lg p-5 border-l-2"
          style={{ borderLeftColor: item.borderColor }}
        >
          <div className="text-textFaint text-[10px] uppercase font-bold tracking-widest mb-3">{item.label}</div>
          <div className="text-3xl font-mono font-bold text-textMain">{item.value}</div>
        </div>
      ))}
    </div>
  );
}