import { Clock, Download } from "lucide-react";
import { colorHex } from "./FabricSwatch";
import { GarmentScan } from "../lib/api";

export default function HistoryLog({ history }: { history: GarmentScan[] }) {
  const exportToCSV = () => {
    if (history.length === 0) {
      alert("No data to export!");
      return;
    }

    const headers = ["Time", "Style", "Main Color", "Confidence (%)"];

    const rows = history.map((scan) => [
      scan.timestamp ? new Date(scan.timestamp).toLocaleTimeString() : "-",
      scan.style_name,
      scan.main_color,
      scan.confidence,
    ]);

    const csvContent = [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `ThreadScan_History_${new Date().getTime()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="bg-surface border border-line rounded-xl flex flex-col overflow-hidden shadow-sm">
      <div className="px-5 py-4 border-b border-line flex items-center justify-between bg-surface-muted">
        <div className="flex items-center gap-2">
          <Clock size={14} className="text-accent" />
          <h3 className="text-ink-secondary font-semibold text-[11px] tracking-widest uppercase">Recent Scan History</h3>
        </div>

        <button
          onClick={exportToCSV}
          className="flex items-center gap-2 px-3 py-1.5 bg-accent-soft text-accent hover:bg-accent/15 border border-accent/20 rounded-md text-[10px] font-mono font-bold uppercase transition-colors cursor-pointer"
        >
          <Download size={12} />
          Export CSV
        </button>
      </div>

      <div className="overflow-x-auto max-h-[420px]">
        <table className="w-full text-left text-sm relative">
          <thead className="bg-surface-muted border-b border-line text-ink-soft font-mono text-[10px] uppercase tracking-wider sticky top-0 z-10">
            <tr>
              <th className="px-5 py-3">Time</th>
              <th className="px-5 py-3">Style</th>
              <th className="px-5 py-3">Main Color</th>
              <th className="px-5 py-3">Confidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {history.length === 0 && (
              <tr>
                <td colSpan={4} className="p-8 text-center text-ink-soft font-mono text-xs">
                  No scans recorded yet. Waiting for AI data...
                </td>
              </tr>
            )}
            {history.map((scan, idx) => (
              <tr key={idx} className="hover:bg-surface-muted transition-colors">
                <td className="px-5 py-3 font-mono text-ink-secondary text-xs">
                  {scan.timestamp ? new Date(scan.timestamp).toLocaleTimeString() : "-"}
                </td>
                <td className="px-5 py-3 font-semibold text-ink">{scan.style_name}</td>
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: colorHex(scan.main_color), border: "1px solid var(--color-line)" }}></span>
                    <span className="font-mono text-xs text-ink-secondary">{scan.main_color}</span>
                  </div>
                </td>
                <td className="px-5 py-3 font-mono text-accent">{scan.confidence}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
