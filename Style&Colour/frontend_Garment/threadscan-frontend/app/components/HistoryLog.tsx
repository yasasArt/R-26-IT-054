"use client";
import { Clock, Download } from "lucide-react";
import { colorHex } from "./FabricSwatch";

export default function HistoryLog({ history }: { history: any[] }) {
  
  // CSV ෆයිල් එක හදන Function එක
  const exportToCSV = () => {
    if (history.length === 0) {
      alert("No data to export!");
      return;
    }

    // CSV එකේ මාතෘකා (Headers)
    const headers = ["Time", "Style", "Main Color", "Confidence (%)"];
    
    // දත්ත පේළි (Rows) සකස් කිරීම
    const rows = history.map(scan => [
      new Date().toLocaleTimeString(), // මෙතනට Backend එකෙන් එන නියම Time එක දෙන්නත් පුළුවන්
      scan.style_name,
      scan.main_color,
      scan.confidence
    ]);

    // Headers සහ Rows එකතු කර CSV ආකෘතියට හැරවීම
    const csvContent = [
      headers.join(","),
      ...rows.map(row => row.join(","))
    ].join("\n");

    // ෆයිල් එක බාගත කිරීම (Download)
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
    <div className="bg-panel border border-borderStrong rounded-lg flex flex-col overflow-hidden shadow-sm">
      <div className="px-5 py-4 border-b border-borderSoft flex items-center justify-between bg-panelRaised">
        <div className="flex items-center gap-2">
          <Clock size={14} className="text-brandGreen" />
          <h3 className="text-textDim font-bold text-[11px] tracking-widest uppercase">Recent Scan History</h3>
        </div>
        
        {/* CSV Download Button එක */}
        <button 
          onClick={exportToCSV}
          className="flex items-center gap-2 px-3 py-1.5 bg-brandGreen/10 text-brandGreen hover:bg-brandGreen/20 border border-brandGreen/30 rounded text-[10px] font-mono font-bold uppercase transition-colors cursor-pointer"
        >
          <Download size={12} />
          Export CSV
        </button>
      </div>
      
      <div className="overflow-x-auto max-h-[400px]">
        <table className="w-full text-left text-sm relative">
          <thead className="bg-panelRaised border-b border-borderSoft text-textFaint font-mono text-[10px] uppercase tracking-wider sticky top-0 z-10">
            <tr>
              <th className="px-5 py-3">Time</th>
              <th className="px-5 py-3">Style</th>
              <th className="px-5 py-3">Main Color</th>
              <th className="px-5 py-3">Confidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-borderSoft">
            {history.length === 0 && (
              <tr>
                <td colSpan={4} className="p-8 text-center text-textFaint font-mono text-xs">
                  No scans recorded yet. Waiting for AI data...
                </td>
              </tr>
            )}
            {history.map((scan, idx) => (
              <tr key={idx} className="hover:bg-white/5 transition-colors">
                <td className="px-5 py-3 font-mono text-textDim text-xs">
                   {new Date().toLocaleTimeString()}
                </td>
                <td className="px-5 py-3 font-bold text-textMain">{scan.style_name}</td>
                <td className="px-5 py-3 flex items-center gap-2">
                   <span className="w-3 h-3 rounded-full border border-white/20" style={{backgroundColor: colorHex(scan.main_color)}}></span>
                   <span className="font-mono text-xs">{scan.main_color}</span>
                </td>
                <td className="px-5 py-3 font-mono text-brandGreen">{scan.confidence}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}