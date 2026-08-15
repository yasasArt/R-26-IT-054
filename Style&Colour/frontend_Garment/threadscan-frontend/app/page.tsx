"use client";
import { useEffect, useState, useRef } from "react";
import { fetchLatestGarment } from "../lib/api";
import { LayoutDashboard, BarChart3, Clock, CircleDot, AlertTriangle } from "lucide-react";
import LiveCameraPanel from "./components/LiveCameraPanel";
import AlertsFeed, { AlertItem } from "./components/AlertsFeed";
import KpiStrip from "./components/KpiStrip";
import HistoryLog from "./components/HistoryLog";
import Analytics from "./components/Analytics";

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("dashboard");
  
  // දත්ත ගබඩා කිරීම සඳහා States
  const [latestScan, setLatestScan] = useState<any>(null);
  const [scanHistory, setScanHistory] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  
  // එකම දත්තය දෙපාරක් සේව් වීම වැළැක්වීමට
  const lastScanId = useRef<string | null>(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      const scanData = await fetchLatestGarment();
      
      // අලුත් Scan එකක් ආවොත් පමණක්...
      if (scanData && scanData._id !== lastScanId.current) {
        lastScanId.current = scanData._id;
        setLatestScan(scanData);
        
        // 1. History එකට එකතු කිරීම (අලුත්ම එක උඩින්ම පෙන්වයි)
        setScanHistory(prev => [scanData, ...prev].slice(0, 20)); // අවසන් 20 පමණක් තියාගන්න

        // 2. AI දත්ත මත පදනම්ව Alerts සෑදීම
        if (scanData.confidence < 80) {
          addAlert("warning", `Low Confidence (${scanData.confidence}%) detected for ${scanData.style_name}. Ensure flat placement.`);
        }
        if (scanData.main_color === "UNKNOWN") {
          addAlert("critical", `Cannot verify main color for ${scanData.style_name}. Check lighting.`);
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const addAlert = (severity: "info" | "warning" | "critical", message: string) => {
    const newAlert: AlertItem = {
      id: Math.random().toString(36).substr(2, 9),
      severity,
      message,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setAlerts(prev => [newAlert, ...prev].slice(0, 10)); // අවසන් Alerts 10 පමණක් තබාගන්න
  };

  // KPI සඳහා ගණනය කිරීම්
  const totalScans = scanHistory.length;
  const avgConf = totalScans > 0 
    ? (scanHistory.reduce((sum, s) => sum + s.confidence, 0) / totalScans).toFixed(1) 
    : "0.0";

  const getNavClass = (tabName: string) => {
    return activeTab === tabName
      ? "flex items-center gap-3 px-3 py-2 bg-brandGreen/10 text-brandGreen border border-brandGreen/20 rounded-md text-[13px] font-medium cursor-pointer"
      : "flex items-center gap-3 px-3 py-2 text-textDim hover:text-textMain hover:bg-white/5 rounded-md text-[13px] font-medium transition-colors cursor-pointer";
  };

  return (
    <div className="flex h-screen overflow-hidden font-sans">
      {/* වම් පස මෙනුව */}
      <aside className="w-[220px] bg-panel border-r border-borderStrong flex-shrink-0 flex flex-col p-[22px_14px]">
        <div className="font-mono font-semibold text-[14px] text-textMain tracking-widest mb-8 border-b border-borderSoft pb-4 flex items-center gap-3">
          <div className="w-8 h-8 border border-brandGreen rounded flex items-center justify-center shadow-[0_0_8px_rgba(63,224,161,0.3)]">
            <div className="w-2 h-2 bg-brandGreen rounded-sm" />
          </div>
          <div>
            <div className="leading-tight text-brandGreen">THREADSCAN</div>
            <div className="text-[9px] text-textFaint uppercase tracking-widest">AI Vision Floor</div>
          </div>
        </div>

        <div className="text-textFaint text-[10px] uppercase font-mono tracking-widest mb-2 px-2">Monitor</div>
        <nav className="flex flex-col gap-1 mb-8">
          <div onClick={() => setActiveTab("dashboard")} className={getNavClass("dashboard")}>
            <LayoutDashboard size={16} /> Live Dashboard
          </div>
          <div onClick={() => setActiveTab("history")} className={getNavClass("history")}>
            <Clock size={16} /> History Log
          </div>
          <div onClick={() => setActiveTab("alerts")} className={getNavClass("alerts")}>
            <AlertTriangle size={16} /> Alerts
          </div>
          <div onClick={() => setActiveTab("analytics")} className={getNavClass("analytics")}>
            <BarChart3 size={16} /> Analytics
          </div>
        </nav>
      </aside>

      {/* ප්‍රධාන දර්ශනය */}
      <main className="flex-1 flex flex-col min-w-0 relative">
        <header className="h-[60px] border-b border-borderStrong flex items-center justify-between px-7 bg-panel/80 backdrop-blur-md sticky top-0 z-10">
          <div className="flex items-center gap-4">
            <h1 className="font-semibold text-[15px]">Live AI Recognition</h1>
            <span className="border border-borderStrong text-textDim font-mono text-[10px] px-2 py-1 rounded">PACKING ZONE</span>
          </div>
          <div className="flex items-center gap-6 text-brandGreen font-mono text-[11px] tracking-wider">
            <div className="flex items-center gap-2">
              <CircleDot size={12} className="animate-pulse" /> AI ENGINE CONNECTED
            </div>
          </div>
        </header>

        {/* අන්තර්ගතය */}
        <div className="p-7 flex flex-col gap-6 overflow-y-auto h-full">
          
          {activeTab === "dashboard" && (
            <>
              {/* යාවත්කාලීන කරන ලද AI KPI */}
              <KpiStrip 
                totalScans={totalScans} 
                avgConfidence={avgConf} 
                latestStyle={latestScan?.style_name} 
                latestColor={latestScan?.main_color} 
              />
              <div className="grid grid-cols-[1fr_360px] gap-6 items-start max-lg:grid-cols-1">
                <LiveCameraPanel scan={latestScan} />
                <div className="flex flex-col gap-6">
                   {/* Real-time Alerts */}
                  <AlertsFeed alerts={alerts} />
                </div>
              </div>
            </>
          )}

          {activeTab === "history" && (
            <div className="w-full">
              <h2 className="text-xl font-bold mb-4 text-textMain">Garment Scan History</h2>
              <HistoryLog history={scanHistory} />
            </div>
          )}

          {activeTab === "alerts" && (
            <div className="w-full">
              <h2 className="text-xl font-bold mb-4 text-textMain">System Alerts Log</h2>
              <AlertsFeed alerts={alerts} />
            </div>
          )}

          {activeTab === "analytics" && (
             <div className="w-full h-full">
               {/* අපගේ AI History දත්ත (scanHistory) මෙතැනින් Analytics එකට ලබා දෙනවා */}
             <Analytics history={scanHistory} />
             </div>
           )}

        </div>
      </main>

      <style jsx global>{`
        @keyframes sweep {
          0% { top: 10%; opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { top: 90%; opacity: 0; }
        }
      `}</style>
    </div>
  );
}