// app/dashboard/quality/page.tsx
"use client";
import { useQualityStore }         from "@/store/qualityStore";
import { useQualitySimulator }     from "@/lib/hooks/useQualitySimulator";
import { GarmentAnalysisPanel }    from "@/components/dashboard/quality/GarmentAnalysisPanel";
import { SizeResultCard }          from "@/components/dashboard/quality/SizeResultCard";
import { StyleLabelCard }          from "@/components/dashboard/quality/StyleLabelCard";
import { ColourSwatchDisplay }     from "@/components/dashboard/quality/ColourSwatchDisplay";
import { QualityDecisionBadge }    from "@/components/dashboard/quality/QualityDecisionBadge";
import { CalibrationStatusCard }   from "@/components/dashboard/quality/CalibrationStatusCard";
import { SpecMatchTable }          from "@/components/dashboard/quality/SpecMatchTable";
import { InspectionLogTable }      from "@/components/dashboard/quality/InspectionLogTable";
import { InspectionRatioChart }    from "@/components/charts/InspectionRatioChart";
import { SizeDistributionChart }   from "@/components/charts/SizeDistributionChart";

// ── KPI Tile (private to page) ───────────────────────────────────
function KPITile({
  label, value, unit, sub, subColor, valueColor, flash,
  badge,
}: {
  label:       string;
  value:       string | number;
  unit?:       string;
  sub?:        string;
  subColor?:   string;
  valueColor?: string;
  flash?:      boolean;
  badge?:      { text: string; color: string };
}) {
  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ background: "#1A2536", border: "1px solid #243044", borderRadius: 12 }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 shrink-0"
        style={{ height: 44, background: "#131B26", borderBottom: "1px solid #243044" }}
      >
        <span className="font-mono text-text-muted uppercase" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
          {label}
        </span>
        {badge && (
          <span
            className="font-mono font-bold uppercase"
            style={{
              fontSize: 8, letterSpacing: "0.08em",
              padding: "3px 8px", borderRadius: 4,
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
      <div style={{ padding: "20px 20px 20px", flex: 1 }}>
        <div className="flex items-end gap-2" style={{ marginBottom: 6 }}>
          <span
            key={`${label}-${value}`}
            className="font-mono font-bold"
            style={{
              fontSize: 38, color: valueColor || "#E8ECF1",
              lineHeight: 1, letterSpacing: "-0.02em",
              animation: flash ? "countUp 0.3s ease-out" : "none",
            }}
          >
            {value}
          </span>
          {unit && (
            <span className="font-mono text-text-muted pb-1" style={{ fontSize: 15 }}>{unit}</span>
          )}
        </div>
        {sub && (
          <div className="font-mono" style={{ fontSize: 11, color: subColor || "#6B7A8D" }}>{sub}</div>
        )}
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────
export default function QualityDashboardPage() {
  const {
    approvedCount, reworkCount, mismatchCount,
  } = useQualityStore();

  useQualitySimulator("1x");

  const total    = approvedCount + reworkCount + mismatchCount;
  const passRate = total > 0 ? Math.round((approvedCount / total) * 100) : 0;
  const passColor =
    passRate >= 90 ? "#22C55E"
    : passRate >= 70 ? "#3B82F6"
    : passRate >= 50 ? "#FACC15"
    : "#EF4444";

  return (
    <div className="space-y-6 animate-fade-in min-w-0">

      {/* ══ ROW 1: KPI TILES ════════════════════════════════ */}
      <div className="grid gap-5" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
        <KPITile
          label="Approved"
          value={approvedCount}
          sub="PASS decisions"
          valueColor="#22C55E"
          flash
          badge={approvedCount > 0 ? { text: "PASS", color: "#22C55E" } : undefined}
        />
        <KPITile
          label="Rework"
          value={reworkCount}
          sub="Quality issues"
          valueColor="#FACC15"
          flash
          badge={reworkCount > 0 ? { text: "REWORK", color: "#FACC15" } : undefined}
        />
        <KPITile
          label="Mismatch"
          value={mismatchCount}
          sub="Spec violations"
          valueColor="#EF4444"
          flash
          badge={mismatchCount > 0 ? { text: "MISMATCH", color: "#EF4444" } : undefined}
        />
        <KPITile
          label="Pass Rate"
          value={total > 0 ? passRate : "—"}
          unit={total > 0 ? "%" : ""}
          sub={total > 0 ? `${total} total inspected` : "Awaiting inspections"}
          subColor={total > 0 ? passColor : "#3A4A5C"}
          valueColor={total > 0 ? passColor : "#3A4A5C"}
          badge={total > 0 ? {
            text: passRate >= 80 ? "Good" : passRate >= 60 ? "Fair" : "Low",
            color: passColor,
          } : undefined}
        />
      </div>

      {/* ══ ROW 2: CAMERA + QUALITY RESULTS ═════════════════
          Mirror of sewing dashboard Row 2 structure:
          3fr camera panel | 2fr 2×2 results grid
      ════════════════════════════════════════════════════ */}
      <div className="grid gap-5" style={{ gridTemplateColumns: "minmax(0, 3fr) minmax(0, 2fr)" }}>
        <GarmentAnalysisPanel />
        <div className="grid gap-4" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <SizeResultCard />
          <StyleLabelCard />
          <ColourSwatchDisplay />
          <QualityDecisionBadge />
        </div>
      </div>

      {/* ══ ROW 3: SPEC MATCH + CALIBRATION ═════════════════ */}
      <div className="grid gap-5" style={{ gridTemplateColumns: "minmax(0, 3fr) minmax(0, 2fr)" }}>
        <SpecMatchTable />
        <CalibrationStatusCard />
      </div>

      {/* ══ ROW 4: CHARTS + INSPECTION LOG ══════════════════ */}
      <div className="grid gap-5" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(0, 2fr) minmax(0, 3fr)" }}>
        <InspectionRatioChart />
        <SizeDistributionChart />
        <InspectionLogTable />
      </div>
    </div>
  );
}