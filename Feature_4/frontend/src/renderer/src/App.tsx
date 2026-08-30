import { useEffect, useState, useRef } from "react";
import {
  fetchAllGarments,
  fetchLatestGarment,
  fetchSummary,
  fetchPipelineStatus,
  resetProgress,
  DecisionSummary,
  GarmentScan,
} from "./lib/api";
import {
  LayoutDashboard,
  BarChart3,
  Clock,
  CircleDot,
  AlertTriangle,
  Settings as SettingsIcon,
  PowerOff,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  RotateCcw,
  Loader2,
} from "lucide-react";
import LiveCameraPanel from "./components/LiveCameraPanel";
import AlertsFeed, { AlertItem } from "./components/AlertsFeed";
import KpiStrip from "./components/KpiStrip";
import HistoryLog from "./components/HistoryLog";
import Analytics from "./components/Analytics";
import SettingsPanel from "./components/SettingsPanel";
import DowntimeLog from "./components/DowntimeLog";
import DeviceSetup from "./components/DeviceSetup";
import CategoryBreakdown from "./components/CategoryBreakdown";
import OrderSummary from "./components/OrderSummary";

export default function App() {
  // Land on Device Setup first - this is a workstation for an external USB
  // webcam, so the operator should confirm/select the camera before moving
  // on to production monitoring, not the other way around.
  const [activeTab, setActiveTab] = useState("device-setup");
  // Was previously a hardcoded "AI ENGINE CONNECTED" label in the sidebar,
  // regardless of whether the CV service was actually reachable - now
  // reflects a real, polled connectivity check.
  const [aiEngineConnected, setAiEngineConnected] = useState(false);

  const [latestScan, setLatestScan] = useState<GarmentScan | null>(null);
  const [scanHistory, setScanHistory] = useState<GarmentScan[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [summary, setSummary] = useState<DecisionSummary | null>(null);

  const lastScanId = useRef<string | null>(null);
  // Tracks whether we've already auto-navigated to the Order Summary page
  // for the *current* completion. is_completed stays true indefinitely now
  // (the counter is frozen, not reset), so without this guard every 10s
  // summary poll would yank the operator back to the summary page even if
  // they'd deliberately navigated elsewhere. Cleared the moment a new
  // target is saved (is_completed goes false again), arming it for the
  // next completion.
  const hasNavigatedToSummary = useRef(false);

  const [confirmingReset, setConfirmingReset] = useState(false);
  const [resettingSession, setResettingSession] = useState(false);

  const addAlert = (severity: "info" | "warning" | "critical", message: string) => {
    const newAlert: AlertItem = {
      id: Math.random().toString(36).substr(2, 9),
      severity,
      message,
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    setAlerts((prev) => [newAlert, ...prev].slice(0, 10));
  };

  const refreshSummary = async () => {
    const data = await fetchSummary();
    if (!data) return;
    setSummary(data);

    if (data.is_completed && !hasNavigatedToSummary.current) {
      hasNavigatedToSummary.current = true;
      addAlert(
        "info",
        `Target completed: ${data.total_packed}/${data.target_pieces} pcs packed. Counting is now frozen - see Order Summary.`
      );
      setActiveTab("order-summary");
    } else if (!data.is_completed) {
      hasNavigatedToSummary.current = false;
    }
  };

  // Manual counterpart to the automatic freeze-on-completion reset - lets
  // the operator restart the current counting cycle on demand (e.g. mid-day,
  // or to unfreeze a completed target without going through Target &
  // Schedule). Only moves the counting baseline forward; every garment
  // record already saved stays in the database untouched.
  const handleResetSession = async () => {
    setResettingSession(true);
    try {
      await resetProgress();
      setLatestScan(null);
      hasNavigatedToSummary.current = false;
      await refreshSummary();
      addAlert("info", "Session manually reset - counting restarted from now. History preserved.");
    } catch (error) {
      addAlert("critical", `Failed to reset session: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setResettingSession(false);
      setConfirmingReset(false);
    }
  };

  // Entering the Live Dashboard should never show a stale "best frame" from
  // before - clear it, and pre-seed the dedupe tracker with whatever the
  // latest capture already is so the poll loop doesn't immediately treat
  // that pre-existing scan as "new" and pull it back in. Detection then
  // starts fresh from this point on.
  const enterLiveDashboard = async () => {
    setLatestScan(null);
    const current = await fetchLatestGarment();
    lastScanId.current = current?._id ?? null;
    setActiveTab("dashboard");
  };

  // History Management (Target & Schedule page) just permanently deleted
  // every garment record on the backend - reflect that immediately rather
  // than waiting for the next poll tick, so History Log shows its empty
  // state right away.
  const handleHistoryDeleted = () => {
    setScanHistory([]);
    setLatestScan(null);
    lastScanId.current = null;
    refreshSummary();
  };

  useEffect(() => {
    (async () => {
      await refreshSummary();
    })();
    const interval = setInterval(refreshSummary, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const pollConnection = async () => {
      const status = await fetchPipelineStatus();
      if (!cancelled) setAiEngineConnected(status !== null);
    };
    pollConnection();
    const interval = setInterval(pollConnection, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    (async () => {
      // Load full persisted history first (History Log/Analytics should
      // reflect everything ever captured, not just what streamed in during
      // this session) and seed the dedupe tracker with the current latest
      // so the poll below doesn't immediately re-add it as "new".
      const allHistory = await fetchAllGarments();
      setScanHistory(allHistory);
      lastScanId.current = allHistory[0]?._id ?? null;
    })();

    const interval = setInterval(async () => {
      const scanData = await fetchLatestGarment();

      if (scanData && scanData._id !== lastScanId.current) {
        lastScanId.current = scanData._id;
        setLatestScan(scanData);
        refreshSummary();
        setScanHistory((prev) => [scanData, ...prev]);

        if (scanData.confidence < 80) {
          addAlert("warning", `Low Confidence (${scanData.confidence}%) detected for ${scanData.style_name}.`);
        }
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const getNavClass = (tabName: string) => {
    const base = "flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium cursor-pointer transition-colors";
    return activeTab === tabName
      ? `${base} bg-white/[0.08] text-nav-text-active`
      : `${base} text-nav-text hover:text-nav-text-active hover:bg-white/[0.04]`;
  };

  const cycleTimeSec = summary && summary.current_rate_per_hour > 0 ? 3600 / summary.current_rate_per_hour : 0;
  const progressPct = summary ? Math.min(100, (summary.total_packed / Math.max(1, summary.target_pieces)) * 100) : 0;

  return (
    <div className="flex h-screen overflow-hidden font-sans bg-canvas">
      <aside className="w-[240px] bg-sidebar flex-shrink-0 flex flex-col p-[22px_16px] relative">
        <div className="absolute inset-0 pointer-events-none opacity-[0.03] hero-gradient" />

        <div className="flex items-center gap-3 mb-9 pb-5 border-b border-white/10 relative">
          <div className="w-9 h-9 rounded-lg logo-gradient flex items-center justify-center shadow-lg shadow-black/20">
            <div className="w-2.5 h-2.5 bg-white rounded-sm" />
          </div>
          <div>
            <div className="leading-tight text-white font-semibold text-[14px] tracking-wide">THREADSCAN</div>
            <div className="text-[9px] text-nav-text uppercase tracking-widest">Workstation Intelligence</div>
          </div>
        </div>

        <div className="text-nav-text/60 text-[10px] uppercase font-mono tracking-widest mb-2 px-2 relative">Setup</div>
        <nav className="flex flex-col gap-1 mb-8 relative">
          <div onClick={() => setActiveTab("device-setup")} className={getNavClass("device-setup")}>
            <Camera size={16} /> Device Setup
          </div>
        </nav>

        <div className="text-nav-text/60 text-[10px] uppercase font-mono tracking-widest mb-2 px-2 relative">Monitor</div>
        <nav className="flex flex-col gap-1 mb-8 relative">
          <div onClick={enterLiveDashboard} className={getNavClass("dashboard")}>
            <LayoutDashboard size={16} /> Live Dashboard
          </div>
          <div onClick={() => setActiveTab("order-summary")} className={getNavClass("order-summary")}>
            <ClipboardCheck size={16} /> Order Summary
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

        <div className="text-nav-text/60 text-[10px] uppercase font-mono tracking-widest mb-2 px-2 relative">Admin</div>
        <nav className="flex flex-col gap-1 mb-8 relative">
          <div onClick={() => setActiveTab("settings")} className={getNavClass("settings")}>
            <SettingsIcon size={16} /> Target &amp; Schedule
          </div>
          <div onClick={() => setActiveTab("downtime")} className={getNavClass("downtime")}>
            <PowerOff size={16} /> Downtime Log
          </div>
        </nav>

        <div
          className={`mt-auto pt-5 border-t border-white/10 relative flex items-center gap-2 font-mono text-[10px] tracking-wider ${
            aiEngineConnected ? "text-connected" : "text-error"
          }`}
        >
          <CircleDot size={11} className={aiEngineConnected ? "animate-pulse" : ""} />
          {aiEngineConnected ? "AI ENGINE CONNECTED" : "AI ENGINE OFFLINE"}
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0 relative">
        <header className="h-[64px] border-b border-line flex items-center justify-between px-8 bg-surface/90 backdrop-blur-md sticky top-0 z-10">
          <div className="flex items-center gap-4">
            <h1 className="font-semibold text-[16px] text-ink">Production Decision Support</h1>
            <span className="border border-line text-ink-soft font-mono text-[10px] px-2 py-1 rounded-full">PACKING ZONE</span>
          </div>
        </header>

        <div className="p-8 flex flex-col gap-6 overflow-y-auto h-full">
          {activeTab === "dashboard" && (
            <>
              {!summary ? (
                <div className="bg-surface border border-dashed border-line rounded-xl p-10 text-center text-ink-soft font-mono text-sm">
                  No production target configured yet. Go to <span className="text-accent">Target &amp; Schedule</span> to set one up.
                </div>
              ) : (
                <>
                  <div className="flex justify-end">
                    {!confirmingReset ? (
                      <button
                        onClick={() => setConfirmingReset(true)}
                        className="flex items-center gap-2 px-3 py-2 bg-surface border border-line text-ink-secondary hover:text-ink hover:bg-surface-muted rounded-lg text-[12px] font-medium transition-colors"
                      >
                        <RotateCcw size={13} /> Reset Session
                      </button>
                    ) : (
                      <div className="flex items-center gap-2.5 bg-warning-soft border border-warning/30 rounded-lg px-3.5 py-2">
                        <span className="text-warning text-[12px] font-medium">Reset counting from now? History is kept.</span>
                        <button
                          onClick={handleResetSession}
                          disabled={resettingSession}
                          className="flex items-center gap-1.5 px-2.5 py-1.5 bg-error text-white rounded text-[11px] font-semibold hover:bg-error/90 disabled:opacity-50 transition-colors"
                        >
                          {resettingSession && <Loader2 size={12} className="animate-spin" />}
                          {resettingSession ? "Resetting..." : "Yes, reset"}
                        </button>
                        <button
                          onClick={() => setConfirmingReset(false)}
                          disabled={resettingSession}
                          className="px-2.5 py-1.5 text-ink-secondary text-[11px] font-medium hover:text-ink disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>

                  {summary.is_completed && (
                    <div className="bg-success-soft border-2 border-success rounded-2xl p-6 shadow-sm flex items-center gap-4">
                      <div className="w-14 h-14 rounded-full bg-success/15 flex items-center justify-center flex-shrink-0">
                        <CheckCircle2 size={28} className="text-success" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-success font-bold text-2xl">Target Completed!</div>
                        <div className="text-ink-secondary text-[13px] mt-1">
                          {summary.total_packed} of {summary.target_pieces} pcs packed
                          {summary.elapsed_days ? ` in ${summary.elapsed_days} day${summary.elapsed_days === 1 ? "" : "s"}` : ""}
                          . Counting is frozen - see{" "}
                          <button
                            onClick={() => setActiveTab("order-summary")}
                            className="text-success font-semibold underline underline-offset-2 hover:text-success/80"
                          >
                            Order Summary
                          </button>{" "}
                          for the full report.
                        </div>
                      </div>
                    </div>
                  )}

                  <KpiStrip
                    totalScans={summary.total_packed}
                    target={summary.target_pieces}
                    ratePerHour={summary.current_rate_per_hour}
                    efficiency={summary.efficiency_pct ?? 0}
                  />

                  <div className="grid grid-cols-3 gap-4 max-lg:grid-cols-1">
                    <div className="bg-surface border border-line rounded-xl p-5 shadow-sm relative overflow-hidden">
                      <div className={`absolute top-0 left-0 h-1 w-full ${summary.on_track !== false ? "bg-success" : "bg-error"}`} />
                      <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-3">Projected Delivery</div>
                      <div className="text-xl font-mono font-bold text-ink">
                        {summary.estimated_days_to_target === null
                          ? "AWAITING DATA"
                          : summary.on_track
                          ? `ON TRACK — ${summary.projected_completion_date}`
                          : `DELAYED BY ${summary.delayed_days} DAY(S)`}
                      </div>
                      <div className={`text-[11px] mt-2 font-medium ${summary.on_track !== false ? "text-success" : "text-error"}`}>
                        {summary.estimated_days_to_target === null
                          ? "Not enough packing history yet to estimate a rate"
                          : summary.on_track
                          ? "Projected to finish before target"
                          : `Warning: will miss due date (${summary.due_date})`}
                      </div>
                    </div>

                    <div className="bg-surface border border-line rounded-xl p-5 shadow-sm relative overflow-hidden">
                      <div
                        className={`absolute top-0 left-0 h-1 w-full ${
                          summary.extra_hours_per_day ? (summary.extra_hours_per_day > 3 ? "bg-error" : "bg-warning") : "bg-line"
                        }`}
                      />
                      <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-3">Suggested OT</div>
                      <div className="text-xl font-mono font-bold text-ink">
                        {(summary.extra_hours_per_day ?? 0).toFixed(1)} <span className="text-xs text-ink-secondary">hrs/day</span>
                      </div>
                      <div className="text-ink-secondary text-[11px] mt-2 font-medium">
                        {!summary.extra_hours_per_day ? "No OT required currently" : "Action required to catch up"}
                      </div>
                    </div>

                    <div className="bg-surface border border-line rounded-xl p-5 shadow-sm relative overflow-hidden">
                      <div className="absolute top-0 left-0 h-1 w-full bg-accent" />
                      <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest mb-3">Avg Cycle Time</div>
                      <div className="text-xl font-mono font-bold text-ink">
                        {cycleTimeSec.toFixed(1)} <span className="text-xs text-ink-secondary">sec/pc</span>
                      </div>
                      <div className="text-ink-secondary text-[11px] mt-2 font-medium">
                        Based on effective packing time (breaks &amp; downtime excluded)
                      </div>
                    </div>
                  </div>

                  <div className="bg-surface border border-line rounded-xl p-5 shadow-sm">
                    <div className="flex flex-col gap-2">
                      <div className="text-ink-soft text-[10px] uppercase font-bold tracking-widest">Order Target Progress</div>
                      <div className="flex justify-between items-baseline">
                        <div>
                          <span className="text-3xl font-mono font-bold text-accent">{summary.total_packed}</span>
                          <span className="text-xl text-ink-soft"> / {summary.target_pieces} pcs</span>
                        </div>
                        <span className="text-xs text-ink-secondary">{progressPct.toFixed(1)}% complete</span>
                      </div>

                      <div className="h-2 w-full bg-line-soft rounded-full mt-2 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-accent/70 to-accent transition-all duration-500"
                          style={{ width: `${progressPct}%` }}
                        />
                      </div>

                      <div className="flex justify-between text-[10px] text-ink-soft mt-1 font-mono">
                        <span>Due: {summary.due_date}</span>
                        <span>Remaining: {summary.remaining} pcs</span>
                      </div>
                    </div>
                  </div>

                  <CategoryBreakdown categories={summary.categories} />
                </>
              )}

              <div className="grid grid-cols-[1fr_360px] gap-6 items-start max-lg:grid-cols-1">
                <LiveCameraPanel scan={latestScan} />
                <div className="flex flex-col gap-6">
                  <AlertsFeed alerts={alerts} />
                </div>
              </div>
            </>
          )}

          {activeTab === "order-summary" && (
            <div className="w-full">
              <OrderSummary summary={summary} history={scanHistory} />
            </div>
          )}

          {activeTab === "history" && (
            <div className="w-full">
              <h1 className="text-ink text-2xl font-bold mb-1.5">Garment Scan History</h1>
              <p className="text-ink-secondary text-[13px] mb-7">
                Every garment detected and captured by the pipeline, most recent first.
              </p>
              <HistoryLog history={scanHistory} />
            </div>
          )}

          {activeTab === "alerts" && (
            <div className="w-full">
              <h1 className="text-ink text-2xl font-bold mb-1.5">System Alerts</h1>
              <p className="text-ink-secondary text-[13px] mb-7">
                Low-confidence detections and other events worth a second look.
              </p>
              <AlertsFeed alerts={alerts} />
            </div>
          )}

          {activeTab === "analytics" && (
            <div className="w-full h-full">
              <Analytics history={scanHistory} summary={summary} />
            </div>
          )}

          {activeTab === "settings" && (
            <div className="w-full">
              <SettingsPanel onSaved={refreshSummary} historyCount={scanHistory.length} onHistoryDeleted={handleHistoryDeleted} />
            </div>
          )}

          {activeTab === "downtime" && (
            <div className="w-full">
              <DowntimeLog />
            </div>
          )}

          {activeTab === "device-setup" && (
            <div className="w-full">
              <DeviceSetup onTestPassed={enterLiveDashboard} />
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
