// app/dashboard/sewing/page.tsx
"use client";
import { useSewingStore }        from "@/store/sewingStore";
import { useWorkstationStore }   from "@/store/workstationStore";
import { useSewingSimulator }    from "@/lib/hooks/useSewingSimulator";
import { CameraFeedCard }        from "@/components/dashboard/sewing/CameraFeedCard";
import { OperatorStatusCard }    from "@/components/dashboard/sewing/OperatorStatusCard";
import { ReworkCard }            from "@/components/dashboard/sewing/ReworkCard";
import { DowntimeCard }          from "@/components/dashboard/sewing/DowntimeCard";
import { IoTCard }               from "@/components/dashboard/sewing/IoTCard";
import { ShiftSummaryCard }      from "@/components/dashboard/sewing/ShiftSummaryCard";
import { EventTicker }           from "@/components/dashboard/sewing/EventTicker";
import { DetectionLog }          from "@/components/dashboard/sewing/DetectionLog";
import { PieceCountChart }       from "@/components/charts/PieceCountChart";
import { CycleTimeChart }        from "@/components/charts/CycleTimeChart";
import { HourlyChart }           from "@/components/charts/HourlyChart";
import { getCycleTimeColor }     from "@/lib/utils";
import { CYCLE_TIME }            from "@/lib/constants";

