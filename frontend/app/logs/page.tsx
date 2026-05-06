"use client";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { DataTable, MetricCard, PageHeader, Panel, StatusPill } from "@/components/industrial/Primitives";
import { formatTime } from "@/lib/utils";
import { useQualityStore } from "@/store/qualityStore";
import { useSewingStore } from "@/store/sewingStore";
import { useWorkstationStore } from "@/store/workstationStore";

export default function LogsPage() {
  return (
    <DashboardShell>
      <LogsContent />
    </DashboardShell>
  );
}

function LogsContent() {
  const { config } = useWorkstationStore();
  const sewing = useSewingStore();
  const quality = useQualityStore();
  const isQuality = config.mode === "quality";
  const rows = isQuality
    ? quality.inspectionLog.slice(0, 20).map(item => [
        formatTime(new Date(item.timestamp)),
        "Inspection",
        item.specLabel,
        <StatusPill key={item.id} label={item.decision} tone={item.decision === "PASS" ? "ok" : item.decision === "REWORK" ? "warn" : "bad"} />,
        `${Math.round(item.garmentAnalysis.overallConfidence * 100)}%`,
      ])
    : sewing.detectionLog.slice(0, 20).map(item => [
        formatTime(new Date(item.timestamp)),
        "Piece detected",
        `Piece #${item.pieceNumber}`,
        <StatusPill key={item.id} label={`${item.cycleTimeSeconds}s cycle`} tone={item.cycleTimeSeconds <= 45 ? "ok" : item.cycleTimeSeconds <= 65 ? "warn" : "bad"} />,
        `${Math.round(item.confidenceScore * 100)}%`,
      ]);

  return (
    <div className="animate-in">
      <PageHeader
        eyebrow="Logs & history"
        title="Local production records"
        description="A compact history view for the currently configured workstation mode. These records are simulated locally and shaped for future local API persistence."
        actions={<StatusPill label={isQuality ? "Quality logs" : "Sewing logs"} tone="info" />}
      />
      <div className="grid grid-4">
        <MetricCard label="Mode" value={isQuality ? "Quality" : "Sewing"} sub={config.stationId} tone="info" />
        <MetricCard label="Sewing events" value={sewing.detectionLog.length} sub="Piece detections" tone="ok" />
        <MetricCard label="Inspections" value={quality.inspectionLog.length} sub="Garment records" tone="cyan" />
        <MetricCard label="Operator" value={config.operatorName || "—"} sub="Active session" tone="muted" />
      </div>
      <div style={{ marginTop: 16 }}>
        <Panel title="Session Event Table" eyebrow="Most recent first">
          <DataTable headers={["Time", "Type", "Reference", "Status", "Confidence"]} rows={rows} />
        </Panel>
      </div>
    </div>
  );
}
