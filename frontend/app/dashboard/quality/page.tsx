"use client";

import type { ReactElement } from "react";
import { CheckCircle2, Ruler, Shirt, SwatchBook } from "lucide-react";
import { useQualitySimulator } from "@/lib/hooks/useQualitySimulator";
import { formatCm, formatTime } from "@/lib/utils";
import { useQualityStore } from "@/store/qualityStore";
import { RegionalSizeConversionCard } from "@/components/dashboard/quality/RegionalSizeConversionCard";
import { CameraFrame, DataTable, MetricCard, PageHeader, Panel, StatusPill } from "@/components/industrial/Primitives";

export default function QualityDashboardPage() {
  useQualitySimulator("1x");

  const quality = useQualityStore();
  const current = quality.currentGarment;
  const total = quality.approvedCount + quality.reworkCount + quality.mismatchCount;
  const passRate = total ? Math.round((quality.approvedCount / total) * 100) : 0;
  const decisionTone = current?.decision === "PASS" ? "ok" : current?.decision === "REWORK" ? "warn" : current?.decision === "MISMATCH" ? "bad" : "muted";

  return (
    <div className="animate-in">
      <PageHeader
        eyebrow="Features 3 + 4 | Quality checker area"
        title="Live garment inspection"
        description="One fixed camera handles colour recognition, style recognition, cloth size measurement, calibration state, and production specification matching."
        actions={<StatusPill label={quality.isAnalysing ? "Analysing garment" : "Inspection feed live"} tone={quality.isAnalysing ? "warn" : "ok"} pulse />}
      />

      <div className="grid grid-4">
        <MetricCard label="Approved" value={quality.approvedCount} sub="PASS decisions" tone="ok" />
        <MetricCard label="Rework" value={quality.reworkCount} sub="Size or finish correction" tone="warn" />
        <MetricCard label="Mismatch" value={quality.mismatchCount} sub="Wrong spec/style/colour" tone="bad" />
        <MetricCard label="Pass rate" value={total ? passRate : "—"} unit={total ? "%" : ""} sub={`${total} inspected garments`} tone={passRate >= 80 ? "ok" : passRate >= 60 ? "warn" : "bad"} />
      </div>

      <div className="grid monitor-grid" style={{ marginTop: 16 }}>
        <Panel title="Current Garment Analysis" eyebrow="Camera measurement frame" action={<StatusPill label={quality.cameraStatus} tone="ok" pulse />}>
          <CameraFrame mode="quality">
            <div style={{ position: "absolute", inset: "58px 24% 46px", border: "2px solid rgba(47, 128, 237, 0.58)", borderRadius: 18 }} />
            <div style={{ position: "absolute", left: "30%", top: "26%" }}><StatusPill label={`Width ${current ? formatCm(current.sizeMeasurement.widthCm) : "--"}`} tone="info" /></div>
            <div style={{ position: "absolute", right: "24%", top: "58%" }}><StatusPill label={`Height ${current ? formatCm(current.sizeMeasurement.heightCm) : "--"}`} tone="cyan" /></div>
            <div className="camera-caption">
              <StatusPill label={`Ratio ${quality.calibration.pixelPerCmRatio} px/cm`} tone="ok" />
              <StatusPill label={quality.calibration.status} tone={quality.calibration.status === "calibrated" ? "ok" : "bad"} />
              <StatusPill label={current?.decision || "Awaiting garment"} tone={decisionTone} />
            </div>
          </CameraFrame>
        </Panel>

        <div className="grid">
          <Panel title="Recognition Results" eyebrow="Feature 3 + 4" action={<StatusPill label={current?.decision || "WAIT"} tone={decisionTone} />}>
            <div className="panel-body grid grid-2">
              <ResultFact icon={<Ruler />} label="Detected size" value={current?.sizeMeasurement.detectedSize || "—"} tone="info" />
              <ResultFact icon={<Shirt />} label="Detected style" value={current?.styleDetection.style || "—"} tone="cyan" />
              <ResultFact icon={<SwatchBook />} label="Primary colour" value={current?.colourDetections[0]?.name || "—"} tone="ok" />
              <ResultFact icon={<CheckCircle2 />} label="Confidence" value={current ? `${Math.round(current.overallConfidence * 100)}%` : "—"} tone={decisionTone === "muted" ? "info" : decisionTone} />
            </div>
          </Panel>

          <Panel title="Production Spec" eyebrow="Active PO">
            <div className="panel-body grid">
              <SummaryRow label="Spec label" value={quality.activeSpec.specLabel} />
              <SummaryRow label="Expected style" value={quality.activeSpec.expectedStyle} />
              <SummaryRow label="Expected size" value={quality.activeSpec.expectedSize} />
              <SummaryRow label="Expected colour" value={quality.activeSpec.expectedColours.join(", ")} />
            </div>
          </Panel>
        </div>
      </div>

      <div className="grid grid-3" style={{ marginTop: 16 }}>
        <Panel title="Specification Match" eyebrow="Detected vs expected" className="span-2">
          <DataTable
            headers={["Attribute", "Expected", "Detected", "Result"]}
            rows={(current?.specMatchResults || []).map(result => [
              result.label,
              result.expected,
              result.detected,
              <StatusPill key={result.attribute} label={result.isMatch ? "Match" : "Mismatch"} tone={result.isMatch ? "ok" : "bad"} />,
            ])}
          />
        </Panel>

        <RegionalSizeConversionCard />
      </div>

      <div style={{ marginTop: 16 }}>
        <Panel title="Inspection Logs" eyebrow="Recent garment records">
          <DataTable
            headers={["Time", "Spec", "Decision", "Size", "Style", "Colours", "Confidence"]}
            rows={quality.inspectionLog.slice(0, 9).map(record => [
              formatTime(new Date(record.timestamp)),
              record.specLabel,
              <StatusPill key={record.id} label={record.decision} tone={record.decision === "PASS" ? "ok" : record.decision === "REWORK" ? "warn" : "bad"} />,
              record.garmentAnalysis.sizeMeasurement.detectedSize,
              record.garmentAnalysis.styleDetection.style,
              record.garmentAnalysis.colourDetections.map(colour => colour.name).join(", "),
              `${Math.round(record.garmentAnalysis.overallConfidence * 100)}%`,
            ])}
          />
        </Panel>
      </div>
    </div>
  );
}

function ResultFact({ icon, label, value, tone }: { icon: ReactElement; label: string; value: string; tone: "ok" | "warn" | "bad" | "info" | "cyan" }) {
  return (
    <div className="panel" style={{ boxShadow: "none", padding: 14 }}>
      <div className={tone}>{icon}</div>
      <div className="meta-label" style={{ marginTop: 8 }}>{label}</div>
      <strong>{value}</strong>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, borderBottom: "1px solid var(--line-soft)", paddingBottom: 10 }}>
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