// ── KPI Tile (private to page) ────────────────────────────────────
function KPITile({
  label, value, unit, sub, subColor, valueColor, flash, badge,
}: {
  label:      string;
  value:      string | number;
  unit?:      string;
  sub?:       string;
  subColor?:  string;
  valueColor?: string;
  flash?:     boolean;
  badge?:     { text: string; color: string };
}) {
  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}
    >
      {/* Card header */}
      <div
        className="flex items-center justify-between px-4 shrink-0"
        style={{ height: 36, background: "#131B26", borderBottom: "1px solid #243044" }}
      >
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 8.5, letterSpacing: "0.14em" }}>
          {label}
        </span>
        {badge && (
          <span
            className="font-mono font-bold uppercase"
            style={{
              fontSize: 7, letterSpacing: "0.08em",
              padding: "2px 7px", borderRadius: 4,
              background: `${badge.color}14`,
              border: `1px solid ${badge.color}35`,
              color: badge.color,
            }}
          >
            {badge.text}
          </span>
        )}
      </div>

      {/* Value */}
      <div style={{ padding: "12px 16px 14px", flex: 1 }}>
        <div className="flex items-end gap-1.5" style={{ marginBottom: 4 }}>
          <span
            key={`${label}-${value}`}
            className="font-mono font-bold"
            style={{
              fontSize: 36,
              color: valueColor || "#E8ECF1",
              lineHeight: 1,
              letterSpacing: "-0.02em",
              animation: flash ? "countUp 0.3s ease-out" : "none",
            }}
          >
            {value}
          </span>
          {unit && (
            <span className="font-mono text-text-muted pb-1" style={{ fontSize: 14 }}>
              {unit}
            </span>
          )}
        </div>
        {sub && (
          <div className="font-mono" style={{ fontSize: 10.5, color: subColor || "#6B7A8D" }}>
            {sub}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────
export default function SewingDashboardPage() {
  const {
    pieceCount, currentCycleTimeSeconds,
    averageCycleTimeSeconds, cycleHistory,
  } = useSewingStore();
  const { config } = useWorkstationStore();

  // Start simulation
  useSewingSimulator("1x");

  const target = config.shiftTarget;
  const pct    = Math.min(Math.round((pieceCount / target) * 100), 100);

  const cycleColor = getCycleTimeColor(
    currentCycleTimeSeconds,
    CYCLE_TIME.TARGET_SECONDS,
    CYCLE_TIME.WARNING_SECONDS,
    CYCLE_TIME.DANGER_SECONDS,
  );
  const avgColor = getCycleTimeColor(
    averageCycleTimeSeconds,
    CYCLE_TIME.TARGET_SECONDS,
    CYCLE_TIME.WARNING_SECONDS,
    CYCLE_TIME.DANGER_SECONDS,
  );

  // Trend — last 5 vs previous 5
  const last5   = cycleHistory.slice(-5);
  const prev5   = cycleHistory.slice(-10, -5);
  const recentA = last5.length ? last5.reduce((s, r) => s + r.durationSeconds, 0) / last5.length : 0;
  const prevA   = prev5.length ? prev5.reduce((s, r) => s + r.durationSeconds, 0) / prev5.length : 0;
  const trend =
    prevA === 0 ? "Stable"
    : recentA < prevA - 1 ? "↓ Improving"
    : recentA > prevA + 1 ? "↑ Slowing"
    : "→ Stable";
  const trendColor =
    trend.includes("Improving") ? "#22C55E"
    : trend.includes("Slowing") ? "#FACC15"
    : "#6B7A8D";

  const cycleStatus =
    currentCycleTimeSeconds === 0 ? "Waiting…"
    : currentCycleTimeSeconds <= CYCLE_TIME.TARGET_SECONDS ? "On target ✓"
    : currentCycleTimeSeconds <= CYCLE_TIME.WARNING_SECONDS ? "Slightly slow"
    : "Above target";

  const cycleStatusColor =
    currentCycleTimeSeconds === 0 ? "#3A4A5C"
    : currentCycleTimeSeconds <= CYCLE_TIME.TARGET_SECONDS ? "#22C55E"
    : currentCycleTimeSeconds <= CYCLE_TIME.WARNING_SECONDS ? "#FACC15"
    : "#EF4444";

  return (
    <div className="space-y-4 animate-fade-in">

      {/* ══ ROW 1: KPI TILES ════════════════════════════════ */}
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}
      >
        <KPITile
          label="Total Pieces"
          value={pieceCount}
          sub={`Shift target: ${target} pcs`}
          subColor="#6B7A8D"
          flash
          badge={pct >= 100 ? { text: "Done!", color: "#22C55E" } : undefined}
        />
        <KPITile
          label="Current Cycle"
          value={currentCycleTimeSeconds || "—"}
          unit={currentCycleTimeSeconds ? "s" : ""}
          sub={cycleStatus}
          subColor={cycleStatusColor}
          valueColor={currentCycleTimeSeconds ? cycleColor : "#3A4A5C"}
          badge={{ text: `Target ${CYCLE_TIME.TARGET_SECONDS}s`, color: "#3A4A5C" }}
        />
        <KPITile
          label="Average Cycle"
          value={averageCycleTimeSeconds ? averageCycleTimeSeconds.toFixed(1) : "—"}
          unit={averageCycleTimeSeconds ? "s" : ""}
          sub={trend}
          subColor={trendColor}
          valueColor={averageCycleTimeSeconds ? avgColor : "#3A4A5C"}
        />
        <KPITile
          label="Shift Progress"
          value={pct}
          unit="%"
          sub={`${pieceCount} of ${target} pieces`}
          subColor={pct >= 100 ? "#22C55E" : pct >= 75 ? "#3B82F6" : "#6B7A8D"}
          valueColor={pct >= 100 ? "#22C55E" : pct >= 75 ? "#3B82F6" : "#E8ECF1"}
          badge={
            remaining() > 0
              ? { text: `${remaining()} left`, color: "#6B7A8D" }
              : { text: "Complete!", color: "#22C55E" }
          }
        />
      </div>

      {/* ══ ROW 2: CAMERA + STATUS GRID ═════════════════════ */}
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "minmax(0, 3fr) minmax(0, 2fr)" }}
      >
        {/* Camera feed — flex-col, view area grows to match status grid */}
        <CameraFeedCard />

        {/* Status 2×2 grid */}
        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: "1fr 1fr", gridTemplateRows: "1fr 1fr" }}
        >
          <OperatorStatusCard />
          <IoTCard />
          <ReworkCard />
          <DowntimeCard />
        </div>
      </div>

      {/* ══ ROW 3: CHARTS ═══════════════════════════════════ */}
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "minmax(0, 3fr) minmax(0, 2fr)" }}
      >
        <PieceCountChart />
        <CycleTimeChart />
      </div>

      {/* ══ ROW 4: SHIFT SUMMARY + EVENTS + HOURLY ══════════ */}
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(0, 3fr) minmax(0, 2fr)" }}
      >
        <ShiftSummaryCard />
        <EventTicker />
        <HourlyChart />
      </div>

      {/* ══ ROW 5: DETECTION LOG (full width) ═══════════════ */}
      <DetectionLog />
    </div>
  );

  function remaining() {
    return Math.max(target - pieceCount, 0);
  }
}